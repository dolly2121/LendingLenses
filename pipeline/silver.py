"""Silver layer: the quality gate and the masking step (Phases.md Phase 3).

This file is shown on screen during the demo, so comments here explain WHY,
not what (Rules R5).
"""
import hashlib
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

# pandera checks for a minimum pandas version even though we only use its
# polars backend; this environment's pandas is older but irrelevant here, and
# the warning would otherwise clutter the live demo console (Design.md).
warnings.filterwarnings("ignore", message="pandera requires pandas")

import pandera.polars as pa
import polars as pl
from pandera.polars import Check, Column, DataFrameSchema

from pipeline import lake_io

REPO_ROOT = Path(__file__).resolve().parent.parent
BRONZE_LOANS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_loans"
BRONZE_CALLS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_calls"
SILVER_LOANS = REPO_ROOT / "data" / "lake" / "silver" / "silver_loans"
SILVER_CALLS = REPO_ROOT / "data" / "lake" / "silver" / "silver_calls"
QUARANTINE = REPO_ROOT / "data" / "lake" / "silver" / "quarantine"
DQ_AUDIT = REPO_ROOT / "data" / "lake" / "silver" / "dq_audit"

# Fixed anchor, matches generate_data.py's TODAY, so "not in the future" is
# deterministic regardless of the real run date (Rules: reproducible demo data).
TODAY = "2026-07-15"
STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]

# Fixed demo salt: deterministic, reproducible hashes across runs (a stated demo
# requirement). Production uses keyed HMAC via Azure Key Vault, never an
# application constant like this (see Architecture.md section 6).
MASK_SALT = "lendinglens-demo-fixed-salt"

# One Column entry per Phase 3's five checks (loan_id unique, state valid AU,
# loan_amount range, application_date not future, no nulls in key fields).
# strict=False: interest_rate/channel/customer_name pass through unchecked,
# they are out of Phase 3's declared scope.
LOAN_SCHEMA = DataFrameSchema({
    "loan_id": Column(str, nullable=False, unique=True),
    "state": Column(str, Check.isin(STATES), nullable=False),
    "loan_amount": Column(float, Check.in_range(0, 5_000_000, include_min=False, include_max=False), nullable=False),
    "loan_type": Column(str, nullable=False),
    "application_date": Column(str, Check.le(TODAY), nullable=False),
    "status": Column(str, nullable=False),
}, strict=False)

# Maps pandera's (column, raw check name) to a short, stable check_name used in
# quarantine and dq_audit. Decoupled from pandera's internal string formatting
# (which embeds parameters, e.g. "in_range(0, 5000000)") via prefix matching.
_CHECK_NAME_BY_PREFIX = [
    (("loan_id", "not_nullable"), "loan_id_not_null"),
    (("loan_id", "field_uniqueness"), "loan_id_unique"),
    (("state", "not_nullable"), "state_not_null"),
    (("state", "isin"), "state_valid_au"),
    (("loan_amount", "not_nullable"), "loan_amount_not_null"),
    (("loan_amount", "in_range"), "loan_amount_range"),
    (("loan_type", "not_nullable"), "loan_type_not_null"),
    (("application_date", "not_nullable"), "application_date_not_null"),
    (("application_date", "less_than_or_equal_to"), "application_date_not_future"),
    (("status", "not_nullable"), "status_not_null"),
]

REASONS = {
    "loan_id_not_null": "loan_id must not be null",
    "loan_id_unique": "duplicate loan_id",
    "state_not_null": "state must not be null",
    "state_valid_au": "state is not a valid AU state",
    "loan_amount_not_null": "loan_amount must not be null",
    "loan_amount_range": "loan_amount must be between 0 and 5,000,000",
    "loan_type_not_null": "loan_type must not be null",
    "application_date_not_null": "application_date must not be null",
    "application_date_not_future": "application_date must not be in the future",
    "status_not_null": "status must not be null",
}


