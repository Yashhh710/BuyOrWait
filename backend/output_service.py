"""Write generated challenge predictions separately from official inputs."""
from pathlib import Path
from typing import Any

import pandas as pd

from verifier import OUTPUT_COLUMNS, verify_output

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "generated" / "output.csv"


def write_output(rows: list[dict[str, Any]], facts_by_request: dict[str, dict[str, Any]]) -> Path:
    checked = [verify_output(row, facts_by_request[row["request_id"]]) for row in rows]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(checked, columns=OUTPUT_COLUMNS).to_csv(OUTPUT_PATH, index=False)
    return OUTPUT_PATH
