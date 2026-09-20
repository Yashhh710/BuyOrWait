"""Deterministic facts from one official request context."""
from datetime import date
from typing import Any

import numpy as np


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_facts(context: dict[str, Any]) -> dict[str, Any]:
    request = context["request"]
    profile = context.get("profile") or {}
    events = context.get("events", [])
    currency = profile.get("home_currency", "")
    balance = _number(profile.get("current_available_balance")) or 0.0
    minimum = _number(profile.get("minimum_balance_to_keep")) or 0.0
    requested = _number(request.get("requested_amount")) or 0.0
    request_date = str(request.get("request_date"))

    settled_amounts = [
        _number(event.get("amount"))
        for event in events
        if event.get("status") == "settled"
        and event.get("direction") == "debit"
        and str(event.get("event_date", "")) <= request_date
    ]
    pending_amounts = [
        _number(event.get("amount"))
        for event in events
        if event.get("status") in {"pending", "scheduled"}
        and event.get("direction") == "debit"
        and str(event.get("event_date", "")) >= request_date
    ]
    unresolved_debits = int(np.sum([amount is None for amount in settled_amounts + pending_amounts]))
    settled_debits = float(np.sum([amount or 0 for amount in settled_amounts], dtype=float))
    pending_debits = float(np.sum([amount or 0 for amount in pending_amounts], dtype=float))
    protected_balance = float(np.maximum(minimum, pending_debits))
    if unresolved_debits:
        protected_balance = balance
    safe_today = float(np.clip(balance - protected_balance, 0.0, requested))
    recurring_fixed = float(np.sum([
        (_number(event.get("amount")) or 0)
        for event in events
        if event.get("event_type") == "expense"
        and event.get("flexibility") == "fixed"
        and event.get("direction") == "debit"
    ], dtype=float))
    return {
        "currency": currency,
        "current_available_balance": balance,
        "minimum_balance_to_keep": minimum,
        "requested_amount": requested,
        "safe_amount_today": float(np.round(safe_today, 2)),
        "settled_debits_before_request": float(np.round(settled_debits, 2)),
        "pending_debits": float(np.round(pending_debits, 2)),
        "unresolved_debit_count": unresolved_debits,
        "protected_balance": float(np.round(protected_balance, 2)),
        "recurring_fixed_expenses": float(np.round(recurring_fixed, 2)),
        "payment_option_count": len(context.get("payment_options", [])),
        "event_count": len(events),
        "as_of": request_date,
    }