def _check_name(column: str, raw_check: str) -> str:
    for (col, prefix), name in _CHECK_NAME_BY_PREFIX:
        if column == col and raw_check.startswith(prefix):
            return name
    return f"{column}_{raw_check}"


def mask_name(name: str) -> str:
    """SHA-256 with a fixed demo salt. Has its own test (Rules R3, R8)."""
    return hashlib.sha256(f"{MASK_SALT}{name}".encode("utf-8")).hexdigest()


def derive_risk_band(loan_amount: float, loan_type: str) -> str:
    """LOW/MEDIUM/HIGH from loan_amount thresholds, nudged by loan_type.

    Baseline by amount: <100k LOW, 100k-300k MEDIUM, >=300k HIGH.
    business/debt_consolidation step up one band (higher default risk in
    consumer lending); car/home_improvement step down one band (typically
    secured, lower risk). Explainable beats clever in a risk context
    (Architecture.md section 3).
    """
    bands = ["LOW", "MEDIUM", "HIGH"]
    idx = 0 if loan_amount < 100_000 else 1 if loan_amount < 300_000 else 2
    if loan_type in ("business", "debt_consolidation"):
        idx = min(idx + 1, 2)
    elif loan_type in ("car", "home_improvement"):
        idx = max(idx - 1, 0)
    return bands[idx]


def _validate_loans(df: pl.DataFrame) -> tuple[set[int], list[dict], dict[str, int]]:
    """Returns (bad row indices, quarantine rows, fail_count per check_name).

    fail_count always covers all 10 checks, including ones with zero failures,
    so dq_audit gets a complete per-run record (Architecture.md dq_audit contract).
    """
    fail_counts = {name: 0 for name in REASONS}
    bad_indices: set[int] = set()
    quarantine_rows: list[dict] = []
    try:
        LOAN_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as err:
        for row in err.failure_cases.iter_rows(named=True):
            check_name = _check_name(row["column"], row["check"])
            # pandera's polars backend can omit the row index (None) when every
            # row in a column fails a not_nullable check; recover it by
            # re-scanning for nulls instead of crashing the run (Rules R6).
            if row["index"] is None:
                indices = df.with_row_index("_i").filter(pl.col(row["column"]).is_null())["_i"].to_list()
            else:
                indices = [int(row["index"])]
            for idx in indices:
                # .get/setdefault, not direct indexing: an unrecognized check_name
                # (an unmapped pandera internal check) must still be quarantined
                # with a fallback reason, never crash the run (Rules R6).
                fail_counts[check_name] = fail_counts.get(check_name, 0) + 1
                bad_indices.add(idx)
                quarantine_rows.append({
                    "source_table": "loans",
                    "source_row_id": df[idx, "loan_id"],
                    "offending_field": row["column"],
                    # Never the full raw row, only the one offending value (Rules R3,
                    # Architecture.md quarantine contract) - stops an unmasked
                    # synthetic name ever reaching this table.
                    "offending_value": "" if row["failure_case"] is None else str(row["failure_case"]),
                    "check_name": check_name,
                    "reason": REASONS.get(check_name, f"{row['column']} failed check {check_name}"),
                })
    return bad_indices, quarantine_rows, fail_counts


def _build_silver_loans(good: pl.DataFrame) -> pl.DataFrame:
    return good.select(
        "loan_id",
        pl.col("customer_name").map_elements(mask_name, return_dtype=pl.Utf8).alias("customer_ref_hash"),
        "state",
        "loan_amount",
        "loan_type",
        "interest_rate",
        "channel",
        pl.struct(["loan_amount", "loan_type"])
          .map_elements(lambda s: derive_risk_band(s["loan_amount"], s["loan_type"]), return_dtype=pl.Utf8)
          .alias("risk_band"),
        "application_date",
        "status",
    )
    # customer_name is deliberately not selected: the raw name column never
    # reaches Silver (Rules R3).


def _audit_rows(table: str, fail_counts: dict[str, int], total: int) -> list[dict]:
    return [
        {"table": table, "check_name": name, "passed_count": total - fail, "failed_count": fail}
        for name, fail in fail_counts.items()
    ]


