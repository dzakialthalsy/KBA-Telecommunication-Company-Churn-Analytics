from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.requests import Request
from starlette.templating import Jinja2Templates

try:
    import duckdb
except ImportError:  # pragma: no cover - dashboard can fall back to CSV artifacts.
    duckdb = None


BASE_DIR = Path(__file__).resolve().parents[1]
BUNDLE_PATH = BASE_DIR / "ml" / "models" / "churn_inference_bundle.joblib"
ML_SCORES_PATH = BASE_DIR / "ml" / "models" / "churn_scores.csv"
DUCKDB_PATH = BASE_DIR / "data" / "gold" / "telco_warehouse.duckdb"
RAW_DATA_CANDIDATES = [
    BASE_DIR / "data" / "raw" / "Telecom_customer.csv",
    BASE_DIR / "data" / "raw" / "telecom_customer.csv",
]
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
CUSTOMER_ID_CANDIDATES = ("Customer_ID", "customer_id", "CustomerID")
RL_ACTION_COL = "rl_recommended_action"


class PredictionPayload(BaseModel):
    features: dict[str, Any]


_bundle_cache: dict[str, Any] | None = None


def _load_bundle() -> dict[str, Any]:
    global _bundle_cache
    if _bundle_cache is not None:
        return _bundle_cache
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(
            f"Bundle inference belum ada: {BUNDLE_PATH}. Jalankan `python dashboard/build_inference_bundle.py` dulu."
        )
    _bundle_cache = joblib.load(BUNDLE_PATH)
    return _bundle_cache


app = FastAPI(title="Telco Churn Executive Dashboard", version="2.0.0")


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _is_container_runtime() -> bool:
    return (
        Path("/.dockerenv").exists()
        or Path("/run/.containerenv").exists()
        or _env_truthy("APP_DOCKER_RUNTIME")
    )


@app.middleware("http")
async def require_docker_runtime(request: Request, call_next):
    if _env_truthy("APP_REQUIRE_DOCKER", default="true") and not _is_container_runtime():
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Dashboard hanya boleh diakses melalui Docker container. "
                    "Jalankan dengan `docker compose up --build dashboard`."
                )
            },
        )
    return await call_next(request)


def _find_id_column(columns: list[str] | pd.Index) -> str | None:
    for candidate in CUSTOMER_ID_CANDIDATES:
        if candidate in columns:
            return candidate
    return None


def _number_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def _format_int(value: float | int) -> str:
    return f"{int(round(float(value))):,}"


def _format_money(value: float | int) -> str:
    return f"${float(value):,.2f}"


def _format_percent(value: float | int) -> str:
    return f"{float(value) * 100:.2f}%"


def _risk_level_from_score(score: float) -> str:
    if score >= 0.70:
        return "High"
    if score >= 0.40:
        return "Medium"
    return "Low"


def _read_gold_table(table_name: str) -> pd.DataFrame:
    if duckdb is None or not DUCKDB_PATH.exists():
        return pd.DataFrame()
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        return con.execute(f"SELECT * FROM {table_name}").df()
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


def _raw_data_path() -> Path | None:
    for path in RAW_DATA_CANDIDATES:
        if path.exists():
            return path
    return None


def _read_raw_context(id_col: str) -> pd.DataFrame:
    raw_path = _raw_data_path()
    if raw_path is None:
        return pd.DataFrame()

    header = pd.read_csv(raw_path, nrows=0)
    raw_id_col = _find_id_column(header.columns)
    if raw_id_col is None:
        return pd.DataFrame()

    wanted_cols = [
        raw_id_col,
        "churn",
        "avgrev",
        "change_rev",
        "months",
        "custcare_Mean",
        "drop_vce_Mean",
        "totrev",
        "avgmou",
        "area",
        "crclscod",
        "ethnic",
    ]
    available_cols = [col for col in wanted_cols if col in header.columns]
    raw = pd.read_csv(raw_path, usecols=available_cols)
    raw = raw.rename(columns={raw_id_col: id_col})
    return raw.drop_duplicates(subset=[id_col])


def _load_dashboard_frame() -> tuple[pd.DataFrame, str]:
    risk = _read_gold_table("gold.churn_risk")
    if not risk.empty:
        id_col = _find_id_column(risk.columns)
        segments = _read_gold_table("gold.customer_segments")
        if id_col and not segments.empty:
            seg_id_col = _find_id_column(segments.columns)
            if seg_id_col:
                segment_cols = [
                    seg_id_col,
                    *[
                        col
                        for col in ["customer_segment", "fe_high_care_call", "fe_revenue_drop", "fe_low_usage"]
                        if col in segments.columns and col not in risk.columns
                    ],
                ]
                segments = segments[segment_cols].rename(columns={seg_id_col: id_col})
                risk = risk.merge(segments, on=id_col, how="left")
        return risk, "Gold DuckDB"

    if ML_SCORES_PATH.exists():
        scores = pd.read_csv(ML_SCORES_PATH)
        id_col = _find_id_column(scores.columns)
        if id_col:
            raw = _read_raw_context(id_col)
            if not raw.empty:
                scores = scores.merge(raw, on=id_col, how="left")
        return scores, "ML scores CSV"

    raw_path = _raw_data_path()
    if raw_path is not None:
        return pd.read_csv(raw_path), "Raw CSV"

    return pd.DataFrame(), "No data"


