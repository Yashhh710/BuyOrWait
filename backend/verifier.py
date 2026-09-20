"""Validation for official challenge output and model decisions."""
from datetime import date
from typing import Any

OUTPUT_COLUMNS = [
    "request_id", "amount_safe_to_pay", "affordability_status",
    "recommended_payment_method", "payment_plan",
    "earliest_date_for_full_payment", "spending_changes_needed",
    "decision_explanation",
]
STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}


def verify_output(row: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    amount = float(row.get("amount_safe_to_pay", 0))
    requested = float(facts["requested_amount"])
    if not 0 <= amount <= requested:
        raise ValueError("amount_safe_to_pay is outside the request bounds")
    if row.get("affordability_status") not in STATUSES:
        raise ValueError("invalid affordability_status")
    if row.get("recommended_payment_method") not in METHODS:
        raise ValueError("invalid recommended_payment_method")
    if row.get("earliest_date_for_full_payment"):
        date.fromisoformat(str(row["earliest_date_for_full_payment"]))
    if not row.get("request_id") or not row.get("decision_explanation"):
        raise ValueError("missing required decision fields")
    return row
