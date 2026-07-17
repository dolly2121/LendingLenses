"""FastAPI AI service: the AI face of the Gold layer (Phases.md Phase 6).

Only ever fed the 3 official transcripts from Phase 1, including live in
front of an audience. Never a name typed live or audience-suggested
(Rules R3a) - this endpoint's masking is keyword-based, not general NER,
and is only proven to work against those 3 transcripts.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ai_service import call_pipeline

app = FastAPI(title="LendingLens AI Service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/record.html")
def record_page() -> FileResponse:
    # Dev/test tool only (Phase 8, browser-mic whisper.js path), not a demo
    # moment. Same-origin static serve so its fetch() to /process-call needs
    # no CORS config. Does not touch process_call's own logic.
    return FileResponse(Path(__file__).parent / "record.html")


@app.post("/process-call")
async def process_call(file: UploadFile) -> dict:
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="only a .txt transcript is accepted")

    raw = (await file.read()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="transcript is empty")

    call_id = Path(file.filename).stem

    try:
        call_pipeline.land_bronze(call_id, raw, file.filename)
        silver_row = call_pipeline.process_silver(call_id, raw)
        call_pipeline.publish_gold(silver_row)
    except Exception as exc:
        # Never a stack trace, one clean 5xx with a short message (Rules R6).
        raise HTTPException(status_code=500, detail="failed to record call insight") from exc

    return {
        "call_id": call_id,
        "hardship_flag": bool(silver_row["hardship_flag"]),
        "complaint_flag": bool(silver_row["complaint_flag"]),
        "enquiry_type": silver_row["enquiry_type"],
    }
