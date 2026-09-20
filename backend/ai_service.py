"""
ai_service.py

Handles the "genuine AI reasoning" part of the app.

We call Groq's OpenAI-compatible chat completions endpoint (fast + free tier,
good fit for a hackathon demo) with the user's financial snapshot and force
the model to answer with ONLY a JSON object matching our AIDecision schema.

If the API key is missing, the request fails, or the AI returns something
that doesn't validate against our schema, we fall back to a transparent
rule-based engine so the app never breaks the demo - but we tag the response
so the frontend/backend logs know which path was used.
"""

import os
import json
import logging
import math
from datetime import date
from typing import Tuple

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from models import PurchaseAnalysisRequest, AIDecision

load_dotenv()

logger = logging.getLogger("ai_service")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """You are a careful, conservative personal finance advisor embedded in an app called "Buy or Wait?".

You will be given a user's financial snapshot and a product they want to buy.
Analyze their real ability to afford the purchase without harming their financial safety net.

Consider:
- Remaining monthly budget = monthly_income - monthly_expenses - existing_commitments
- How many months of expenses their savings + available_balance would cover after the purchase
- Whether buying now would drop their emergency buffer below a safe threshold (~2-3 months of expenses)
- Whether installments or partial payment would be a healthier middle ground
- Whether they indicated they can reduce spending

You must respond with ONLY a single valid JSON object, no markdown fences, no commentary, matching EXACTLY this shape:

{
    "recommendation": "PAY_IN_FULL",
    "confidence": 86,
    "risk_level": "LOW",
    "reasoning": "Buying this purchase now is affordable.",
    "financial_impact": "The purchase remains within the available balance.",
    "months_to_wait": 0,
    "recommended_purchase_date": "2026-09-13",
    "monthly_saving_target": 0,
    "payment_strategy": "PAY_IN_FULL",
    "next_step": "Proceed while continuing to monitor your budget."
}

STRICT RULES — you MUST follow these exactly:

recommendation must be EXACTLY one of:
  PAY_IN_FULL       — user can and should pay the full amount now
  PAY_PARTIALLY     — user can pay part now and the rest later
  USE_INSTALLMENTS  — user should spread the cost into installments
  WAIT              — user should wait and save before buying
  DO_NOT_PROCEED    — user should not make this purchase at all

DO NOT use: BUY_NOW, buy_now, APPROVE, REJECT, YES, NO, or any other value.

payment_strategy must be EXACTLY one of:
  PAY_IN_FULL
  PAY_PARTIALLY
  SAVE_AND_BUY
  USE_INSTALLMENTS
  WAIT

DO NOT use: BUY_NOW or any other value.

risk_level must be EXACTLY one of: LOW, MEDIUM, HIGH

months_to_wait must be an integer >= 0. Use 0 when recommendation is PAY_IN_FULL or PAY_PARTIALLY.

recommended_purchase_date must be a valid YYYY-MM-DD date string. Use today's date when months_to_wait is 0.

monthly_saving_target must be a number >= 0. Use 0 when months_to_wait is 0.

confidence must be an integer between 0 and 100.

The wait duration, date, and saving target must be consistent with one another and with the user's verified numbers. Do not invent financial inputs.
Return ONLY the JSON object. No markdown. No explanation. No extra text."""


def _build_user_prompt(payload: PurchaseAnalysisRequest) -> str:
    today = date.today().isoformat()
    remaining_budget = (
        payload.monthly_income - payload.monthly_expenses - payload.existing_commitments
    )
    return f"""Product: {payload.product_name}
Price: {payload.product_price}
Available balance: {payload.available_balance}
Monthly income: {payload.monthly_income}
Monthly expenses: {payload.monthly_expenses}
Existing monthly commitments: {payload.existing_commitments}
Savings: {payload.savings}
Remaining monthly budget (computed): {remaining_budget}
Can the user reduce discretionary spending if needed?: {"Yes" if payload.can_reduce_spending else "No"}

Analyze whether this user should buy this product now, in part, via installments, wait, or not proceed at all.
Current date: {today}
Return months_to_wait, recommended_purchase_date, and monthly_saving_target in the JSON response."""


