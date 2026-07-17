"""Bronze -> Silver -> Gold for the AI service's live /process-call path,
mirroring pipeline/bronze.py, silver.py, gold.py's structure for the batch
transcripts. A separate table set (the "_live" suffix) - this never touches
bronze_calls/silver_calls, which stay reserved for the batch pipeline's 3
official transcripts.
"""
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ai_service.nlp_flags import classify_enquiry_type, complaint_flag, hardship_flag, mask_names, sentiment_score
from pipeline import lake_io

REPO_ROOT = Path(__file__).resolve().parent.parent
BRONZE_CALLS_LIVE = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_calls_live"
SILVER_CALLS_LIVE = REPO_ROOT / "data" / "lake" / "silver" / "silver_calls_live"
GOLD_CALL_INSIGHTS = REPO_ROOT / "data" / "lake" / "gold" / "gold_call_insights"


def land_bronze(call_id: str, raw_transcript: str, source: str) -> None:
    """Raw, unmasked, as landed - no cleaning, no masking (same Bronze
    principle as pipeline/bronze.py; raw names may exist only in Bronze,
    Rules R3)."""
    row = pl.DataFrame([{
        "call_id": call_id,
        "raw_transcript": raw_transcript,
        "source": source,
        "received_at": datetime.now(timezone.utc),
    }])
    lake_io.append(BRONZE_CALLS_LIVE, row)


def process_silver(call_id: str, raw_transcript: str) -> dict:
    """Masking + NLP flags (same Silver principle as pipeline/silver.py).
    Returns the row as a dict so publish_gold can reuse it directly."""
    row = {
        "call_id": call_id,
        "masked_transcript": mask_names(raw_transcript),
        "sentiment_score": sentiment_score(raw_transcript),
        "hardship_flag": hardship_flag(raw_transcript),
        "complaint_flag": complaint_flag(raw_transcript),
        # Existing hardship_flag/complaint_flag columns kept unchanged for
        # backward compatibility - enquiry_type is additive, not a replacement.
        "enquiry_type": classify_enquiry_type(raw_transcript),
        "processed_at": datetime.now(timezone.utc),
    }
    lake_io.append(SILVER_CALLS_LIVE, pl.DataFrame([row]))
    return row


def publish_gold(silver_row: dict) -> None:
    """gold_call_insights' schema keeps hardship_flag/complaint_flag
    unchanged and adds enquiry_type (human-authorized change to the Phase 4
    frozen contract, Rules R7 - see pipeline/gold.py's matching schema
    update, required so the batch-created empty table and this live writer
    agree on columns). Only the write source changed at Phase 8 - from a
    direct AI-service write to being populated from silver_calls_live."""
    gold_row = pl.DataFrame([{
        "call_id": silver_row["call_id"],
        "transcript_masked": silver_row["masked_transcript"],
        "sentiment_score": silver_row["sentiment_score"],
        "hardship_flag": silver_row["hardship_flag"],
        "complaint_flag": silver_row["complaint_flag"],
        "enquiry_type": silver_row["enquiry_type"],
        "processed_at": silver_row["processed_at"],
    }])
    lake_io.append(GOLD_CALL_INSIGHTS, gold_row)