def _derive_segments(df: pd.DataFrame) -> pd.Series:
    if "customer_segment" in df.columns:
        return df["customer_segment"].fillna("Unknown").astype(str)

    churn = _number_series(df, "churn")
    score = _number_series(df, "ml_churn_score", default=0.0).clip(0.0, 1.0)
    arpu = _number_series(df, "avgrev")
    high_value_threshold = arpu.quantile(0.75) if arpu.nunique() > 1 else arpu.max()

    segments = pd.Series("Stable", index=df.index, dtype=object)
    segments.loc[arpu >= high_value_threshold] = "High Value"
    segments.loc[score >= 0.40] = "Watch"
    segments.loc[score >= 0.70] = "At-Risk"
    segments.loc[churn == 1] = "Churned"
    return segments


def _counts(df: pd.DataFrame, column: str, order: list[str] | None = None) -> list[dict[str, Any]]:
    if df.empty or column not in df.columns:
        return []
    counts = df[column].fillna("Unknown").astype(str).value_counts()
    labels = order or counts.index.tolist()
    max_count = int(counts.max()) if not counts.empty else 1
    rows = []
    for label in labels:
        value = int(counts.get(label, 0))
        if value == 0 and order is None:
            continue
        rows.append(
            {
                "label": label,
                "value": value,
                "display": _format_int(value),
                "percent": round((value / max_count) * 100, 2) if max_count else 0,
            }
        )
    return rows


