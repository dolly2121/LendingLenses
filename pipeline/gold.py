"""Gold layer: business-ready tables. Contracts frozen after this phase (Rules R7)."""
import warnings
from datetime import datetime, timezone
from pathlib import Path

# See silver.py: pandera checks for a minimum pandas version even though only
# its polars backend is used here; keeps the live demo console clean.
warnings.filterwarnings("ignore", message="pandera requires pandas")

import polars as pl
from pandera.polars import Column, DataFrameSchema

from pipeline import lake_io

REPO_ROOT = Path(__file__).resolve().parent.parent
SILVER_LOANS = REPO_ROOT / "data" / "lake" / "silver" / "silver_loans"
GOLD_LOAN_SUMMARY = REPO_ROOT / "data" / "lake" / "gold" / "gold_loan_summary"
GOLD_CALL_INSIGHTS = REPO_ROOT / "data" / "lake" / "gold" / "gold_call_insights"
GOLD_LOAN_OPS = REPO_ROOT / "data" / "lake" / "gold" / "gold_loan_ops"
GOLD_CHANNEL_BY_STATE = REPO_ROOT / "data" / "lake" / "gold" / "gold_channel_by_state"

# strict=True: no column beyond this exact set may exist. This is the guard
# against a direct identifier ever leaking into Gold (Architecture.md section 4,
# PII class D - Gold carries no identifiers of any class). It is a self-check on
# our own output shape, so a violation is a bug in this pipeline, not bad input
# data - it raises rather than being quarantined (contrast with silver.py).
GOLD_LOAN_SUMMARY_SCHEMA = DataFrameSchema({
    "state": Column(str),
    "risk_band": Column(str),
    "loan_count": Column(int),
    "total_amount": Column(float),
    "avg_amount": Column(float),
    "last_updated": Column(pl.Datetime("us", "UTC")),
}, strict=True)

GOLD_CALL_INSIGHTS_SCHEMA = DataFrameSchema({
    "call_id": Column(str),
    "transcript_masked": Column(str),
    "sentiment_score": Column(float),
    "hardship_flag": Column(bool),
    "complaint_flag": Column(bool),
    # enquiry_type added by explicit human request (Rules R7 - Phase 4 frozen
    # contract change, authorized). hardship_flag/complaint_flag kept as-is
    # for backward compatibility; this must match ai_service/call_pipeline.py's
    # publish_gold() column-for-column, or the live writer and this module's
    # empty-table init below disagree on schema (see init_call_insights()).
    "enquiry_type": Column(str),
    "processed_at": Column(pl.Datetime("us", "UTC")),
}, strict=True)

# New table, added by explicit human request (not part of the Phase 4 frozen
# set - gold_loan_summary/gold_call_insights are untouched). Same no-PII
# self-check as the other Gold tables (Rules R3): channel/loan_type are both
# class N, no identifiers.
GOLD_LOAN_OPS_SCHEMA = DataFrameSchema({
    "channel": Column(str),
    "loan_type": Column(str),
    "loan_count": Column(int),
    "total_amount": Column(float),
    "avg_amount": Column(float),
}, strict=True)

# New table, added by explicit human request (not part of the Phase 4 frozen
# set). state is class I in silver_loans but, like gold_loan_summary, this is
# an aggregate with no per-loan rows - no identifier survives (Rules R3,
# Architecture.md section 4: "Gold is aggregate or flag level only").
GOLD_CHANNEL_BY_STATE_SCHEMA = DataFrameSchema({
    "state": Column(str),
    "channel": Column(str),
    "loan_count": Column(int),
    "total_amount": Column(float),
}, strict=True)


def build_loan_summary() -> int:
    """Aggregated by state and risk_band. Idempotent: skips if Gold already
    exists, matching bronze.py/silver.py's compute-once pattern for this
    single-batch demo dataset (see Memory.md)."""
    if lake_io.table_exists(GOLD_LOAN_SUMMARY):
        return 0

    silver = lake_io.read(SILVER_LOANS)
    summary = (
        silver.group_by(["state", "risk_band"])
        .agg(
            pl.len().cast(pl.Int64).alias("loan_count"),
            pl.col("loan_amount").sum().alias("total_amount"),
            pl.col("loan_amount").mean().alias("avg_amount"),
        )
        .with_columns(pl.lit(datetime.now(timezone.utc)).alias("last_updated"))
        .select("state", "risk_band", "loan_count", "total_amount", "avg_amount", "last_updated")
    )
    GOLD_LOAN_SUMMARY_SCHEMA.validate(summary)
    lake_io.append(GOLD_LOAN_SUMMARY, summary)
    return summary.height


def build_loan_ops() -> int:
    """Aggregated by channel and loan_type. Idempotent, same compute-once
    pattern as build_loan_summary. Does not touch gold_loan_summary (frozen,
    Rules R7) - a separate table."""
    if lake_io.table_exists(GOLD_LOAN_OPS):
        return 0

    silver = lake_io.read(SILVER_LOANS)
    ops = (
        silver.group_by(["channel", "loan_type"])
        .agg(
            pl.len().cast(pl.Int64).alias("loan_count"),
            pl.col("loan_amount").sum().alias("total_amount"),
            pl.col("loan_amount").mean().alias("avg_amount"),
        )
        .select("channel", "loan_type", "loan_count", "total_amount", "avg_amount")
    )
    GOLD_LOAN_OPS_SCHEMA.validate(ops)
    lake_io.append(GOLD_LOAN_OPS, ops)
    return ops.height


def build_channel_by_state() -> int:
    """Aggregated by state and channel. Idempotent, same compute-once pattern
    as build_loan_summary/build_loan_ops. Does not touch any existing Gold
    table (Rules R7) - a separate table."""
    if lake_io.table_exists(GOLD_CHANNEL_BY_STATE):
        return 0

    silver = lake_io.read(SILVER_LOANS)
    by_state_channel = (
        silver.group_by(["state", "channel"])
        .agg(
            pl.len().cast(pl.Int64).alias("loan_count"),
            pl.col("loan_amount").sum().alias("total_amount"),
        )
        .select("state", "channel", "loan_count", "total_amount")
    )
    GOLD_CHANNEL_BY_STATE_SCHEMA.validate(by_state_channel)
    lake_io.append(GOLD_CHANNEL_BY_STATE, by_state_channel)
    return by_state_channel.height


def init_call_insights() -> None:
    """Initialised empty with the agreed schema; the AI service appends rows
    to this table via lake_io in Phase 6. Idempotent: no-op if it already
    exists."""
    if lake_io.table_exists(GOLD_CALL_INSIGHTS):
        return

    empty = pl.DataFrame(schema={
        "call_id": pl.Utf8,
        "transcript_masked": pl.Utf8,
        "sentiment_score": pl.Float64,
        "hardship_flag": pl.Boolean,
        "complaint_flag": pl.Boolean,
        "enquiry_type": pl.Utf8,
        "processed_at": pl.Datetime("us", "UTC"),
    })
    GOLD_CALL_INSIGHTS_SCHEMA.validate(empty)
    lake_io.append(GOLD_CALL_INSIGHTS, empty)


def main() -> None:
    rows = build_loan_summary()
    init_call_insights()
    build_loan_ops()
    build_channel_by_state()
    # Console line unchanged (Design.md's rehearsed demo format) - the new
    # Gold tables aren't part of the scripted demo moments.
    print(f"GOLD    summary: {rows} rows            call_insights: ready")


if __name__ == "__main__":
    main()
