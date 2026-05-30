from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


CUSTOMER_ID_CANDIDATES = ("Customer_ID", "customer_id", "CustomerID")
REQUIRED_SCORE_COLUMNS = ("ml_churn_score", "ml_churn_label")
RL_OUTPUT_COLUMNS = [
    "rl_recommended_action",
    "rl_expected_reward",
    "rl_estimated_churn_reduction",
    "rl_adjusted_churn_score",
    "rl_action_cost",
    "rl_policy_confidence",
    "rl_policy_version",
    "rl_generated_at",
]
POLICY_VERSION = "contextual_bandit_v1"


@dataclass(frozen=True)
class RetentionAction:
    name: str
    fixed_cost: float
    discount_rate: float
    base_effect: float
    revenue_drop_weight: float = 0.0
    care_weight: float = 0.0
    quality_weight: float = 0.0
    high_value_weight: float = 0.0
    tenure_weight: float = 0.0


ACTIONS = [
    RetentionAction("no_action", 0.0, 0.00, 0.000),
    RetentionAction("sms_retention_reminder", 0.25, 0.00, 0.018, tenure_weight=0.10),
    RetentionAction("customer_care_call", 3.00, 0.00, 0.045, care_weight=0.35),
    RetentionAction("service_quality_followup", 4.00, 0.00, 0.055, quality_weight=0.45),
    RetentionAction("bonus_data_package", 7.50, 0.00, 0.070, quality_weight=0.15),
    RetentionAction("discount_5_percent", 1.00, 0.05, 0.075, revenue_drop_weight=0.45),
    RetentionAction("discount_10_percent", 1.50, 0.10, 0.105, revenue_drop_weight=0.60),
    RetentionAction("high_value_loyalty_offer", 12.00, 0.02, 0.120, high_value_weight=0.55),
]


def _find_id_column(columns: Iterable[str]) -> str:
    for candidate in CUSTOMER_ID_CANDIDATES:
        if candidate in columns:
            return candidate
    raise ValueError(f"File skor harus punya salah satu kolom ID: {CUSTOMER_ID_CANDIDATES}")


def _risk_level(score: float) -> str:
    if score >= 0.70:
        return "High"
    if score >= 0.40:
        return "Medium"
    return "Low"


def _safe_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.fillna(default)


def _percentile_rank(values: pd.Series) -> pd.Series:
    numeric = _safe_numeric(values)
    if numeric.nunique(dropna=True) <= 1:
        return pd.Series(np.zeros(len(numeric)), index=numeric.index, dtype=float)
    return numeric.rank(method="average", pct=True).fillna(0.0).clip(0.0, 1.0)


def _load_context(raw_path: Path | None, scores: pd.DataFrame, id_col: str) -> pd.DataFrame:
    if raw_path is None or not raw_path.exists():
        return scores.copy()

    context_cols = [
        id_col,
        "avgrev",
        "change_rev",
        "custcare_Mean",
        "drop_vce_Mean",
        "months",
        "totrev",
        "avgmou",
        "mou_Mean",
        "area",
        "crclscod",
        "ethnic",
    ]
    raw_head = pd.read_csv(raw_path, nrows=0)
    raw_id_col = _find_id_column(raw_head.columns)
    available_cols = [raw_id_col] + [col for col in context_cols if col in raw_head.columns and col != id_col]
    raw = pd.read_csv(raw_path, usecols=available_cols)
    raw = raw.rename(columns={raw_id_col: id_col})
    raw = raw.drop_duplicates(subset=[id_col])
    return scores.merge(raw, on=id_col, how="left")


def _prepare_context(frame: pd.DataFrame) -> pd.DataFrame:
    context = frame.copy()
    score = _safe_numeric(context["ml_churn_score"]).clip(0.0, 1.0)
    context["ml_churn_score"] = score
    context["rl_risk_level"] = score.map(_risk_level)

    if "avgrev" in context:
        arpu = _safe_numeric(context["avgrev"], default=float(score.median() * 50 + 25))
    else:
        arpu = pd.Series(25.0 + score * 75.0, index=context.index)
    arpu = arpu.clip(lower=1.0)
    context["_rl_customer_value"] = arpu
    context["_rl_high_value"] = _percentile_rank(arpu)

    if "change_rev" in context:
        revenue_drop = (-_safe_numeric(context["change_rev"])).clip(lower=0.0)
        context["_rl_revenue_drop"] = _percentile_rank(revenue_drop)
    else:
        context["_rl_revenue_drop"] = score

    if "custcare_Mean" in context:
        context["_rl_care_need"] = _percentile_rank(context["custcare_Mean"])
    else:
        context["_rl_care_need"] = score * 0.5

    if "drop_vce_Mean" in context:
        context["_rl_quality_issue"] = _percentile_rank(context["drop_vce_Mean"])
    else:
        context["_rl_quality_issue"] = score * 0.5

    if "months" in context:
        months = _safe_numeric(context["months"])
        context["_rl_new_customer"] = (1.0 - (months / 24.0)).clip(0.0, 1.0)
    else:
        context["_rl_new_customer"] = 0.0

    return context


