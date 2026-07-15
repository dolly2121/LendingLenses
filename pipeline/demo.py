"""Sequences the live demo startup with readiness checks (Phases.md Phase 7).

This IS the rehearsed path (`make demo`). `docker compose up` is a packaging
proof point only, never run on stage (Rules R1, Architecture.md folder
structure notes).
"""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from pipeline import lake_io, run_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_LOAN_SUMMARY = REPO_ROOT / "data" / "lake" / "gold" / "gold_loan_summary"
GOLD_CALL_INSIGHTS = REPO_ROOT / "data" / "lake" / "gold" / "gold_call_insights"
HEALTH_URL = "http://127.0.0.1:8000/health"
HEALTH_TIMEOUT_S = 30


def _wait_for_health(timeout_s: int = HEALTH_TIMEOUT_S) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> None:
    run_pipeline.main()

    if not (lake_io.table_exists(GOLD_LOAN_SUMMARY) and lake_io.table_exists(GOLD_CALL_INSIGHTS)):
        print("DEMO    FAILED: Gold tables not found after pipeline run")
        sys.exit(1)

    dashboard = subprocess.Popen(["streamlit", "run", "dashboard/app.py"], cwd=REPO_ROOT)
    service = subprocess.Popen(["uvicorn", "ai_service.main:app"], cwd=REPO_ROOT)

    healthy = _wait_for_health()
    # No race conditions on stage: confirm both processes are still alive,
    # not just that the AI service answered once.
    if not healthy or dashboard.poll() is not None or service.poll() is not None:
        print("DEMO    FAILED: dashboard or AI service did not become ready in time")
        dashboard.terminate()
        service.terminate()
        sys.exit(1)

    print("DEMO    ready -> dashboard: http://localhost:8501   service: http://localhost:8000")


if __name__ == "__main__":
    main()
