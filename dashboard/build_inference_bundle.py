from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier, early_stopping
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "Telecom_customer.csv"
BUNDLE_PATH = BASE_DIR / "ml" / "models" / "churn_inference_bundle.joblib"

SELECTED_FEATURES = [
    "rev_Mean", "mou_Mean", "totmrc_Mean", "da_Mean", "ovrmou_Mean", "ovrrev_Mean",
    "roam_Mean", "change_mou", "change_rev", "drop_vce_Mean", "blck_vce_Mean",
    "unan_vce_Mean", "plcd_vce_Mean", "recv_vce_Mean", "custcare_Mean", "cc_mou_Mean",
    "inonemin_Mean", "mou_cvce_Mean", "mou_rvce_Mean", "owylis_vce_Mean",
    "mouowylisv_Mean", "iwylis_vce_Mean", "mouiwylisv_Mean", "peak_vce_Mean",
    "mou_peav_Mean", "opk_vce_Mean", "mou_opkv_Mean", "drop_blk_Mean",
    "callwait_Mean", "months", "uniqsubs", "crclscod", "totcalls", "totmou",
    "totrev", "adjrev", "adjmou", "adjqty", "avgrev", "avgmou", "avgqty",
    "avg3mou", "avg3qty", "avg3rev", "avg6mou", "avg6qty", "avg6rev", "area",
    "hnd_price", "ethnic", "eqpdays", "mou_Mean_log", "avgmou_log",
]
RAW_INPUT_FEATURES = [feature for feature in SELECTED_FEATURES if not feature.endswith("_log")]
CATEGORICAL_INPUTS = ["crclscod", "area", "ethnic"]
NUMERIC_INPUTS = [feature for feature in RAW_INPUT_FEATURES if feature not in CATEGORICAL_INPUTS]
FIELD_GROUPS = {
    "Revenue and Usage": [
        "rev_Mean", "mou_Mean", "totmrc_Mean", "da_Mean", "ovrmou_Mean", "ovrrev_Mean",
        "change_mou", "change_rev", "totcalls", "totmou", "totrev", "adjrev", "adjmou",
        "adjqty", "avgrev", "avgmou", "avgqty", "avg3mou", "avg3qty", "avg3rev",
        "avg6mou", "avg6qty", "avg6rev",
    ],
    "Call Quality": [
        "drop_vce_Mean", "blck_vce_Mean", "unan_vce_Mean", "plcd_vce_Mean",
        "recv_vce_Mean", "custcare_Mean", "cc_mou_Mean", "inonemin_Mean",
        "mou_cvce_Mean", "mou_rvce_Mean", "owylis_vce_Mean", "mouowylisv_Mean",
        "iwylis_vce_Mean", "mouiwylisv_Mean", "peak_vce_Mean", "mou_peav_Mean",
        "opk_vce_Mean", "mou_opkv_Mean", "drop_blk_Mean", "callwait_Mean", "roam_Mean",
    ],
    "Customer Profile": [
        "months", "uniqsubs", "crclscod", "area", "hnd_price", "ethnic", "eqpdays",
    ],
}


