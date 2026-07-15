"""Bronze layer: land raw data unmodified, as landed. No cleaning, no masking."""
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from pipeline import lake_io

REPO_ROOT = Path(__file__).resolve().parent.parent
LANDING_DIR = REPO_ROOT / "data" / "landing"
TRANSCRIPTS_DIR = LANDING_DIR / "transcripts"
BRONZE_LOANS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_loans"
BRONZE_CALLS = REPO_ROOT / "data" / "lake" / "bronze" / "bronze_calls"


def _already_landed(table_path: Path, source_file: str) -> bool:
    if not lake_io.table_exists(table_path):
        return False
    return source_file in lake_io.read(table_path)["source_file"].to_list()


def land_loans() -> int:
    source_file = "loans_raw.csv"
    if _already_landed(BRONZE_LOANS, source_file):
        return 0
    df = pl.read_csv(LANDING_DIR / source_file).with_columns(
        pl.lit(source_file).alias("source_file"),
        pl.lit(datetime.now(timezone.utc)).alias("ingest_timestamp"),
    )
    lake_io.append(BRONZE_LOANS, df)
    return df.height


def land_calls() -> int:
    rows = []
    for path in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
        if _already_landed(BRONZE_CALLS, path.name):
            continue
        rows.append({
            "call_id": path.stem,
            "transcript_text": path.read_text(encoding="utf-8"),
            "source_file": path.name,
            "ingest_timestamp": datetime.now(timezone.utc),
        })
    if not rows:
        return 0
    df = pl.DataFrame(rows)
    lake_io.append(BRONZE_CALLS, df)
    return df.height


def main() -> None:
    loans_landed = land_loans()
    calls_landed = land_calls()
    print(f"BRONZE  loans:  {loans_landed} landed          calls: {calls_landed} landed")


if __name__ == "__main__":
    main()