def _get_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    return api_key


def _post_groq(messages: list, temperature: float, max_tokens: int) -> dict:
    """Shared Groq call used by both _call_groq and _call_groq_prompt."""
    api_key = _get_api_key()
    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=20,
    )
    if not response.ok:
        # Surface the real reason (401 bad key, 403 forbidden/org issue,
        # 429 rate limited, 400 bad request, etc.) instead of a bare fallback.
        logger.warning(
            "Groq request failed: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_groq(payload: PurchaseAnalysisRequest) -> dict:
    return _post_groq(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(payload)},
        ],
        temperature=0.3,
        max_tokens=1200,
    )


def _rule_based_fallback(payload: PurchaseAnalysisRequest) -> dict:
    """
    Transparent, deterministic fallback used only if the AI call fails
    or returns invalid data. Keeps the app functional end-to-end for
    the demo/judging even without a live API key.
    """
    remaining_budget = (
        payload.monthly_income - payload.monthly_expenses - payload.existing_commitments
    )
    total_liquid = payload.available_balance + payload.savings
    buffer_after_purchase = total_liquid - payload.product_price
    months_expenses_covered_after = (
        buffer_after_purchase / payload.monthly_expenses if payload.monthly_expenses > 0 else 0
    )

    if payload.product_price <= payload.available_balance and months_expenses_covered_after >= 2:
        rec, conf, risk = "PAY_IN_FULL", 80, "LOW"
        impact = "Paying in full stays within your available balance while keeping over two months of expenses in reserve."
        step = "Proceed with the purchase and monitor your budget as usual."
    elif payload.product_price <= total_liquid and months_expenses_covered_after >= 1:
        rec, conf, risk = "PAY_PARTIALLY", 72, "MEDIUM"
        impact = "A full purchase now would slightly weaken your safety buffer; paying partially preserves more cushion."
        step = "Pay a portion now and cover the rest from next month's income."
    elif remaining_budget > payload.product_price / 6:
        rec, conf, risk = "USE_INSTALLMENTS", 74, "MEDIUM"
        impact = "Your monthly budget can absorb installment payments without touching your emergency savings."
        step = "Spread the cost over 3-6 months via installments instead of paying upfront."
    elif payload.can_reduce_spending:
        rec, conf, risk = "WAIT", 65, "MEDIUM"
        impact = "Buying now would cut into your buffer, but reducing discretionary spending for a short period could change that."
        step = "Wait 1-2 months while trimming discretionary expenses, then re-evaluate."
    else:
        rec, conf, risk = "DO_NOT_PROCEED", 78, "HIGH"
        impact = "This purchase would leave you with too little of a financial cushion given your current income and expenses."
        step = "Hold off on this purchase and focus on rebuilding savings first."

    if rec in {"PAY_IN_FULL", "PAY_PARTIALLY"}:
        months_to_wait = 0
    elif rec == "USE_INSTALLMENTS":
        months_to_wait = 1
    elif rec == "WAIT":
        saving_capacity = max(remaining_budget * 0.6, 1)
        months_to_wait = min(120, max(1, math.ceil(payload.product_price / saving_capacity)))
    else:
        months_to_wait = 0

    monthly_saving_target = (
        math.ceil(payload.product_price / months_to_wait / 100) * 100
        if months_to_wait > 0
        else 0
    )

    return {
        "recommendation": rec,
        "confidence": conf,
        "risk_level": risk,
        "reasoning": (
            f"Based on a remaining monthly budget of {remaining_budget:.2f} and combined liquid funds "
            f"(balance + savings) of {total_liquid:.2f} against a price of {payload.product_price:.2f}, "
            f"this option best balances affordability with financial safety."
        ),
        "financial_impact": impact,
        "months_to_wait": months_to_wait,
        "recommended_purchase_date": _add_months(date.today(), months_to_wait).isoformat(),
        "monthly_saving_target": monthly_saving_target,
        "payment_strategy": {
            "PAY_IN_FULL": "PAY_IN_FULL",
            "PAY_PARTIALLY": "PAY_PARTIALLY",
            "USE_INSTALLMENTS": "USE_INSTALLMENTS",
            "WAIT": "SAVE_AND_BUY",
            "DO_NOT_PROCEED": "WAIT",
        }[rec],
        "next_step": step,
    }


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, 28))


