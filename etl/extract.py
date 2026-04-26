"""ETL Extract Layer — Task DE-07 | Owner: Dhea Akmalia Fibri."""

import pandas as pd
from pathlib import Path
from loguru import logger

REQUIRED_COLUMNS = [
    "churn",
    "avgrev",
    "change_rev",
    "custcare_Mean",
    "drop_vce_Mean",
]


def run_extract(raw_path: Path) -> pd.DataFrame:
    """Ekstrak CSV ke staging DataFrame dengan validasi schema awal."""
    logger.debug(f"Membaca: {raw_path}")
    df = pd.read_csv(raw_path, low_memory=False)
    logger.debug(f"Shape awal: {df.shape}")
    _validate_schema(df)
    df = _cast_types(df)
    staging_path = Path("data/staging/telecom_staging.csv")
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(staging_path, index=False)
    logger.debug(f"Staging disimpan: {staging_path}")
    return df


def _validate_schema(df: pd.DataFrame):
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing}")
    logger.debug("Schema validation: OK")


def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
    # TODO (DE-07): implementasi type casting lengkap
    return df
