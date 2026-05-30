import pandas as pd

from ml.rl.retention_bandit import apply_retention_bandit


def test_retention_bandit_preserves_churn_score_columns():
    scores = pd.DataFrame(
        {
            "Customer_ID": [1, 2],
            "ml_churn_score": [0.10, 0.85],
            "ml_churn_label": [0, 1],
        }
    )

    result = apply_retention_bandit(scores)

    assert result["ml_churn_score"].tolist() == [0.10, 0.85]
    assert result["ml_churn_label"].tolist() == [0, 1]
    assert "rl_recommended_action" in result.columns
    assert "rl_expected_reward" in result.columns


def test_retention_bandit_reduces_score_when_action_is_selected():
    scores = pd.DataFrame(
        {
            "Customer_ID": [1],
            "ml_churn_score": [0.90],
            "ml_churn_label": [1],
            "avgrev": [120.0],
            "change_rev": [-25.0],
            "custcare_Mean": [5.0],
            "drop_vce_Mean": [8.0],
            "months": [8],
        }
    )

    result = apply_retention_bandit(scores)

    assert result.loc[0, "rl_recommended_action"] != "no_action"
    assert result.loc[0, "rl_estimated_churn_reduction"] > 0
    assert result.loc[0, "rl_adjusted_churn_score"] < result.loc[0, "ml_churn_score"]
