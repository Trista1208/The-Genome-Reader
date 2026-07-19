from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score


class ProbabilityCalibrator:
    def __init__(self, method: str = "auto"):
        self.method = method
        self.model = None
        self.fitted_method = None

    def fit(self, scores: np.ndarray, y: np.ndarray):
        scores = np.asarray(scores, dtype=float)
        y = np.asarray(y, dtype=int)
        if np.unique(y).size != 2:
            raise ValueError("Calibration requires both resistant and susceptible examples")
        method = self.method
        if method == "auto":
            counts = np.bincount(y, minlength=2)
            method = "isotonic" if len(y) >= 200 and counts.min() >= 20 else "platt"
        if method == "isotonic":
            self.model = IsotonicRegression(out_of_bounds="clip").fit(scores, y)
        elif method == "platt":
            self.model = LogisticRegression(solver="lbfgs").fit(scores.reshape(-1, 1), y)
        else:
            raise ValueError(f"Unknown calibration method: {method}")
        self.fitted_method = method
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        scores = np.asarray(scores, dtype=float)
        if self.fitted_method == "isotonic":
            return np.asarray(self.model.predict(scores), dtype=float)
        return self.model.predict_proba(scores.reshape(-1, 1))[:, 1]


def choose_ambiguity_band(
    probabilities: np.ndarray,
    y: np.ndarray,
    ood: np.ndarray | None = None,
    minimum_coverage: float = 0.70,
) -> tuple[float, float, dict]:
    probabilities = np.asarray(probabilities, dtype=float)
    y = np.asarray(y, dtype=int)
    ood = np.zeros(len(y), dtype=bool) if ood is None else np.asarray(ood, dtype=bool)
    best = None
    for margin in np.arange(0.0, 0.36, 0.025):
        low, high = 0.5 - margin, 0.5 + margin
        called = (~ood) & ((probabilities < low) | (probabilities > high))
        coverage = float(called.mean())
        if coverage < minimum_coverage or called.sum() == 0 or np.unique(y[called]).size < 2:
            continue
        score = float(balanced_accuracy_score(y[called], probabilities[called] >= 0.5))
        candidate = (score, coverage, -margin, low, high)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        low = high = 0.5
        called = ~ood
        score = float(balanced_accuracy_score(y[called], probabilities[called] >= 0.5))
        coverage = float(called.mean())
    else:
        score, coverage, _neg_margin, low, high = best
    return float(low), float(high), {"balanced_accuracy_called": score, "coverage": coverage}
