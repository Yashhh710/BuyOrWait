"""Completed website analysis history, separate from official challenge inputs."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "app_history" / "analysis_history.csv"
HISTORY_COLUMNS = [
    "request_id", "request_summary", "amount", "decision", "risk_level",
    "safe_amount", "currency", "payment_method", "created_at", "source", "explanation",
]


def list_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        frame = pd.read_csv(HISTORY_PATH)
        return frame.where(pd.notna(frame), None).to_dict(orient="records")
    except (OSError, pd.errors.ParserError):
        return []


def append_analysis(request_id: str, request: dict[str, Any], result: dict[str, Any], source: str, facts: dict[str, Any] | None = None) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "request_id": request_id,
        "request_summary": request.get("request_text", request_id),
        "amount": request.get("requested_amount", 0),
        "decision": result.get("recommended_payment_method", "not_recommended"),
        "risk_level": result.get("risk_level", "UNKNOWN"),
        "safe_amount": result.get("amount_safe_to_pay", 0),
        "currency": (facts or {}).get("currency", ""),
        "payment_method": result.get("recommended_payment_method", "not_recommended"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "explanation": result.get("decision_explanation", ""),
    }
    # Coerce all values to plain Python scalars so pandas doesn't produce NaN on write
    row = {k: (str(v) if v is not None else "") for k, v in row.items()}
    previous = list_history()
    previous.append(row)
    updated = pd.DataFrame(previous, columns=HISTORY_COLUMNS)
    updated.to_csv(HISTORY_PATH, index=False)


def append_manual_analysis(payload: Any, decision: Any, source: str) -> None:
    request = {
        "request_text": payload.product_name,
        "requested_amount": payload.product_price,
    }
    result = {
        "recommended_payment_method": decision.recommendation,
        "amount_safe_to_pay": min(payload.product_price, payload.available_balance),
        "risk_level": decision.risk_level,
        "decision_explanation": decision.reasoning,
    }
    append_analysis(
        f"personal-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        request,
        result,
        source,
        {"currency": getattr(payload, "currency", "₹") or "₹"},
    )