def _revenue_by_segment(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "avgrev" not in df.columns:
        return []
    frame = df.copy()
    frame["avgrev"] = _number_series(frame, "avgrev")
    grouped = (
        frame.groupby("customer_segment", dropna=False)
        .agg(avg_revenue=("avgrev", "mean"), customers=("avgrev", "size"))
        .reset_index()
        .sort_values("avg_revenue", ascending=False)
    )
    max_revenue = float(grouped["avg_revenue"].max()) if not grouped.empty else 1.0
    return [
        {
            "label": str(row["customer_segment"]),
            "value": round(float(row["avg_revenue"]), 2),
            "display": _format_money(row["avg_revenue"]),
            "customers": _format_int(row["customers"]),
            "percent": round((float(row["avg_revenue"]) / max_revenue) * 100, 2) if max_revenue else 0,
        }
        for _, row in grouped.iterrows()
    ]


def _tenure_risk(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "months" not in df.columns:
        return []
    frame = df.copy()
    frame["months"] = _number_series(frame, "months")
    score = _number_series(frame, "ml_churn_score", default=np.nan)
    churn = _number_series(frame, "churn", default=np.nan)
    frame["_risk_value"] = score.fillna(churn).fillna(0.0)
    frame["_tenure_bucket"] = pd.cut(
        frame["months"],
        bins=[-1, 6, 12, 24, 36, 1200],
        labels=["0-6", "7-12", "13-24", "25-36", "36+"],
    )
    grouped = (
        frame.groupby("_tenure_bucket", observed=False)
        .agg(risk=("_risk_value", "mean"), customers=("_risk_value", "size"))
        .reset_index()
    )
    return [
        {
            "label": str(row["_tenure_bucket"]),
            "value": round(float(row["risk"]) * 100, 2),
            "display": f"{float(row['risk']) * 100:.1f}%",
            "customers": _format_int(row["customers"]),
            "percent": round(float(row["risk"]) * 100, 2),
        }
        for _, row in grouped.iterrows()
        if pd.notna(row["_tenure_bucket"])
    ]


def _top_at_risk(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    id_col = _find_id_column(df.columns) or df.columns[0]
    frame = df.copy()
    frame["_score"] = _number_series(frame, "ml_churn_score", default=0.0)
    if "ml_churn_score" not in frame.columns and "fe_churn_risk_rule" in frame.columns:
        frame["_score"] = _number_series(frame, "fe_churn_risk_rule", default=0.0)
    frame["avgrev"] = _number_series(frame, "avgrev")
    top = frame.sort_values("_score", ascending=False).head(10)
    rows = []
    for _, row in top.iterrows():
        rows.append(
            {
                "customer_id": str(row.get(id_col, "-")),
                "score": f"{float(row['_score']) * 100:.1f}%",
                "segment": str(row.get("customer_segment", "Unknown")),
                "arpu": _format_money(row.get("avgrev", 0.0)),
                "action": str(row.get(RL_ACTION_COL, "review_customer")),
                "reward": _format_money(row.get("rl_expected_reward", 0.0)),
            }
        )
    return rows


def _dashboard_data() -> dict[str, Any]:
    df, source = _load_dashboard_frame()
    if df.empty:
        return {
            "source": source,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "kpis": [],
            "risk_distribution": [],
            "segment_distribution": [],
            "action_distribution": [],
            "revenue_by_segment": [],
            "tenure_risk": [],
            "top_at_risk": [],
        }

    df = df.copy()
    df["customer_segment"] = _derive_segments(df)
    score = _number_series(df, "ml_churn_score", default=np.nan).clip(0.0, 1.0)
    if score.isna().all() and "fe_churn_risk_rule" in df.columns:
        score = _number_series(df, "fe_churn_risk_rule", default=0.0).clip(0.0, 1.0)
    df["risk_level"] = df.get("risk_level", score.fillna(0.0).map(_risk_level_from_score))
    df["risk_level"] = df["risk_level"].fillna("Unknown").astype(str)

    total = len(df)
    churn = _number_series(df, "churn", default=np.nan)
    label = _number_series(df, "ml_churn_label", default=np.nan)
    churn_basis = churn if not churn.isna().all() else label
    churn_rate = float(churn_basis.mean()) if not churn_basis.isna().all() else float(score.mean())
    arpu = _number_series(df, "avgrev")
    revenue_change = _number_series(df, "change_rev")
    high_risk_count = int((df["risk_level"] == "High").sum())
    expected_reward = float(_number_series(df, "rl_expected_reward").sum())
    action_cost = float(_number_series(df, "rl_action_cost").sum())

    kpis = [
        {
            "label": "Total Customers",
            "value": _format_int(total),
            "detail": f"{_format_int(high_risk_count)} high risk",
        },
        {
            "label": "Churn Rate",
            "value": _format_percent(churn_rate),
            "detail": f"{_format_percent(1 - churn_rate)} retention",
        },
        {
            "label": "Average ARPU",
            "value": _format_money(arpu.mean()),
            "detail": f"{_format_money(revenue_change.mean())} avg revenue change",
        },
        {
            "label": "Expected RL Reward",
            "value": _format_money(expected_reward),
            "detail": f"{_format_money(action_cost)} estimated action cost",
        },
    ]

    return {
        "source": source,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kpis": kpis,
        "risk_distribution": _counts(df, "risk_level", order=["High", "Medium", "Low", "Unknown"]),
        "segment_distribution": _counts(df, "customer_segment"),
        "action_distribution": _counts(df, RL_ACTION_COL) if RL_ACTION_COL in df.columns else [],
        "revenue_by_segment": _revenue_by_segment(df),
        "tenure_risk": _tenure_risk(df),
        "top_at_risk": _top_at_risk(df),
    }


def _prepare_input(features: dict[str, Any]) -> pd.DataFrame:
    bundle = _load_bundle()
    row: dict[str, Any] = {}
    for feature in bundle["numeric_inputs"]:
        value = features.get(feature, bundle["defaults"][feature])
        try:
            row[feature] = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Nilai numerik tidak valid untuk '{feature}'.") from exc

    for feature in bundle["categorical_inputs"]:
        value = str(features.get(feature, bundle["defaults"][feature]))
        mapping = bundle["label_maps"][feature]
        fallback = "Unknown" if "Unknown" in mapping else bundle["defaults"][feature]
        row[feature] = mapping.get(value, mapping[fallback])

    row["mou_Mean_log"] = float(np.log1p(max(row["mou_Mean"], 0.0)))
    row["avgmou_log"] = float(np.log1p(max(row["avgmou"], 0.0)))

    frame = pd.DataFrame([row], columns=bundle["selected_features"])
    scaled = bundle["scaler"].transform(frame)
    return pd.DataFrame(scaled, columns=bundle["selected_features"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/executive")
def executive_dashboard() -> dict[str, Any]:
    return _dashboard_data()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    prediction_ready = True
    predictor_error = ""
    try:
        bundle = _load_bundle()
    except FileNotFoundError as exc:
        bundle = {
            "field_groups": {},
            "field_metadata": [],
            "bundle_model_name": "Inference bundle belum tersedia",
            "note": str(exc),
        }
        prediction_ready = False
        predictor_error = str(exc)

    grouped_fields = []
    for group_name, features in bundle["field_groups"].items():
        grouped_fields.append(
            {
                "name": group_name,
                "fields": [field for field in bundle["field_metadata"] if field["name"] in features],
            }
        )
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "dashboard": _dashboard_data(),
            "grouped_fields": grouped_fields,
            "model_name": bundle["bundle_model_name"],
            "note": bundle["note"],
            "prediction_ready": prediction_ready,
            "predictor_error": predictor_error,
        },
    )


@app.post("/predict")
def predict(payload: PredictionPayload) -> dict[str, Any]:
    bundle = _load_bundle()
    inference_frame = _prepare_input(payload.features)
    probability = float(bundle["model"].predict_proba(inference_frame)[0, 1])
    label = int(probability >= 0.5)
    return {
        "prediction": "Churn" if label == 1 else "Tidak Churn",
        "churn_label": label,
        "churn_probability": probability,
        "churn_rate_percent": round(probability * 100, 2),
    }
