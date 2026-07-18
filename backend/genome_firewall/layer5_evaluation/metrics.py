from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    recall_score,
    roc_auc_score,
)

from genome_firewall.layer3_model.random_forest import CalibratedRandomForest
from genome_firewall.layer4_scoring.predictor import decide_prediction


def evaluate_drug_model(
    model: CalibratedRandomForest,
    X,
    y: np.ndarray,
    target_ok: np.ndarray,
) -> dict[str, float]:
    prob_fail = model.calibrated_probability_fail(X)
    preds: list[str] = []
    for p, ok in zip(prob_fail, target_ok):
        label, _, _, _ = decide_prediction(
            float(p),
            no_call_low=model.config.no_call_low,
            no_call_high=model.config.no_call_high,
            target_ok=bool(ok),
        )
        preds.append(label)

    called = np.array([p != "no_call" for p in preds])
    out: dict[str, float] = {
        "no_call_rate": float(np.mean(~called)),
        "brier": float(brier_score_loss(y, prob_fail)),
    }
    try:
        out["auroc"] = float(roc_auc_score(y, prob_fail))
    except ValueError:
        out["auroc"] = None
    try:
        out["pr_auc"] = float(average_precision_score(y, prob_fail))
    except ValueError:
        out["pr_auc"] = None

    if called.any():
        y_called = y[called]
        p_called = np.array([0 if p == "likely_to_work" else 1 for p in np.array(preds)[called]])
        out["balanced_accuracy_called"] = float(balanced_accuracy_score(y_called, p_called))
        out["f1_called"] = float(f1_score(y_called, p_called, zero_division=0))
        out["recall_resistant"] = float(recall_score(y_called, p_called, pos_label=1, zero_division=0))
        out["recall_susceptible"] = float(recall_score(y_called, p_called, pos_label=0, zero_division=0))
    else:
        out["balanced_accuracy_called"] = None
        out["f1_called"] = None
        out["recall_resistant"] = None
        out["recall_susceptible"] = None
    return out
