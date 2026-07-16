"""Orchestrates the batch pipeline: Bronze, Silver, Gold, then a run summary
snapshot for the dashboard's quality panel (Phases.md Phase 8, item 1).
`make pipeline` and `make demo` both call this."""
import uuid
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from pipeline import bronze, gold, lake_io, silver

REPO_ROOT = Path(__file__).resolve().parent.parent
BRONZE_LOANS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_loans"
BRONZE_CALLS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_calls"
SILVER_LOANS = REPO_ROOT / "data" / "lake" / "silver" / "silver_loans"
SILVER_CALLS = REPO_ROOT / "data" / "lake" / "silver" / "silver_calls"
QUARANTINE = REPO_ROOT / "data" / "lake" / "silver" / "quarantine"
GOLD_LOAN_SUMMARY = REPO_ROOT / "data" / "lake" / "gold" / "gold_loan_summary"
RUN_SUMMARY = REPO_ROOT / "data" / "lake" / "silver" / "run_summary"


def _height(table_path: Path) -> int:
    return lake_io.read(table_path).height if lake_io.table_exists(table_path) else 0


def _write_run_summary() -> None:
    """One row per pipeline invocation: a current-state snapshot, not this
    run's delta (unlike the per-stage console lines) - so a presenter sees
    "where things stand" even after an idempotent no-op rerun."""
    quarantine = lake_io.read(QUARANTINE) if lake_io.table_exists(QUARANTINE) else pl.DataFrame()
    loans_quarantined = quarantine.filter(pl.col("source_table") == "loans").height if quarantine.height else 0
    calls_quarantined = quarantine.filter(pl.col("source_table") == "calls").height if quarantine.height else 0

    row = pl.DataFrame([{
        "run_id": uuid.uuid4().hex,
        "run_timestamp": datetime.now(timezone.utc),
        "loans_landed": _height(BRONZE_LOANS),
        "loans_passed": _height(SILVER_LOANS),
        "loans_quarantined": loans_quarantined,
        "calls_landed": _height(BRONZE_CALLS),
        "calls_passed": _height(SILVER_CALLS),
        "calls_quarantined": calls_quarantined,
        "gold_loan_summary_rows": _height(GOLD_LOAN_SUMMARY),
    }])
    lake_io.append(RUN_SUMMARY, row)


def main() -> None:
    bronze.main()
    silver.main()
    gold.main()
    _write_run_summary()


if __name__ == "__main__":
    main()
