"""
ETL — Transform Layer
Task: DE-08 | Owner: Dhea Akmalia Fibri

Tanggung jawab:
- Cleaning: missing values, outlier handling
- Feature engineering: derived KPI columns
- Segmentasi: High Value / At-Risk / Stable / Churned
- Churn risk flag (rule-based, sebelum model ML)
"""

import pandas as pd
import os
from loguru import logger

HIGH_RISK_THRESH   = float(os.getenv("CHURN_HIGH_RISK_THRESHOLD",   0.7))
MEDIUM_RISK_THRESH = float(os.getenv("CHURN_MEDIUM_RISK_THRESHOLD",  0.4))


def run_transform(df: pd.DataFrame) -> pd.DataFrame:
    """Transformasi staging DataFrame ke mart-ready DataFrame."""
    logger.debug("Memulai transformasi ...")
    df = _handle_missing(df)
    df = _engineer_features(df)
    df = _add_segment(df)
    logger.debug(f"Transformasi selesai. Shape: {df.shape}")
    return df


def _handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    # TODO (DE-08): imputation strategy per kolom
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    return df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    # TODO (DE-08): tambah derived features
    # Contoh: revenue_drop_flag, high_care_call_flag
    return df


def _add_segment(df: pd.DataFrame) -> pd.DataFrame:
    # TODO (DE-08): implementasi segmentasi rule-based
    # High Value / At-Risk / Stable / Churned
    return df
