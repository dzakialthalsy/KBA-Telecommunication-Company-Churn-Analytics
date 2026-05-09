"""
Gold Layer — Business-Ready Aggregates & Mart
Task: DE-09 | Owner: Dhea Akmalia Fibri

Prinsip Medallion Gold:
- Baca dari Silver, JANGAN baca Bronze atau sumber langsung
- Diagregasi sesuai kebutuhan bisnis & dashboard
- Dikonsumsi langsung oleh Metabase (schema gold saja yang di-expose)
- Tabel:
    gold.customer_segments  → segmentasi pelanggan
    gold.churn_risk         → skor risiko per pelanggan
    gold.churn_summary      → KPI agregat untuk Executive
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger

SILVER_TABLE = "silver.telecom_cleaned"
GOLD_SCHEMA = "gold"
GOLD_CUSTOMER_SEGMENTS = f"{GOLD_SCHEMA}.customer_segments"
GOLD_CHURN_RISK = f"{GOLD_SCHEMA}.churn_risk"
GOLD_CHURN_SUMMARY = f"{GOLD_SCHEMA}.churn_summary"
GOLD_CHURN_PREDICTION = f"{GOLD_SCHEMA}.churn_prediction"

# Nama kolom ID di dataset asli Kaggle adalah "Customer_ID" (kapital)
CUSTOMER_ID_COL = "Customer_ID"

# Threshold segmentasi — sesuai BA-05 & PM-06
HIGH_RISK_THRESHOLD = 0.7
MEDIUM_RISK_THRESHOLD = 0.4
HIGH_VALUE_AVGREV_PERCENTILE = 0.75


def load_to_gold(duckdb_path: Path, model_scores_path: Path = None) -> dict:
    """
    Build semua tabel Gold dari Silver.
    Jika model_scores_path tersedia, gabungkan ML score ke gold.churn_risk.
    Return: dict berisi row count tiap tabel Gold.
    """
    logger.info("[GOLD] Membaca Silver layer ...")
    con = duckdb.connect(str(duckdb_path))
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {GOLD_SCHEMA}")
    df = con.execute(f"SELECT * FROM {SILVER_TABLE}").df()
    logger.info(f"[GOLD] {len(df):,} baris dari Silver")

    results = {}

    # ── Tabel 1: gold.customer_segments ──────────────────────────────────
    df_seg = _build_customer_segments(df.copy())
    con.execute(f"DROP TABLE IF EXISTS {GOLD_CUSTOMER_SEGMENTS}")
    con.execute(f"CREATE TABLE {GOLD_CUSTOMER_SEGMENTS} AS SELECT * FROM df_seg")
    results[GOLD_CUSTOMER_SEGMENTS] = len(df_seg)
    logger.success(f"[GOLD] {GOLD_CUSTOMER_SEGMENTS}: {len(df_seg):,} baris ✓")

    # ── Tabel 2: gold.churn_risk ──────────────────────────────────────────
    df_risk = _build_churn_risk(df.copy(), model_scores_path)
    con.execute(f"DROP TABLE IF EXISTS {GOLD_CHURN_RISK}")
    con.execute(f"CREATE TABLE {GOLD_CHURN_RISK} AS SELECT * FROM df_risk")
    results[GOLD_CHURN_RISK] = len(df_risk)
    logger.success(f"[GOLD] {GOLD_CHURN_RISK}: {len(df_risk):,} baris ✓")

    # ── Tabel 3: gold.churn_summary ───────────────────────────────────────
    df_summary = _build_churn_summary(df_risk.copy())
    con.execute(f"DROP TABLE IF EXISTS {GOLD_CHURN_SUMMARY}")
    con.execute(f"CREATE TABLE {GOLD_CHURN_SUMMARY} AS SELECT * FROM df_summary")
    results[GOLD_CHURN_SUMMARY] = len(df_summary)
    logger.success(f"[GOLD] {GOLD_CHURN_SUMMARY}: {len(df_summary):,} baris ✓")

    # ── Tabel 4: gold.churn_prediction (NEW) ─────────────────────────────
    if model_scores_path and Path(model_scores_path).exists():
        df_pred = _build_churn_prediction(df.copy(), model_scores_path)
        con.execute(f"DROP TABLE IF EXISTS {GOLD_CHURN_PREDICTION}")
        con.execute(f"CREATE TABLE {GOLD_CHURN_PREDICTION} AS SELECT * FROM df_pred")
        results[GOLD_CHURN_PREDICTION] = len(df_pred)
        logger.success(f"[GOLD] {GOLD_CHURN_PREDICTION}: {len(df_pred):,} baris ✓")
    else:
        logger.info("[GOLD] churn_scores.csv belum ada → churn_prediction dilewati")

    con.close()
    return results


def _build_customer_segments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Segmentasi pelanggan berdasarkan ARPU dan rule-based risk score.
    """
    if "avgrev" in df.columns:
        hv_threshold = df["avgrev"].quantile(HIGH_VALUE_AVGREV_PERCENTILE)
    else:
        hv_threshold = 0

    risk_col = "fe_churn_risk_rule" if "fe_churn_risk_rule" in df.columns else None

    def assign_segment(row):
        if "churn" in row and row["churn"] == 1:
            return "Churned"
        if risk_col and row.get(risk_col, 0) >= HIGH_RISK_THRESHOLD:
            return "At-Risk"
        if risk_col and row.get(risk_col, 0) >= MEDIUM_RISK_THRESHOLD:
            return "Watch"
        if "avgrev" in row and row["avgrev"] >= hv_threshold:
            return "High Value"
        return "Stable"

    df["customer_segment"] = df.apply(assign_segment, axis=1)
    df["segment_updated_at"] = pd.Timestamp.now().isoformat()

    keep_cols = [c for c in [
        CUSTOMER_ID_COL,
        "churn", "avgrev", "change_rev",
        "custcare_Mean", "drop_vce_Mean",
        "fe_high_care_call", "fe_revenue_drop",
        "fe_low_usage", "fe_drop_call_flag", "fe_churn_risk_rule",
        "customer_segment", "segment_updated_at",
    ] if c in df.columns]

    return df[keep_cols].reset_index(drop=True)