def get_ai_decision(payload: PurchaseAnalysisRequest) -> Tuple[AIDecision, str]:
    """
    Returns (validated_decision, source) where source is "ai" or "fallback".
    """
    try:
        raw = _call_groq(payload)
        decision = AIDecision(**raw)
        return decision, "ai"
    except (requests.RequestException, RuntimeError, ValueError, KeyError, ValidationError) as exc:
        logger.warning("AI call failed or returned invalid data, using fallback: %s", exc)
        raw = _rule_based_fallback(payload)
        decision = AIDecision(**raw)
        return decision, "fallback"


def get_dataset_decision(context: dict, facts: dict) -> tuple[dict, str]:
    """Use only one retrieved request context and verified facts for judgment."""
    request = context["request"]
    profile = context.get("profile") or {}
    prompt = f"""You are the judgment layer for the Buy or Wait challenge.
Use only the retrieved request, profile, payment options, messages, and verified facts below.
Do not invent balances, events, income, preferences, or evidence. If evidence is insufficient, say so.
Choose a safe result that respects the request deadline and minimum balance.
Use exactly these enum values, with no synonyms:
affordability_status = affordable_now | affordable_with_plan | affordable_later | not_affordable
recommended_payment_method = full_payment | partial_payment | installments | wait | not_recommended
Use numeric amount_safe_to_pay between 0 and requested_amount. Use "none" for empty plans or spending changes.

REQUEST: {json.dumps(request, default=str)}
PROFILE: {json.dumps(profile, default=str)}
PAYMENT_OPTIONS: {json.dumps(context.get('payment_options', []), default=str)}
RELEVANT_EVENTS: {json.dumps(context.get('relevant_events', []), default=str)}
RELEVANT_MESSAGES: {json.dumps(context.get('messages', []), default=str)}
RELEVANT_IMAGE_REFERENCES: {json.dumps(context.get('images', []), default=str)}
VERIFIED_FACTS: {json.dumps(facts, default=str)}

Return only JSON with exactly these fields:
{{"amount_safe_to_pay": 0, "affordability_status": "not_affordable", "recommended_payment_method": "not_recommended", "payment_plan": "none", "earliest_date_for_full_payment": "", "spending_changes_needed": "none", "decision_explanation": "Explain using only supplied facts."}}"""
    try:
        raw = _call_groq_prompt(prompt)
        raw.setdefault("request_id", request["request_id"])
        from verifier import verify_output
        verify_output(raw, facts)
        return raw, "ai"
    except (requests.RequestException, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Dataset AI failed, using verified safe fallback: %s", exc)
        amount = round(float(facts["safe_amount_today"]), 2)
        requested = float(facts["requested_amount"])
        status = "affordable_now" if amount >= requested else "not_affordable"
        method = "full_payment" if status == "affordable_now" else "not_recommended"
        return {
            "request_id": request["request_id"],
            "amount_safe_to_pay": amount,
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": f"{facts['as_of']}:{requested:g}" if status == "affordable_now" else "none",
            "earliest_date_for_full_payment": facts["as_of"] if status == "affordable_now" else "",
            "spending_changes_needed": "none",
            "decision_explanation": f"Verified balance {facts['current_available_balance']:.2f} and protected balance {facts['protected_balance']:.2f} were used; live judgment was unavailable.",
        }, "fallback"


def _call_groq_prompt(prompt: str) -> dict:
    return _post_groq(
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1600,
    )