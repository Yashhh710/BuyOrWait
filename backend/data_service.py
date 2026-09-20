"""Official challenge dataset retrieval. Input files are read-only."""
from pathlib import Path
from typing import Any
from datetime import timedelta

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "official_dataset"


def _read(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def list_requests() -> list[dict[str, Any]]:
    frame = _read("requests.csv")
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def get_request_context(request_id: str) -> dict[str, Any] | None:
    requests = _read("requests.csv")
    match = requests[requests["request_id"].astype(str) == request_id]
    if match.empty:
        return None
    request = match.iloc[0].to_dict()
    user_id = str(request["user_id"])

    profiles = _read("financial_profiles.csv")
    profile_match = profiles[profiles["user_id"].astype(str) == user_id]
    events = _read("financial_events.csv")
    user_events = events[events["user_id"].astype(str) == user_id]
    request_day = pd.to_datetime(request["request_date"])
    event_dates = pd.to_datetime(user_events["event_date"], errors="coerce")
    relevant_events = user_events[
        event_dates.isna()
        | (event_dates >= request_day - timedelta(days=90))
        | user_events["status"].isin(["pending", "scheduled"])
    ]
    options = _read("request_payment_options.csv")
    request_options = options[options["request_id"].astype(str) == request_id]
    messages = _read("messages.csv")
    related_messages = messages[
        (messages["request_id"].fillna("").astype(str) == request_id)
        | (messages["user_id"].astype(str) == user_id)
    ]
    images = _read("images.csv")
    related_images = images[
        (images["request_id"].fillna("").astype(str) == request_id)
        | (images["user_id"].astype(str) == user_id)
    ]

    def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        # Cast to object first; otherwise pandas can retain NaN in float columns.
        clean = frame.astype(object).where(pd.notna(frame), None)
        return clean.to_dict(orient="records")

    def record(row: dict[str, Any]) -> dict[str, Any]:
        return {key: (None if pd.isna(value) else value) for key, value in row.items()}

    return {
        "request": record(request),
        "profile": record(profile_match.iloc[0].to_dict()) if not profile_match.empty else None,
        "events": records(user_events),
        "relevant_events": records(relevant_events),
        "payment_options": records(request_options),
        "messages": records(related_messages),
        "images": records(related_images),
    }
