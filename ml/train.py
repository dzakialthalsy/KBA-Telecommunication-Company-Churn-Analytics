"""
ML Pipeline — Model Training & Evaluation
Task: ML-07, ML-08, ML-09 | Owner: Fairuz El Fauzy

Model: Logistic Regression, Decision Tree, Random Forest
Target: AUC-ROC >= 0.75, Accuracy >= 80%
"""

import os
import duckdb
import joblib
import pandas as pd
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score,
)

load_dotenv()

DUCKDB_PATH  = Path(os.getenv("DUCKDB_PATH", "data/mart/telco_warehouse.duckdb"))
TARGET_COL   = os.getenv("ML_TARGET_COLUMN", "churn")
TEST_SIZE    = float(os.getenv("ML_TEST_SIZE", 0.2))
RANDOM_STATE = int(os.getenv("ML_RANDOM_STATE", 42))
MODEL_OUT    = Path(os.getenv("MODEL_OUTPUT_PATH", "ml/models/best_model.joblib"))

MODELS = {
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
    "Decision Tree":       DecisionTreeClassifier(random_state=RANDOM_STATE),
    "Random Forest":       RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE),
}


def load_data() -> pd.DataFrame:
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB belum ada: {DUCKDB_PATH}. Jalankan ETL dulu.")
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("SELECT * FROM mart_churn_risk").df()
    con.close()
    return df


def build_pipeline(model) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("clf",     model),
    ])


def main():
    logger.info("=" * 55)
    logger.info("  Telco Churn — ML Training Pipeline")
    logger.info("=" * 55)

    df = load_data()
    logger.info(f"Data: {df.shape[0]:,} baris x {df.shape[1]} kolom")

    feature_cols = [c for c in df.select_dtypes(include="number").columns if c != TARGET_COL]
    X = df[feature_cols]
    y = df[TARGET_COL].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    logger.info(f"Train: {len(X_train):,} | Test: {len(X_test):,} | Churn: {y.mean():.1%}")

    results, trained = [], {}
    for name, model in MODELS.items():
        logger.info(f"Training: {name} ...")
        pipe = build_pipeline(model)
        pipe.fit(X_train, y_train)
        y_pred  = pipe.predict(X_test)
        y_proba = pipe.predict_proba(X_test)[:, 1]
        r = {
            "model":     name,
            "accuracy":  round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall":    round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1":        round(f1_score(y_test, y_pred, zero_division=0), 4),
            "auc_roc":   round(roc_auc_score(y_test, y_proba), 4),
        }
        results.append(r)
        trained[name] = pipe
        logger.info(f"  AUC={r['auc_roc']} | Acc={r['accuracy']} | F1={r['f1']}")

    best = max(results, key=lambda r: r["auc_roc"])
    logger.success(f"\nBest model: {best['model']} (AUC-ROC: {best['auc_roc']})")

    if best["auc_roc"] >= 0.75 and best["accuracy"] >= 0.80:
        logger.success("✓ Target KPI ML TERCAPAI")
    else:
        logger.warning("✗ Target belum tercapai — lakukan tuning hyperparameter")

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(trained[best["model"]], MODEL_OUT)
    logger.success(f"Model disimpan: {MODEL_OUT}")

    report = Path("ml/reports/model_evaluation.csv")
    report.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(report, index=False)
    logger.info(f"Laporan: {report}")


if __name__ == "__main__":
    main()
