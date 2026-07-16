"""Sole writer to the lake. All other modules must go through this file (Rules R4)."""
from pathlib import Path

import polars as pl
from deltalake import write_deltalake


def append(table_path: str | Path, dataframe: pl.DataFrame) -> None:
    """One atomic Delta append. Never called with a held-open write (Rules R4).

    Writes via to_arrow(compat_level=oldest) + write_deltalake directly,
    bypassing df.write_delta(), which always uses polars' newest Arrow
    export and has no compat_level knob of its own. polars' default export
    uses newer physical types (e.g. Utf8View) that older Parquet readers -
    including Power BI Desktop's bundled reader - fail to parse ("Parquet
    magic bytes not found in footer", a misleading error for an unrecognized
    embedded Arrow schema type). This changes only the on-disk physical
    encoding, never the data itself.
    """
    table = dataframe.to_arrow(compat_level=pl.CompatLevel.oldest())
    write_deltalake(str(table_path), table, mode="append")


def read(table_path: str | Path) -> pl.DataFrame:
    if not table_exists(table_path):
        return pl.DataFrame()
    return pl.read_delta(str(table_path))


def table_exists(table_path: str | Path) -> bool:
    return (Path(table_path) / "_delta_log").exists()
