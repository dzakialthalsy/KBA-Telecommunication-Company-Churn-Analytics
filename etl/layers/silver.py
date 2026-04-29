"""
Silver Layer — Cleaned & Conformed Data
Task: DE-08 | Owner: Dhea Akmalia Fibri

Prinsip Medallion Silver:
- Baca dari Bronze, JANGAN sentuh sumber asli
- Cleaning sesuai notebook silver_processing.ipynb (Google Colab)
- JANGAN scaling — scaling hanya di notebook ML (Fairuz)
- Disimpan sebagai tabel DuckDB: silver_telecom_cleaned
"""

import duckdb
import pandas as pd
from pathlib import Path
from loguru import logger
from sklearn.impute import SimpleImputer

BRONZE_TABLE = "bronze_telecom_raw"
SILVER_TABLE = "silver_telecom_cleaned"

# ── Kolom yang di-drop (missing > 20% atau tidak relevan bisnis) ──────────
COLUMNS_TO_DROP = [
    "numbcars", "ownrent", "dwlltype", "dwllsize", "HHstatin",
    "lor", "adults", "income", "infobase", "hnd_webcap", "prizm_social_one",
]

# ── Kolom metadata Bronze — tidak dibawa ke Silver ────────────────────────
BRONZE_META_COLS = ["_ingested_at", "_source_file", "_row_id"]

# ── Kolom imputasi median (Kelompok A) ───────────────────────────────────
IMPUTE_MEDIAN_A = [
    "rev_Mean", "mou_Mean", "totmrc_Mean", "da_Mean", "ovrmou_Mean",
    "ovrrev_Mean", "vceovr_Mean", "datovr_Mean", "roam_Mean",
]

# ── Kolom imputasi median (Kelompok B) ───────────────────────────────────
IMPUTE_MEDIAN_B = ["change_mou", "change_rev"]

# ── Kolom imputasi median (Kelompok C) ───────────────────────────────────
IMPUTE_MEDIAN_C = ["avg6mou", "avg6qty", "avg6rev"]

# ── Kolom imputasi median (Kelompok D) ───────────────────────────────────
IMPUTE_MEDIAN_D = ["hnd_price"]

# ── Kolom imputasi "Unknown" (kategorik) ─────────────────────────────────
IMPUTE_UNKNOWN_CAT = [
    "truck", "rv", "forgntvl", "ethnic",
    "kid0_2", "kid3_5", "kid6_10", "kid11_15", "kid16_17",
    "creditcd", "marital", "dualband", "refurb_new", "area",
]

# ── Kolom imputasi median (numerik kecil) ────────────────────────────────
IMPUTE_MEDIAN_NUM = ["phones", "models", "eqpdays"]

# ── Kolom dikecualikan dari outlier capping ──────────────────────────────
EXCLUDE_FROM_CAPPING = [
    "churn", "Customer_ID", "creditcd", "asl_flag", "new_cell",
    "months", "uniqsubs", "actvsubs", "phones", "models", "totcalls",
]


