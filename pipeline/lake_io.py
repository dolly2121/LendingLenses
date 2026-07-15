"""Sole writer to the lake. All other modules must go through this file (Rules R4)."""
from pathlib import Path

import polars as pl


def append(table_path: str | Path, dataframe: pl.DataFrame) -> None:
    """One atomic Delta append. Never called with a held-open write (Rules R4)."""
    dataframe.write_delta(str(table_path), mode="append")


def read(table_path: str | Path) -> pl.DataFrame:
    if not table_exists(table_path):
        return pl.DataFrame()
    return pl.read_delta(str(table_path))


def table_exists(table_path: str | Path) -> bool:
    return (Path(table_path) / "_delta_log").exists()