def _build_churn_risk(df: pd.DataFrame, model_scores_path: Path = None) -> pd.DataFrame:
    """
    Tabel risiko churn per pelanggan.
    Jika ML scores tersedia → pakai ml_churn_score.
    Jika belum → pakai fe_churn_risk_rule sebagai fallback.
    """
    if model_scores_path and Path(model_scores_path).exists():
        logger.info("[GOLD] ML scores ditemukan → merge ke gold.churn_risk")
        ml_scores = pd.read_csv(model_scores_path)

        id_col_ml = None
        for candidate in ["Customer_ID", "customer_id", "CustomerID"]:
            if candidate in ml_scores.columns:
                id_col_ml = candidate
                break

        required_score_cols = ["ml_churn_score", "ml_churn_label"]
        missing = [c for c in required_score_cols if c not in ml_scores.columns]

        if missing or id_col_ml is None:
            logger.warning(
                f"[GOLD] ML scores format salah (missing: {missing}, id_col: {id_col_ml})"
                " → pakai rule-based fallback"
            )
        elif CUSTOMER_ID_COL in df.columns:
            ml_scores = ml_scores.rename(columns={id_col_ml: CUSTOMER_ID_COL})
            df = df.merge(
                ml_scores[[CUSTOMER_ID_COL] + required_score_cols],
                on=CUSTOMER_ID_COL,
                how="left",
            )
            logger.success("[GOLD] ML scores berhasil di-merge ✓")
    else:
        logger.info("[GOLD] ML scores belum ada → rule-based fallback")
        df["ml_churn_score"] = df.get("fe_churn_risk_rule", np.nan)
        df["ml_churn_label"] = (
            df["ml_churn_score"] >= HIGH_RISK_THRESHOLD
        ).astype(int)

    def risk_level(score):
        if pd.isna(score):
            return "Unknown"
        if score >= HIGH_RISK_THRESHOLD:
            return "High"
        if score >= MEDIUM_RISK_THRESHOLD:
            return "Medium"
        return "Low"

    df["risk_level"] = df["ml_churn_score"].apply(risk_level)
    df["risk_updated_at"] = pd.Timestamp.now().isoformat()

    keep_cols = [c for c in [
        CUSTOMER_ID_COL,
        "churn", "avgrev", "change_rev", "custcare_Mean",
        "fe_churn_risk_rule", "ml_churn_score", "ml_churn_label",
        "risk_level", "customer_segment", "risk_updated_at",
    ] if c in df.columns]

    return df[keep_cols].reset_index(drop=True)


