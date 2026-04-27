"""
Bronze Layer — Raw Ingestion
Task: DE-07 | Owner: Dhea Akmalia Fibri

Prinsip Medallion Bronze:
- Data masuk APA ADANYA dari sumber (CSV Kaggle)
- TIDAK ada transformasi bisnis, TIDAK ada filtering
- Hanya tambah metadata: ingested_at, source_file, row_id
- Append-only: data lama tidak pernah dihapus
- Disimpan sebagai tabel DuckDB: bronze.telecom_raw
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger


BRONZE_TABLE = "bronze_telecom_raw"


def load_to_bronze(raw_path: Path, duckdb_path: Path) -> int:
    """
    Baca CSV dan load ke Bronze layer di DuckDB.
    Tambah kolom metadata: _ingested_at, _source_file, _row_id.
    Return: jumlah baris yang di-load.
    """
    logger.info(f"[BRONZE] Membaca sumber: {raw_path.name}")

    if not raw_path.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {raw_path}")

    df = pd.read_csv(raw_path, low_memory=False)

    # ── Tambah metadata kolom (satu-satunya transformasi di Bronze) ──────
    df["_ingested_at"] = datetime.now().isoformat()
    df["_source_file"] = raw_path.name
    df["_row_id"] = range(1, len(df) + 1)

    row_count = len(df)
    logger.info(f"[BRONZE] {row_count:,} baris dibaca dari sumber")

    # ── Load ke DuckDB ────────────────────────────────────────────────────
    con = duckdb.connect(str(duckdb_path))

    # Drop dan recreate (full refresh — cocok untuk dataset statis Kaggle)
    con.execute(f"DROP TABLE IF EXISTS {BRONZE_TABLE}")
    con.execute(f"CREATE TABLE {BRONZE_TABLE} AS SELECT * FROM df")

    # Validasi sederhana: cek row count konsisten
    loaded = con.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}").fetchone()[0]
    con.close()

    if loaded != row_count:
        raise ValueError(f"[BRONZE] Row count mismatch: expected {row_count}, got {loaded}")

    logger.success(f"[BRONZE] {loaded:,} baris → tabel '{BRONZE_TABLE}' ✓")
    return loaded