def _fill_and_engineer(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    base_impute = [
        "rev_Mean", "mou_Mean", "totmrc_Mean", "da_Mean", "ovrmou_Mean",
        "ovrrev_Mean", "vceovr_Mean", "datovr_Mean", "roam_Mean",
    ]
    df[base_impute] = SimpleImputer(strategy="median").fit_transform(df[base_impute])
    df[["change_mou", "change_rev"]] = SimpleImputer(strategy="median").fit_transform(
        df[["change_mou", "change_rev"]]
    )
    df[["avg6mou", "avg6qty", "avg6rev"]] = SimpleImputer(strategy="median").fit_transform(
        df[["avg6mou", "avg6qty", "avg6rev"]]
    )
    df[["hnd_price"]] = SimpleImputer(strategy="median").fit_transform(df[["hnd_price"]])

    for column in [
        "truck", "rv", "forgntvl", "ethnic", "kid0_2", "kid3_5", "kid6_10",
        "kid11_15", "kid16_17", "creditcd", "marital", "dualband", "refurb_new", "area",
    ]:
        df[column] = df[column].fillna("Unknown")
    for column in ["phones", "models", "eqpdays"]:
        df[column] = df[column].fillna(df[column].median())

    df = df.drop(
        columns=[
            "numbcars", "ownrent", "dwlltype", "dwllsize", "HHstatin", "lor",
            "adults", "income", "infobase", "hnd_webcap", "prizm_social_one",
        ],
        errors="ignore",
    )

    exclude_cols = [
        "churn", "Customer_ID", "creditcd", "asl_flag", "new_cell", "months",
        "uniqsubs", "actvsubs", "phones", "models", "totcalls", "totrev", "totmou",
        "adjrev", "adjmou", "avgrev", "avgmou",
    ]
    numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns.tolist()
    for column in [col for col in numeric_cols if col not in exclude_cols]:
        lower_limit = df[column].quantile(0.005)
        upper_limit = df[column].quantile(0.995)
        df[column] = df[column].clip(lower=lower_limit, upper=upper_limit)

    for column in [
        "rev_Mean", "mou_Mean", "totrev", "totmou", "adjrev", "adjmou",
        "avgrev", "avgmou", "avg3rev", "avg6rev",
    ]:
        if (df[column] >= 0).all():
            df[f"{column}_log"] = np.log1p(df[column])

    for column in ["ovrmou_Mean", "vceovr_Mean", "ovrrev_Mean", "datovr_Mean"]:
        df[f"{column}_flag"] = (df[column] > 0).astype(int)
        df[f"{column}_log"] = np.log1p(df[column])

    return df


def _encode_categories(df: pd.DataFrame, label_maps: dict[str, dict[str, int]]) -> pd.DataFrame:
    encoded = df.copy()
    for column, mapping in label_maps.items():
        fallback = "Unknown" if "Unknown" in mapping else sorted(mapping, key=mapping.get)[0]
        encoded[column] = encoded[column].astype(str).map(lambda value: mapping.get(value, mapping[fallback]))
    return encoded


def build_bundle() -> Path:
    df = pd.read_csv(RAW_DATA_PATH)
    processed = _fill_and_engineer(df)

    label_maps = {
        column: {value: index for index, value in enumerate(sorted(processed[column].astype(str).unique()))}
        for column in CATEGORICAL_INPUTS
    }
    encoded = _encode_categories(processed, label_maps)

    X = encoded[RAW_INPUT_FEATURES].copy()
    X["mou_Mean_log"] = np.log1p(X["mou_Mean"])
    X["avgmou_log"] = np.log1p(X["avgmou"])
    X = X[SELECTED_FEATURES]
    y = encoded["churn"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=1, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=SELECTED_FEATURES, index=X_train.index)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=SELECTED_FEATURES, index=X_test.index)
    X_train_sm, y_train_sm = SMOTE(random_state=42).fit_resample(X_train_scaled, y_train)

    model = LGBMClassifier(
        objective="binary",
        metric="auc",
        boosting_type="gbdt",
        num_leaves=31,
        learning_rate=0.05,
        colsample_bytree=0.9,
        subsample=0.8,
        subsample_freq=5,
        n_estimators=1000,
        is_unbalance=True,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(
        X_train_sm,
        y_train_sm,
        eval_set=[(X_test_scaled, y_test)],
        callbacks=[early_stopping(stopping_rounds=50, verbose=False)],
    )

    defaults = {feature: float(processed[feature].median()) for feature in NUMERIC_INPUTS}
    defaults.update({feature: str(processed[feature].mode(dropna=False).iloc[0]) for feature in CATEGORICAL_INPUTS})
    category_options = {
        feature: sorted(processed[feature].astype(str).unique().tolist()) for feature in CATEGORICAL_INPUTS
    }

    field_metadata = []
    for group_name, features in FIELD_GROUPS.items():
        for feature in features:
            field_metadata.append(
                {
                    "name": feature,
                    "group": group_name,
                    "type": "select" if feature in CATEGORICAL_INPUTS else "number",
                    "step": "any",
                    "default": defaults[feature],
                    "options": category_options.get(feature, []),
                }
            )

    bundle = {
        "model": model,
        "scaler": scaler,
        "selected_features": SELECTED_FEATURES,
        "raw_input_features": RAW_INPUT_FEATURES,
        "categorical_inputs": CATEGORICAL_INPUTS,
        "numeric_inputs": NUMERIC_INPUTS,
        "label_maps": label_maps,
        "defaults": defaults,
        "field_groups": FIELD_GROUPS,
        "field_metadata": field_metadata,
        "bundle_model_name": "lightgbm_deployment_bundle",
        "note": (
            "Deployment-safe bundle built from the visible notebook preprocessing. "
            "The original best_model.joblib was not used directly because its preprocessing artifacts were not persisted."
        ),
    }

    BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    return BUNDLE_PATH


if __name__ == "__main__":
    print(f"Inference bundle saved to: {build_bundle()}")
