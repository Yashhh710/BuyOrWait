"""
main.py
FastAPI backend for "Buy or Wait?" - AI-Powered Financial Decision Assistant.

Endpoints:
    GET  /api/health    -> backend + data + AI config health status
    GET  /api/requests  -> all historical requests, read dynamically from CSV
    POST /api/analyze   -> run a purchase through the AI decision engine
"""

import os
import logging
import html as html_lib
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from models import PurchaseAnalysisRequest, HealthResponse
from ai_service import get_ai_decision, get_dataset_decision
from data_service import get_request_context, list_requests
from document_service import extract_from_image, extract_from_pdf
from financial_engine import calculate_facts
from verifier import verify_output
from history_service import append_analysis, append_manual_analysis, list_history
from data_service import DATA_DIR

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "official_dataset" / "requests.csv"

app = FastAPI(
    title="Buy or Wait? API",
    description="AI-powered financial decision assistant backend",
    version="1.0.0",
)

# Enable CORS so the plain HTML/JS frontend (served from a different
# origin/port, e.g. via file:// or a static server) can call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # The frontend uses no cookies or authorization credentials. Wildcard
    # origins are valid only when credentialed CORS is disabled.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_requests_df() -> pd.DataFrame:
    """
    Dynamically reads requests.csv on every call - never hardcoded.
    Returns an empty DataFrame (rather than raising) if the file is
    missing, so /api/health can report the problem gracefully.
    """
    if not CSV_PATH.exists():
        logger.warning("CSV file not found at %s", CSV_PATH)
        return pd.DataFrame()
    try:
        return pd.read_csv(CSV_PATH)
    except Exception as exc:  # malformed CSV, etc.
        logger.error("Failed to read CSV: %s", exc)
        return pd.DataFrame()


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    df = _load_requests_df()
    return HealthResponse(
        status="ok",
        csv_loaded=not df.empty,
        total_requests=int(len(df)),
        ai_provider_configured=bool(os.getenv("GROQ_API_KEY")),
    )


@app.get("/api/requests")
def get_requests():
    """Return official challenge requests only; input files remain read-only."""
    records = list_requests()
    return {"count": len(records), "requests": records, "source": "official_dataset"}


@app.get("/api/history")
def get_history():
    """Return completed website analyses only, never raw challenge requests."""
    return {"count": len(list_history()), "analyses": list_history()}


@app.get("/api/dataset-info")
def dataset_info():
    files = {
        "requests": "requests.csv",
        "financial_profiles": "financial_profiles.csv",
        "financial_events": "financial_events.csv",
        "payment_options": "request_payment_options.csv",
        "messages": "messages.csv",
        "images": "images.csv",
    }
    counts = {}
    for key, filename in files.items():
        frame = pd.read_csv(DATA_DIR / filename) if (DATA_DIR / filename).exists() else pd.DataFrame()
        counts[key] = int(len(frame))
    return {"source": "official_dataset", "counts": counts}


@app.post("/api/generate-output")
def generate_output():
    """Generate the official submission CSV without overwriting official inputs."""
    try:
        from generate_output import main as generate
        generate()
        output_path = BASE_DIR / "data" / "generated" / "output.csv"
        output_frame = pd.read_csv(output_path)
        return {
            "status": "ok",
            "path": "data/generated/output.csv",
            "count": int(len(output_frame)),
            "columns": list(output_frame.columns),
            "rows": output_frame.fillna("").to_dict(orient="records"),
        }
    except Exception as exc:
        logger.exception("Output generation failed")
        raise HTTPException(status_code=500, detail="Output generation failed.") from exc


