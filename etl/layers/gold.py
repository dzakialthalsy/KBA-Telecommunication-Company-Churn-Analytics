"""
Gold Layer — Business-Ready Aggregates & Mart
Task: DE-09 | Owner: Dhea Akmalia Fibri

Prinsip Medallion Gold:
- Baca dari Silver, JANGAN baca Bronze atau sumber langsung
- Data sudah di-agregasi / di-join sesuai kebutuhan bisnis & dashboard
- Didesain untuk konsumsi langsung: Metabase, laporan, ML model
- Satu tabel Gold = satu "pertanyaan bisnis" yang terjawab
- Disimpan sebagai tabel DuckDB:
    gold_customer_segments   → segmentasi pelanggan untuk dashboard
    gold_churn_summary       → KPI agregat untuk Executive Overview
    gold_churn_risk          → skor risiko per pelanggan (input dari ML)
    gold_kpi_monthly         → tren KPI bulanan (jika ada kolom tanggal)
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger


SILVER_TABLE = "silver_telecom_cleaned"

# Threshold segmentasi — sesuai BA-05
# PM-06 (Analytics Design Signoff) → disepakati threshold ini
HIGH_RISK_THRESHOLD = 0.7
MEDIUM_RISK_THRESHOLD = 0.4
HIGH_VALUE_AVGREV_PERCENTILE = 0.75


def load_to_gold(duckdb_path: Path, model_scores_path: Path = None) -> dict:
    """
    Build semua tabel Gold dari Silver.
    Jika model_scores_path tersedia (output ML Fairuz), gabungkan ke gold_churn_risk.
    Return: dict berisi row count tiap tabel Gold.
    """
    logger.info("[GOLD] Membaca Silver layer ...")
    con = duckdb.connect(str(duckdb_path))
    df = con.execute(f"SELECT * FROM {SILVER_TABLE}").df()
    logger.info(f"[GOLD] {len(df):,} baris dari Silver")

    results = {}

    # ── Tabel 1: gold_customer_segments ──────────────────────────────────
    df_seg = _build_customer_segments(df.copy())
    con.execute("DROP TABLE IF EXISTS gold_customer_segments")
    con.execute("CREATE TABLE gold_customer_segments AS SELECT * FROM df_seg")
    results["gold_customer_segments"] = len(df_seg)
    logger.success(f"[GOLD] gold_customer_segments: {len(df_seg):,} baris ✓")

    # ── Tabel 2: gold_churn_risk (+ merge ML scores jika ada) ────────────
    df_risk = _build_churn_risk(df.copy(), model_scores_path)
    con.execute("DROP TABLE IF EXISTS gold_churn_risk")
    con.execute("CREATE TABLE gold_churn_risk AS SELECT * FROM df_risk")
    results["gold_churn_risk"] = len(df_risk)
    logger.success(f"[GOLD] gold_churn_risk: {len(df_risk):,} baris ✓")

    # ── Tabel 3: gold_churn_summary (KPI agregat untuk Executive dashboard) ─
    df_summary = _build_churn_summary(df_risk.copy())
    con.execute("DROP TABLE IF EXISTS gold_churn_summary")
    con.execute("CREATE TABLE gold_churn_summary AS SELECT * FROM df_summary")
    results["gold_churn_summary"] = len(df_summary)
    logger.success(f"[GOLD] gold_churn_summary: {len(df_summary):,} baris ✓")

    con.close()
    return results


def _build_customer_segments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Segmentasi pelanggan berdasarkan ARPU dan rule-based risk score.
    Output: satu baris per pelanggan dengan label segmen.
    Dikonsumsi: dashboard Metabase (At-Risk Board, drill-down)
    """
    # Tentukan High Value threshold dari data aktual
    if "avgrev" in df.columns:
        hv_threshold = df["avgrev"].quantile(HIGH_VALUE_AVGREV_PERCENTILE)
    else:
        hv_threshold = 0

    risk_col = "fe_churn_risk_rule" if "fe_churn_risk_rule" in df.columns else None

    def assign_segment(row):
        # Sudah churn (label aktual dari dataset)
        if "churn" in row and row["churn"] == 1:
            return "Churned"
        # Rule-based risk (sebelum model ML tersedia)
        if risk_col and row.get(risk_col, 0) >= HIGH_RISK_THRESHOLD:
            return "At-Risk"
        if risk_col and row.get(risk_col, 0) >= MEDIUM_RISK_THRESHOLD:
            return "Watch"
        # High Value: ARPU tinggi dan tidak at-risk
        if "avgrev" in row and row["avgrev"] >= hv_threshold:
            return "High Value"
        return "Stable"

    df["customer_segment"] = df.apply(assign_segment, axis=1)
    df["segment_updated_at"] = pd.Timestamp.now().isoformat()

    # Pilih kolom relevan untuk dashboard
    keep_cols = [c for c in [
        "customer_id", "churn", "avgrev", "change_rev",
        "custcare_mean", "drop_vce_mean",
        "fe_high_care_call", "fe_revenue_drop",
        "fe_low_usage", "fe_churn_risk_rule",
        "customer_segment", "segment_updated_at",
    ] if c in df.columns]

    return df[keep_cols].reset_index(drop=True)


