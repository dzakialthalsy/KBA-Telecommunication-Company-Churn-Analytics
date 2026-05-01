"""ETL Load Layer — Task DE-09 | Owner: Dhea Akmalia Fibri."""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger


def run_load(df: pd.DataFrame, duckdb_path: Path):
    """Load DataFrame ke DuckDB data warehouse."""
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute("DROP TABLE IF EXISTS mart_churn_risk")
    con.execute("DROP TABLE IF EXISTS etl_run_log")
    logger.debug("Membuat tabel mart_churn_risk ...")
    con.execute("DROP TABLE IF EXISTS gold.mart_churn_risk")
    con.execute("CREATE TABLE gold.mart_churn_risk AS SELECT * FROM df")
    con.execute("""
        CREATE TABLE IF NOT EXISTS gold.etl_run_log (
            run_at      TIMESTAMP,
            row_count   INTEGER,
            status      VARCHAR
        )
    """)
    con.execute(
        "INSERT INTO gold.etl_run_log VALUES (?, ?, ?)",
        [datetime.now(), len(df), "success"]
    )
    con.close()
    logger.debug("Load ke DuckDB selesai.")
