"""ETL Pipeline entry point — Telco Churn Analytics, Kelompok 4."""

import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

RAW_PATH = Path(os.getenv("RAW_DATA_PATH", "data/raw/telecom_customer.csv"))
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", "data/mart/telco_warehouse.duckdb"))
LOG_LEVEL = os.getenv("ETL_LOG_LEVEL", "INFO")

logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL,
           format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def main():
    logger.info("=" * 55)
    logger.info("  Telco Churn Analytics — ETL Pipeline")
    logger.info("=" * 55)

    if not RAW_PATH.exists():
        logger.error(f"Dataset tidak ditemukan: {RAW_PATH}")
        logger.info("Unduh dari: https://www.kaggle.com/datasets/abhinav89/telecom-customer")
        sys.exit(1)

    try:
        from etl.extract import run_extract
        from etl.transform import run_transform
        from etl.load import run_load
    except ImportError as e:
        logger.warning(f"Module belum tersedia: {e}")
        return

    logger.info("[1/3] EXTRACT ...")
    staging_df = run_extract(RAW_PATH)
    logger.success(f"      {len(staging_df):,} baris diekstrak")

    logger.info("[2/3] TRANSFORM ...")
    mart_df = run_transform(staging_df)
    logger.success(f"      {len(mart_df):,} baris siap dimuat")

    logger.info("[3/3] LOAD → DuckDB ...")
    run_load(mart_df, DUCKDB_PATH)
    logger.success(f"      Data mart: {DUCKDB_PATH}")

    logger.info("=" * 55)
    logger.success("  Pipeline selesai.")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
