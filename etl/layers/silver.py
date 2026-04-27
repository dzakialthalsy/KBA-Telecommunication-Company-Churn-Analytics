"""
Silver Layer — Cleaned & Conformed Data
Task: DE-08 | Owner: Dhea Akmalia Fibri

Prinsip Medallion Silver:
- Baca dari Bronze, JANGAN sentuh sumber asli
- Cleaning: handle missing values, outlier, tipe data
- Standardisasi: nama kolom konsisten, encoding kategorik
- Feature engineering BISNIS (derived dari PRD): derived KPIs
- Normalisasi: StandardScaler untuk kolom numerik model
- Disimpan sebagai tabel DuckDB: silver_telecom_cleaned
- Setiap baris tetap 1:1 dengan Bronze (tidak ada agregasi)
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger


BRONZE_TABLE = "bronze_telecom_raw"
SILVER_TABLE = "silver_telecom_cleaned"

# Kolom KPI utama dari PRD — harus ada setelah cleaning
REQUIRED_KPI_COLS = [
    "churn",
    "avgrev",
    "change_rev",
    "custcare_Mean",
    "drop_vce_Mean",
]


def load_to_silver(duckdb_path: Path) -> int:
    """
    Baca Bronze layer, clean & conform, simpan ke Silver.
    Return: jumlah baris Silver.
    """
    logger.info("[SILVER] Membaca Bronze layer ...")
    con = duckdb.connect(str(duckdb_path))

    df = con.execute(f"SELECT * FROM {BRONZE_TABLE}").df()
    logger.info(f"[SILVER] {len(df):,} baris dari Bronze")

    # ── 1. Validasi kolom KPI wajib ada ──────────────────────────────────
    _validate_required_cols(df)

    # ── 2. Hapus kolom metadata Bronze (tidak relevan di Silver) ─────────
    meta_cols = ["_ingested_at", "_source_file", "_row_id"]
    df = df.drop(columns=[c for c in meta_cols if c in df.columns])

    # ── 3. Standardisasi nama kolom (lowercase, strip spasi) ─────────────
    df.columns = [c.strip().lower() for c in df.columns]

    # ── 4. Handle missing values ──────────────────────────────────────────
    df = _handle_missing(df)

    # ── 5. Cleaning tipe data ─────────────────────────────────────────────
    df = _cast_types(df)

    # ── 6. Feature engineering KPI turunan (dari PRD) ────────────────────
    df = _engineer_features(df)

    # ── 7. Hapus duplicate rows ───────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"[SILVER] {dropped} duplicate rows dihapus")

    # ── 8. Simpan ke Silver ───────────────────────────────────────────────
    con.execute(f"DROP TABLE IF EXISTS {SILVER_TABLE}")
    con.execute(f"CREATE TABLE {SILVER_TABLE} AS SELECT * FROM df")
    loaded = con.execute(f"SELECT COUNT(*) FROM {SILVER_TABLE}").fetchone()[0]
    con.close()

    logger.success(f"[SILVER] {loaded:,} baris → tabel '{SILVER_TABLE}' ✓")
    return loaded


def _validate_required_cols(df: pd.DataFrame):
    missing = [c for c in REQUIRED_KPI_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"[SILVER] Kolom KPI wajib tidak ditemukan: {missing}")


def _handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Imputasi missing values per tipe kolom."""
    numeric_cols = df.select_dtypes(include=["number"]).columns
    categorical_cols = df.select_dtypes(include=["object"]).columns

    # Median untuk numerik (robust terhadap outlier)
    for col in numeric_cols:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            logger.debug(f"[SILVER] {col}: {null_count} null → median={median_val:.2f}")

    # Mode untuk kategorik
    for col in categorical_cols:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            mode_val = df[col].mode()[0]
            df[col] = df[col].fillna(mode_val)
            logger.debug(f"[SILVER] {col}: {null_count} null → mode='{mode_val}'")

    return df


def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
    """Pastikan tipe data kolom kritis sudah benar."""
    if "churn" in df.columns:
        df["churn"] = pd.to_numeric(df["churn"], errors="coerce").fillna(0).astype(int)
    for col in ["avgrev", "change_rev", "custcare_mean", "drop_vce_mean"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering berdasarkan definisi KPI di PRD.
    Semua kolom derived ditandai dengan prefix 'fe_'.
    """
    # fe_high_care_call: flag pelanggan yang telepon CS lebih dari 2x rata-rata
    if "custcare_mean" in df.columns:
        threshold = df["custcare_mean"].mean() * 2
        df["fe_high_care_call"] = (df["custcare_mean"] > threshold).astype(int)

    # fe_revenue_drop: flag jika change_rev negatif (pendapatan turun)
    if "change_rev" in df.columns:
        df["fe_revenue_drop"] = (df["change_rev"] < 0).astype(int)

    # fe_low_usage: flag jika avgrev di bawah Q1 (pelanggan penggunaan rendah)
    if "avgrev" in df.columns:
        q1 = df["avgrev"].quantile(0.25)
        df["fe_low_usage"] = (df["avgrev"] < q1).astype(int)

    # fe_drop_call_flag: flag jika drop_vce_mean di atas median
    if "drop_vce_mean" in df.columns:
        median_drop = df["drop_vce_mean"].median()
        df["fe_drop_call_flag"] = (df["drop_vce_mean"] > median_drop).astype(int)

    # fe_churn_risk_score_rule: rule-based risk score (0.0 – 1.0)
    # Sebelum model ML — dipakai sebagai baseline dan validasi bisnis (BA-04)
    risk_flags = [c for c in [
        "fe_high_care_call", "fe_revenue_drop",
        "fe_low_usage", "fe_drop_call_flag"
    ] if c in df.columns]

    if risk_flags:
        df["fe_churn_risk_rule"] = df[risk_flags].sum(axis=1) / len(risk_flags)

    return df