def _build_churn_risk(df: pd.DataFrame, model_scores_path: Path = None) -> pd.DataFrame:
    """
    Tabel risiko churn per pelanggan.
    Jika model ML (Fairuz) sudah tersedia → gunakan ml_churn_score.
    Jika belum → gunakan fe_churn_risk_rule sebagai fallback.
    Output dikonsumsi: At-Risk Board + ML pipeline
    """
    if model_scores_path and Path(model_scores_path).exists():
        logger.info("[GOLD] ML scores ditemukan → merge ke gold_churn_risk")
        ml_scores = pd.read_csv(model_scores_path)

        # Ekspektasi kolom dari Fairuz: customer_id, ml_churn_score, ml_churn_label
        required_ml_cols = ["customer_id", "ml_churn_score", "ml_churn_label"]
        missing = [c for c in required_ml_cols if c not in ml_scores.columns]
        if missing:
            logger.warning(f"[GOLD] ML scores tidak punya kolom: {missing} → pakai rule-based")
        elif "customer_id" in df.columns:
            df = df.merge(
                ml_scores[required_ml_cols],
                on="customer_id",
                how="left"
            )
            logger.success("[GOLD] ML scores berhasil di-merge ✓")
    else:
        logger.info("[GOLD] ML scores belum tersedia → pakai rule-based score sebagai fallback")
        df["ml_churn_score"] = df.get("fe_churn_risk_rule", np.nan)
        df["ml_churn_label"] = (df["ml_churn_score"] >= HIGH_RISK_THRESHOLD).astype(int)

    # Tambah kolom risk level untuk filter di dashboard
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
        "customer_id", "churn",
        "avgrev", "change_rev", "custcare_mean",
        "fe_churn_risk_rule", "ml_churn_score", "ml_churn_label",
        "risk_level", "customer_segment", "risk_updated_at",
    ] if c in df.columns]

    return df[keep_cols].reset_index(drop=True)


def _build_churn_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    KPI agregat untuk Executive Overview dashboard.
    Output: satu baris per segmen + baris total keseluruhan.
    Dikonsumsi: Executive Overview di Metabase
    """
    rows = []

    # Total keseluruhan
    total = len(df)
    churned = df["churn"].sum() if "churn" in df.columns else 0
    at_risk = (df["risk_level"] == "High").sum() if "risk_level" in df.columns else 0
    avg_revenue = df["avgrev"].mean() if "avgrev" in df.columns else 0
    avg_rev_change = df["change_rev"].mean() if "change_rev" in df.columns else 0

    rows.append({
        "segment": "ALL",
        "total_customers": int(total),
        "churned_customers": int(churned),
        "churn_rate": round(churned / total, 4) if total > 0 else 0,
        "retention_rate": round(1 - (churned / total), 4) if total > 0 else 1,
        "at_risk_customers": int(at_risk),
        "avg_revenue_arpu": round(float(avg_revenue), 2),
        "avg_revenue_change": round(float(avg_rev_change), 4),
    })

    # Per segmen
    if "customer_segment" in df.columns:
        for seg in df["customer_segment"].unique():
            seg_df = df[df["customer_segment"] == seg]
            seg_total = len(seg_df)
            seg_churned = seg_df["churn"].sum() if "churn" in seg_df.columns else 0
            seg_arpu = seg_df["avgrev"].mean() if "avgrev" in seg_df.columns else 0
            rows.append({
                "segment": str(seg),
                "total_customers": int(seg_total),
                "churned_customers": int(seg_churned),
                "churn_rate": round(seg_churned / seg_total, 4) if seg_total > 0 else 0,
                "retention_rate": round(1 - (seg_churned / seg_total), 4) if seg_total > 0 else 1,
                "at_risk_customers": int((seg_df.get("risk_level", pd.Series()) == "High").sum()),
                "avg_revenue_arpu": round(float(seg_arpu), 2),
                "avg_revenue_change": 0.0,
            })

    summary_df = pd.DataFrame(rows)
    return summary_df