def _estimate_action(row: pd.Series, action: RetentionAction) -> tuple[float, float, float]:
    score = float(row["ml_churn_score"])
    customer_value = float(row["_rl_customer_value"])

    if action.name == "no_action":
        return 0.0, score, 0.0

    context_boost = (
        action.revenue_drop_weight * float(row["_rl_revenue_drop"])
        + action.care_weight * float(row["_rl_care_need"])
        + action.quality_weight * float(row["_rl_quality_issue"])
        + action.high_value_weight * float(row["_rl_high_value"])
        + action.tenure_weight * float(row["_rl_new_customer"])
    )
    risk_readiness = float(np.clip((score - 0.25) / 0.65, 0.0, 1.0))
    risk_multiplier = (risk_readiness ** 1.25) * (0.75 + score)
    churn_reduction = action.base_effect * risk_multiplier * (1.0 + context_boost)
    churn_reduction = float(np.clip(churn_reduction, 0.0, min(score, 0.25)))

    horizon_revenue = customer_value * 3.0
    action_cost = action.fixed_cost + (action.discount_rate * customer_value)
    overtreatment_penalty = action_cost * max(0.0, 0.50 - score) * 3.0
    expected_reward = (churn_reduction * horizon_revenue) - action_cost - overtreatment_penalty
    adjusted_score = max(score - churn_reduction, 0.0)
    return expected_reward, adjusted_score, action_cost


def apply_retention_bandit(scores: pd.DataFrame, raw_context_path: Path | None = None) -> pd.DataFrame:
    id_col = _find_id_column(scores.columns)
    missing = [col for col in REQUIRED_SCORE_COLUMNS if col not in scores.columns]
    if missing:
        raise ValueError(f"File skor kurang kolom wajib: {missing}")

    base = scores.drop(columns=[col for col in RL_OUTPUT_COLUMNS if col in scores.columns], errors="ignore").copy()
    context = _prepare_context(_load_context(raw_context_path, base, id_col))
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    outputs = []
    for _, row in context.iterrows():
        estimates = []
        for action in ACTIONS:
            expected_reward, adjusted_score, action_cost = _estimate_action(row, action)
            churn_reduction = float(row["ml_churn_score"]) - adjusted_score
            estimates.append(
                {
                    "action": action.name,
                    "expected_reward": expected_reward,
                    "adjusted_score": adjusted_score,
                    "action_cost": action_cost,
                    "churn_reduction": churn_reduction,
                }
            )

        estimates = sorted(estimates, key=lambda item: item["expected_reward"], reverse=True)
        best = estimates[0]
        runner_up = estimates[1] if len(estimates) > 1 else {"expected_reward": 0.0}
        confidence = 1.0 / (1.0 + np.exp(-(best["expected_reward"] - runner_up["expected_reward"])))

        outputs.append(
            {
                "rl_recommended_action": best["action"],
                "rl_expected_reward": round(float(best["expected_reward"]), 4),
                "rl_estimated_churn_reduction": round(float(best["churn_reduction"]), 6),
                "rl_adjusted_churn_score": round(float(best["adjusted_score"]), 6),
                "rl_action_cost": round(float(best["action_cost"]), 4),
                "rl_policy_confidence": round(float(confidence), 6),
                "rl_policy_version": POLICY_VERSION,
                "rl_generated_at": generated_at,
            }
        )

    rl_frame = pd.DataFrame(outputs, index=base.index)
    return pd.concat([base, rl_frame], axis=1)


def _default_raw_path() -> Path | None:
    env_path = os.getenv("RAW_DATA_PATH")
    candidates = [
        Path(env_path) if env_path else None,
        Path("data/raw/Telecom_customer.csv"),
        Path("data/raw/telecom_customer.csv"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tambahkan output RL/contextual bandit ke ml/models/churn_scores.csv."
    )
    parser.add_argument(
        "--scores-path",
        type=Path,
        default=Path(os.getenv("ML_SCORES_PATH", "ml/models/churn_scores.csv")),
        help="Path input churn scores.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Path output. Default: overwrite scores-path.",
    )
    parser.add_argument(
        "--raw-path",
        type=Path,
        default=_default_raw_path(),
        help="Path data raw untuk konteks pelanggan. Jika tidak ada, policy hanya memakai ml_churn_score.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output_path or args.scores_path
    scores = pd.read_csv(args.scores_path)
    augmented = apply_retention_bandit(scores, raw_context_path=args.raw_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    augmented.to_csv(output_path, index=False)
    print(f"RL churn scores saved to: {output_path}")
    print(f"Rows: {len(augmented):,}")
    print("Action distribution:")
    print(augmented["rl_recommended_action"].value_counts().to_string())


if __name__ == "__main__":
    main()