def _loans_already_processed() -> bool:
    if not lake_io.table_exists(DQ_AUDIT):
        return False
    return lake_io.read(DQ_AUDIT).filter(pl.col("table") == "loans").height > 0


def _calls_already_processed() -> bool:
    if not lake_io.table_exists(DQ_AUDIT):
        return False
    return lake_io.read(DQ_AUDIT).filter(pl.col("table") == "calls").height > 0


def process_loans(run_id: str) -> tuple[int, int]:
    """Returns (passed_count, quarantined_count) for THIS run, not the running
    total (mirrors bronze.py's idempotency style: 0/0 once already processed)."""
    if _loans_already_processed():
        return 0, 0

    df = lake_io.read(BRONZE_LOANS)
    bad_indices, quarantine_rows, fail_counts = _validate_loans(df)

    if quarantine_rows:
        q_df = pl.DataFrame(quarantine_rows).with_columns(
            pl.lit(run_id).alias("run_id"),
            pl.lit(datetime.now(timezone.utc)).alias("quarantined_at"),
        )
        lake_io.append(QUARANTINE, q_df)

    good = (
        df.with_row_index("_row_idx")
          .filter(~pl.col("_row_idx").is_in(list(bad_indices)))
          .drop("_row_idx")
    )
    silver_df = _build_silver_loans(good)
    if silver_df.height:
        lake_io.append(SILVER_LOANS, silver_df)

    audit_df = pl.DataFrame(_audit_rows("loans", fail_counts, df.height)).with_columns(
        pl.lit(run_id).alias("run_id"),
        pl.lit(datetime.now(timezone.utc)).alias("run_timestamp"),
    )
    lake_io.append(DQ_AUDIT, audit_df)

    return good.height, len(bad_indices)


def process_calls(run_id: str) -> tuple[int, int]:
    """Light call checks: file exists (implied, only landed files reach Bronze),
    transcript non-empty. Returns (passed_count, quarantined_count) for THIS run."""
    if _calls_already_processed():
        return 0, 0

    df = lake_io.read(BRONZE_CALLS)
    non_empty = df["transcript_text"].str.strip_chars().str.len_chars() > 0
    fail_count = int((~non_empty).sum())

    if fail_count:
        bad_rows = [
            {
                "source_table": "calls",
                "source_row_id": r["call_id"],
                "offending_field": "transcript_text",
                "offending_value": "",
                "check_name": "call_transcript_non_empty",
                "reason": "transcript is empty",
            }
            for r in df.filter(~non_empty).iter_rows(named=True)
        ]
        q_df = pl.DataFrame(bad_rows).with_columns(
            pl.lit(run_id).alias("run_id"),
            pl.lit(datetime.now(timezone.utc)).alias("quarantined_at"),
        )
        lake_io.append(QUARANTINE, q_df)

    good = df.filter(non_empty).select("call_id", "transcript_text")
    if good.height:
        lake_io.append(SILVER_CALLS, good)

    audit_df = pl.DataFrame([
        {"table": "calls", "check_name": "call_file_exists", "passed_count": df.height, "failed_count": 0},
        {"table": "calls", "check_name": "call_transcript_non_empty",
         "passed_count": df.height - fail_count, "failed_count": fail_count},
    ]).with_columns(
        pl.lit(run_id).alias("run_id"),
        pl.lit(datetime.now(timezone.utc)).alias("run_timestamp"),
    )
    lake_io.append(DQ_AUDIT, audit_df)

    return good.height, fail_count


def main() -> None:
    run_id = uuid.uuid4().hex
    passed, quarantined = process_loans(run_id)
    print(f"SILVER  loans:  {passed} passed          {quarantined} quarantined -> dq_audit")
    print(f"MASK    names:  {passed} hashed          0 raw names downstream")
    process_calls(run_id)


if __name__ == "__main__":
    main()
