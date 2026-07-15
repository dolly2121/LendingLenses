"""FastAPI AI service: the AI face of the Gold layer (Phases.md Phase 6).

Only ever fed the 3 official transcripts from Phase 1, including live in
front of an audience. Never a name typed live or audience-suggested
(Rules R3a) - this endpoint's masking is keyword-based, not general NER,
and is only proven to work against those 3 transcripts.
"""
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from fastapi import FastAPI, HTTPException, UploadFile

from ai_service.nlp_flags import complaint_flag, hardship_flag, mask_names, sentiment_score
from pipeline import lake_io

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_CALL_INSIGHTS = REPO_ROOT / "data" / "lake" / "gold" / "gold_call_insights"

app = FastAPI(title="LendingLens AI Service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/process-call")
async def process_call(file: UploadFile) -> dict:
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="only a .txt transcript is accepted")

    raw = (await file.read()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="transcript is empty")

    call_id = Path(file.filename).stem
    row = pl.DataFrame([{
        "call_id": call_id,
        "transcript_masked": mask_names(raw),
        "sentiment_score": sentiment_score(raw),
        "hardship_flag": hardship_flag(raw),
        "complaint_flag": complaint_flag(raw),
        "processed_at": datetime.now(timezone.utc),
    }])

    try:
        lake_io.append(GOLD_CALL_INSIGHTS, row)
    except Exception as exc:
        # Never a stack trace, one clean 5xx with a short message (Rules R6).
        raise HTTPException(status_code=500, detail="failed to record call insight") from exc

    return {
        "call_id": call_id,
        "hardship_flag": bool(row["hardship_flag"][0]),
        "complaint_flag": bool(row["complaint_flag"][0]),
    }