def _build_churn_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI agregat untuk Executive Overview dashboard.
    Satu baris per segmen + satu baris total (segment='ALL').
    """
    rows = []

    total = len(df)
    churned = int(df["churn"].sum()) if "churn" in df.columns else 0
    at_risk = int((df["risk_level"] == "High").sum()) if "risk_level" in df.columns else 0
    avg_revenue = float(df["avgrev"].mean()) if "avgrev" in df.columns else 0
    avg_rev_change = float(df["change_rev"].mean()) if "change_rev" in df.columns else 0

    rows.append({
        "segment": "ALL",
        "total_customers": total,
        "churned_customers": churned,
        "churn_rate": round(churned / total, 4) if total > 0 else 0,
        "retention_rate": round(1 - (churned / total), 4) if total > 0 else 1,
        "at_risk_customers": at_risk,
        "avg_revenue_arpu": round(avg_revenue, 2),
        "avg_revenue_change": round(avg_rev_change, 4),
    })

    if "customer_segment" in df.columns:
        for seg in df["customer_segment"].unique():
            seg_df = df[df["customer_segment"] == seg]
            seg_total = len(seg_df)
            seg_churned = int(seg_df["churn"].sum()) if "churn" in seg_df.columns else 0
            seg_arpu = float(seg_df["avgrev"].mean()) if "avgrev" in seg_df.columns else 0
            seg_at_risk = int(
                (seg_df["risk_level"] == "High").sum()
            ) if "risk_level" in seg_df.columns else 0

            rows.append({
                "segment": str(seg),
                "total_customers": seg_total,
                "churned_customers": seg_churned,
                "churn_rate": round(seg_churned / seg_total, 4) if seg_total > 0 else 0,
                "retention_rate": round(1 - (seg_churned / seg_total), 4) if seg_total > 0 else 1,
                "at_risk_customers": seg_at_risk,
                "avg_revenue_arpu": round(seg_arpu, 2),
                "avg_revenue_change": 0.0,
            })

    return pd.DataFrame(rows)

def _build_churn_prediction(df: pd.DataFrame, model_scores_path: Path) -> pd.DataFrame:
    """
    Tabel prediksi ML — hanya berisi test set (20k baris dari churn_scores.csv).
    Digabung dengan fitur profil pelanggan dari Silver untuk konteks analisis.
    """
    ml_scores = pd.read_csv(model_scores_path)

    # Normalise nama kolom ID
    for candidate in ["Customer_ID", "customer_id", "CustomerID"]:
        if candidate in ml_scores.columns:
            ml_scores = ml_scores.rename(columns={candidate: CUSTOMER_ID_COL})
            break

    # Validasi kolom wajib
    required = ["ml_churn_score", "ml_churn_label"]
    missing = [c for c in required if c not in ml_scores.columns]
    if missing:
        raise ValueError(f"[GOLD] churn_scores.csv kurang kolom: {missing}")

    # Join dengan Silver untuk tambah konteks pelanggan
    context_cols = [c for c in [
        CUSTOMER_ID_COL,
        "avgrev",
        "change_rev",
        "months",
        "custcare_Mean",
        "drop_vce_Mean",
        "customer_segment",  # dari _build_customer_segments (jika sudah ada)
        "fe_churn_risk_rule",
    ] if c in df.columns]

    df_pred = ml_scores[[CUSTOMER_ID_COL] + required].merge(
        df[context_cols],
        on=CUSTOMER_ID_COL,
        how="left",
    )

        # Risk level berdasarkan ml_churn_score
    def risk_level(score):
        if pd.isna(score):
            return "Unknown"
        if score >= HIGH_RISK_THRESHOLD:
            return "High"
        if score >= MEDIUM_RISK_THRESHOLD:
            return "Medium"
        return "Low"

    df_pred["risk_level"] = df_pred["ml_churn_score"].apply(risk_level)

    # Kolom evaluasi model (hanya ada jika actual label tersedia)
    if "churn" in df_pred.columns:
        df_pred["is_correct"] = (
            df_pred["ml_churn_label"] == df_pred["churn"]
        ).astype(int)

    logger.info(f"[GOLD] churn_prediction: {len(df_pred):,} baris test set")
    logger.info(f"[GOLD] Distribusi risk_level:\n{df_pred['risk_level'].value_counts().to_string()}")

    return df_pred.reset_index(drop=True)