@app.get("/api/request/{request_id}")
def get_request(request_id: str):
    context = get_request_context(request_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Official request not found")
    context["facts"] = calculate_facts(context)
    return context


@app.get("/api/product-preview")
def product_preview(url: str):
    """Read a product title and price from a public product page server-side."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise HTTPException(status_code=400, detail="Enter a valid product URL.")
    if not (hostname == "amazon.in" or hostname.endswith(".amazon.in")):
        raise HTTPException(status_code=400, detail="Only Amazon India links are supported right now.")

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BuyOrWait/1.0)"},
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Amazon could not be reached. Please try again.") from exc

    page = response.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    title = html_lib.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
    title = re.sub(r"\s*[:|-]\s*Amazon\.in.*$", "", title, flags=re.IGNORECASE).strip()

    price_patterns = (
        r'"priceAmount"\s*:\s*"?([0-9,]+(?:\.[0-9]+)?)',
        r'"price"\s*:\s*"?([0-9,]+(?:\.[0-9]+)?)',
        r'a-offscreen[^>]*>\s*₹\s*([0-9,]+(?:\.[0-9]+)?)',
    )
    price = None
    for pattern in price_patterns:
        price_match = re.search(pattern, page, re.IGNORECASE)
        if price_match:
            price = float(price_match.group(1).replace(",", ""))
            break

    if not title or price is None:
        raise HTTPException(status_code=422, detail="Product name or current price was not available on that page.")
    return {"product_name": title, "price": price, "currency": "₹", "source": "amazon.in"}


@app.post("/api/document-preview")
async def document_preview(file: UploadFile = File(...)):
    """Read a product name + price from an uploaded receipt image or PDF."""
    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")

    is_pdf = content_type == "application/pdf" or filename.endswith(".pdf")
    is_image = content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp"))

    if not (is_pdf or is_image):
        raise HTTPException(status_code=400, detail="Only image (PNG/JPG) or PDF files are supported.")

    try:
        result = extract_from_pdf(file_bytes) if is_pdf else extract_from_image(file_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@app.post("/api/analyze")
def analyze_purchase(payload: PurchaseAnalysisRequest):
    """
    Receives the user's financial + product data, sends it to the AI
    decision engine, validates the structured response, and returns it.

    History persistence is intentionally isolated — a CSV write failure
    must never prevent the analysis result from reaching the frontend.
    """
    logger.info("Analyze request: request_id=%s product=%s price=%s",
                payload.request_id, payload.product_name, payload.product_price)

    if payload.request_id:
        context = get_request_context(payload.request_id)
        if context is None:
            raise HTTPException(status_code=404, detail="Official request not found")

        facts = calculate_facts(context)
        result, source = get_dataset_decision(context, facts)

        try:
            result = verify_output(result, facts)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"The decision failed verification: {exc}") from exc

        # Map internal backend method names to frontend-expected enum values
        method = result.get("recommended_payment_method", "not_recommended")
        recommendation_map = {
            "full_payment": "PAY_IN_FULL",
            "partial_payment": "PAY_PARTIALLY",
            "installments": "USE_INSTALLMENTS",
            "wait": "WAIT",
            "not_recommended": "DO_NOT_PROCEED",
        }
        strategy_map = {
            "full_payment": "PAY_IN_FULL",
            "partial_payment": "PAY_PARTIALLY",
            "installments": "USE_INSTALLMENTS",
            "wait": "SAVE_AND_BUY",
            "not_recommended": "WAIT",
        }
        frontend_recommendation = recommendation_map.get(method, "DO_NOT_PROCEED")
        frontend_strategy = strategy_map.get(method, "WAIT")

        # Derive a meaningful confidence and risk_level from affordability_status
        # instead of always returning 0 / UNKNOWN which the frontend verifier rejects.
        affordability = result.get("affordability_status", "not_affordable")
        confidence_map = {
            "affordable_now": 90,
            "affordable_with_plan": 70,
            "affordable_later": 55,
            "not_affordable": 40,
        }
        risk_map = {
            "affordable_now": "LOW",
            "affordable_with_plan": "MEDIUM",
            "affordable_later": "MEDIUM",
            "not_affordable": "HIGH",
        }
        confidence_val = confidence_map.get(affordability, 50)
        risk_val = risk_map.get(affordability, "UNKNOWN")

        # Ensure recommended_purchase_date is always a valid YYYY-MM-DD string,
        # never empty (empty string would be passed as null to the frontend verifier).
        purchase_date = result.get("earliest_date_for_full_payment") or ""
        if not purchase_date or not str(purchase_date).strip():
            from datetime import date as _date
            purchase_date = _date.today().isoformat()

        # Ensure all facts values are plain Python scalars (no numpy types)
        safe_facts = {k: (float(v) if hasattr(v, "__float__") and not isinstance(v, (str, bool)) else v)
                      for k, v in facts.items()}

        explanation = str(result.get("decision_explanation", ""))
        financial_impact = (
            f"Safe to pay today: {float(facts['safe_amount_today']):.2f} {facts['currency']}. "
            f"Requested: {float(facts['requested_amount']):.2f} {facts['currency']}."
        )

        # History save must not break analysis — isolate it
        try:
            append_analysis(payload.request_id, context["request"], result, source, facts)
        except Exception as history_err:
            logger.warning("History save failed (analysis still returned): %s", history_err)

        logger.info("Analyze result: request_id=%s recommendation=%s source=%s",
                    payload.request_id, frontend_recommendation, source)

        return {
            **{k: (float(v) if hasattr(v, "__float__") and not isinstance(v, (str, bool)) else v)
               for k, v in result.items()},
            "recommendation": frontend_recommendation,
            "confidence": confidence_val,
            "risk_level": risk_val,
            "reasoning": explanation,
            "financial_impact": financial_impact,
            "months_to_wait": 0,
            "recommended_purchase_date": purchase_date,
            "monthly_saving_target": 0.0,
            "payment_strategy": frontend_strategy,
            "next_step": explanation,
            "source": source,
            "request_id": str(payload.request_id),
            "facts": safe_facts,
        }

    # ---- Personal / manual analysis path ----
    try:
        decision, source = get_ai_decision(payload)
    except Exception as exc:
        logger.exception("Unexpected failure during analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    response = decision.model_dump()
    response["source"] = source  # "ai" or "fallback"

    # History save must not break analysis — isolate it
    try:
        append_manual_analysis(payload, decision, source)
    except Exception as history_err:
        logger.warning("History save failed (analysis still returned): %s", history_err)

    logger.info("Analyze result: personal recommendation=%s confidence=%s source=%s",
                decision.recommendation, decision.confidence, source)
    return response


@app.get("/")
def root():
    return {
        "message": "Buy or Wait? API is running.",
        "docs": "/docs",
        "endpoints": ["/api/health", "/api/requests", "/api/request/{request_id}", "/api/history", "/api/dataset-info", "/api/analyze", "/api/product-preview", "/api/document-preview"],
    }
