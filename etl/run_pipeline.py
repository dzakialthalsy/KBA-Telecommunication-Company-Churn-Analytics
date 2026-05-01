"""
ETL Pipeline — Medallion Architecture
Telco Churn Analytics | Kelompok 4

Alur:
  CSV (sumber)
    → Bronze Layer  (raw ingestion, metadata only)
    → Silver Layer  (cleaned, conformed, feature engineering)
    → Gold Layer    (business aggregates, mart siap dashboard)
"""

import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

RAW_PATH = Path(os.getenv("RAW_DATA_PATH", "data/raw/telecom_customer.csv"))
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", "data/gold/telco_warehouse.duckdb"))
ML_SCORES_PATH = Path(os.getenv("ML_SCORES_PATH", "ml/models/churn_scores.csv"))
LOG_LEVEL = os.getenv("ETL_LOG_LEVEL", "INFO")

logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
)


def main():
    logger.info("=" * 60)
    logger.info("  Telco Churn Analytics — Medallion ETL Pipeline")
    logger.info("  Bronze → Silver → Gold")
    logger.info("=" * 60)

    if not RAW_PATH.exists():
        logger.error(f"Dataset tidak ditemukan: {RAW_PATH}")
        logger.info("Download dari: https://www.kaggle.com/datasets/abhinav89/telecom-customer")
        logger.info(f"Simpan ke: {RAW_PATH}")
        sys.exit(1)

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    from etl.layers.bronze import load_to_bronze
    from etl.layers.silver import load_to_silver
    from etl.layers.gold import load_to_gold

    # ── BRONZE ────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("── LAYER 1: BRONZE (Raw Ingestion) ──────────────────────")
    bronze_count = load_to_bronze(RAW_PATH, DUCKDB_PATH)

    # ── SILVER ────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("── LAYER 2: SILVER (Clean & Conform) ───────────────────")
    silver_count = load_to_silver(DUCKDB_PATH)

    # ── GOLD ──────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("── LAYER 3: GOLD (Business Aggregates) ─────────────────")
    ml_path = ML_SCORES_PATH if ML_SCORES_PATH.exists() else None
    if not ml_path:
        logger.info("  ML scores belum ada → Gold pakai rule-based fallback")
    gold_results = load_to_gold(DUCKDB_PATH, ml_path)

    # ── SUMMARY ───────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.success("  PIPELINE SELESAI — Medallion Summary:")
    logger.info(f"  🥉 Bronze : {bronze_count:>10,} baris  (bronze.telecom_raw)")
    logger.info(f"  🥈 Silver : {silver_count:>10,} baris  (silver.telecom_cleaned)")
    for tbl, cnt in gold_results.items():
        logger.info(f"  🥇 Gold   : {cnt:>10,} baris  ({tbl})")
    logger.info(f"  📦 DuckDB : {DUCKDB_PATH}")

    # ── Buat copy read-only untuk Metabase ───────────────────────────────────
    import shutil
    readonly_path = DUCKDB_PATH.parent / "telco_warehouse_readonly.duckdb"
    shutil.copy2(str(DUCKDB_PATH), str(readonly_path))
    logger.info(f"  📋 Read-only copy → {readonly_path}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
