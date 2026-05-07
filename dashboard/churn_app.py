from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.requests import Request
from starlette.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parents[1]
BUNDLE_PATH = BASE_DIR / "ml" / "models" / "churn_inference_bundle.joblib"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


class PredictionPayload(BaseModel):
    features: dict[str, Any]


def _load_bundle() -> dict[str, Any]:
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(
            f"Bundle inference belum ada: {BUNDLE_PATH}. Jalankan `python dashboard/build_inference_bundle.py` dulu."
        )
    return joblib.load(BUNDLE_PATH)


bundle = _load_bundle()
app = FastAPI(title="Telco Churn Predictor", version="1.0.0")


def _prepare_input(features: dict[str, Any]) -> pd.DataFrame:
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
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
            "grouped_fields": grouped_fields,
            "model_name": bundle["bundle_model_name"],
            "note": bundle["note"],
        },
    )


@app.post("/predict")
def predict(payload: PredictionPayload) -> dict[str, Any]:
    inference_frame = _prepare_input(payload.features)
    probability = float(bundle["model"].predict_proba(inference_frame)[0, 1])
    label = int(probability >= 0.5)
    return {
        "prediction": "Churn" if label == 1 else "Tidak Churn",
        "churn_label": label,
        "churn_probability": probability,
        "churn_rate_percent": round(probability * 100, 2),
    }