def load_to_silver(duckdb_path: Path) -> int:
    """
    Baca Bronze layer, jalankan cleaning pipeline, simpan ke Silver.
    Return: jumlah baris Silver.
    """
    logger.info("[SILVER] Membaca Bronze layer ...")
    con = duckdb.connect(str(duckdb_path))
    df = con.execute(f"SELECT * FROM {BRONZE_TABLE}").df()
    logger.info(f"[SILVER] {len(df):,} baris dari Bronze")

    # ── STEP 1: Hapus kolom metadata Bronze ──────────────────────────────
    df = df.drop(columns=[c for c in BRONZE_META_COLS if c in df.columns])
    logger.info("[SILVER] Step 1: Metadata Bronze dihapus")

    # ── STEP 2: Drop kolom tidak relevan ─────────────────────────────────
    cols_exist = [c for c in COLUMNS_TO_DROP if c in df.columns]
    df = df.drop(columns=cols_exist, errors="ignore")
    logger.info(f"[SILVER] Step 2: {len(cols_exist)} kolom di-drop "
                f"(missing >20% / tidak relevan)")

    # ── STEP 3: Imputasi missing values ──────────────────────────────────
    # Kelompok A — median
    cols_a = [c for c in IMPUTE_MEDIAN_A if c in df.columns]
    if cols_a:
        imp_a = SimpleImputer(strategy="median")
        df[cols_a] = imp_a.fit_transform(df[cols_a])

    # Kelompok B — median (change_mou, change_rev)
    cols_b = [c for c in IMPUTE_MEDIAN_B if c in df.columns]
    if cols_b:
        imp_b = SimpleImputer(strategy="median")
        df[cols_b] = imp_b.fit_transform(df[cols_b])

    # Kelompok C — median (avg6mou, avg6qty, avg6rev)
    cols_c = [c for c in IMPUTE_MEDIAN_C if c in df.columns]
    if cols_c:
        imp_c = SimpleImputer(strategy="median")
        df[cols_c] = imp_c.fit_transform(df[cols_c])

    # Kelompok D — median (hnd_price)
    cols_d = [c for c in IMPUTE_MEDIAN_D if c in df.columns]
    if cols_d:
        imp_d = SimpleImputer(strategy="median")
        df[cols_d] = imp_d.fit_transform(df[cols_d])

    # Kelompok E — kategorik → "Unknown"
    for col in IMPUTE_UNKNOWN_CAT:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")

    # Kelompok F — numerik kecil → median
    for col in IMPUTE_MEDIAN_NUM:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())

    total_null = df.isnull().sum().sum()
    logger.info(f"[SILVER] Step 3: Imputasi selesai — sisa null: {total_null}")

    # ── STEP 4: Drop duplicate rows ───────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    logger.info(f"[SILVER] Step 4: {dropped} duplicate rows dihapus")

    # ── STEP 5: Fix tipe data ─────────────────────────────────────────────
    if "churn" in df.columns:
        df["churn"] = pd.to_numeric(df["churn"], errors="coerce").fillna(0).astype(int)
    for col in ["avgrev", "change_rev", "custcare_Mean", "drop_vce_Mean", "hnd_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    logger.info("[SILVER] Step 5: Tipe data dikoreksi")

    # ── STEP 6: Outlier Capping (IQR Winsorizing) ─────────────────────────
    numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns.tolist()
    cols_to_cap = [c for c in numeric_cols if c not in EXCLUDE_FROM_CAPPING]

    capped_count = {}
    for col in cols_to_cap:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        n_outliers = ((df[col] < lower) | (df[col] > upper)).sum()
        if n_outliers > 0:
            df[col] = df[col].clip(lower=lower, upper=upper)
            capped_count[col] = n_outliers

    logger.info(
        f"[SILVER] Step 6: Outlier capping — {len(capped_count)} kolom di-cap"
    )

    # ── STEP 7: Feature Engineering (fe_ columns) ─────────────────────────
    if "custcare_Mean" in df.columns:
        threshold_cc = df["custcare_Mean"].mean() * 2
        df["fe_high_care_call"] = (df["custcare_Mean"] > threshold_cc).astype(int)

    if "change_rev" in df.columns:
        df["fe_revenue_drop"] = (df["change_rev"] < 0).astype(int)

    if "avgrev" in df.columns:
        q1_rev = df["avgrev"].quantile(0.25)
        df["fe_low_usage"] = (df["avgrev"] < q1_rev).astype(int)

    if "drop_vce_Mean" in df.columns:
        median_drop = df["drop_vce_Mean"].median()
        df["fe_drop_call_flag"] = (df["drop_vce_Mean"] > median_drop).astype(int)

    risk_flags = [
        c for c in [
            "fe_high_care_call", "fe_revenue_drop",
            "fe_low_usage", "fe_drop_call_flag",
        ] if c in df.columns
    ]
    if risk_flags:
        df["fe_churn_risk_rule"] = (
            df[risk_flags].sum(axis=1) / len(risk_flags)
        )

    logger.info(f"[SILVER] Step 7: Feature engineering — {len(risk_flags) + 1} kolom fe_ dibuat")

    # ── STEP 8: Validasi akhir ────────────────────────────────────────────
    final_null = df.isnull().sum().sum()
    if final_null > 0:
        logger.warning(f"[SILVER] ⚠ Masih ada {final_null} null setelah cleaning!")
    else:
        logger.info("[SILVER] Step 8: Validasi — 0 null ✓")

    logger.info(f"[SILVER] Shape akhir: {df.shape[0]:,} baris × {df.shape[1]} kolom")

    # ── STEP 9: Simpan ke Silver DuckDB ──────────────────────────────────
    con.execute(f"DROP TABLE IF EXISTS {SILVER_TABLE}")
    con.execute(f"CREATE TABLE {SILVER_TABLE} AS SELECT * FROM df")
    loaded = con.execute(f"SELECT COUNT(*) FROM {SILVER_TABLE}").fetchone()[0]
    con.close()

    logger.success(f"[SILVER] {loaded:,} baris → tabel '{SILVER_TABLE}' ✓")
    return loaded
