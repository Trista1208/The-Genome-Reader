from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy import sparse
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from genome_firewall.config import ModelConfig
from genome_firewall.layer3_model.sampling import oversample_minority

CalibrationMethod = Literal["isotonic", "sigmoid", "passthrough"]


class PassthroughCalibrator:
    """Fallback when calibration split has a single class."""

    def predict(self, raw_probs: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(raw_probs, dtype=float).ravel(), 0.0, 1.0)


@dataclass
class CalibratedRandomForest:
    """Random Forest with post-hoc probability calibration."""

    rf: RandomForestClassifier
    calibrator: IsotonicRegression | LogisticRegression | PassthroughCalibrator
    config: ModelConfig
    feature_names: list[str]
    calibration_method: CalibrationMethod

    def raw_probability_fail(self, X: sparse.csr_matrix) -> np.ndarray:
        return _probability_fail(self.rf, X)

    def calibrated_probability_fail(self, X: sparse.csr_matrix) -> np.ndarray:
        raw = self.raw_probability_fail(X)
        if isinstance(self.calibrator, PassthroughCalibrator):
            return self.calibrator.predict(raw)
        if isinstance(self.calibrator, IsotonicRegression):
            return np.clip(self.calibrator.predict(raw), 0.0, 1.0)
        return np.clip(self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1], 0.0, 1.0)

    def to_bundle(self) -> dict[str, Any]:
        return {
            "algorithm": self.config.algorithm,
            "calibration_method": self.calibration_method,
            "model": self.rf,
            "calibrator": self.calibrator,
            "feature_names": self.feature_names,
            "no_call_low": self.config.no_call_low,
            "no_call_high": self.config.no_call_high,
            "hyperparameters": {
                "n_estimators": self.config.n_estimators,
                "max_depth": self.config.max_depth,
                "min_samples_leaf": self.config.min_samples_leaf,
                "class_weight": self.config.class_weight,
                "random_state": self.config.random_state,
            },
        }

    @classmethod
    def from_bundle(cls, bundle: dict[str, Any]) -> CalibratedRandomForest:
        cfg = ModelConfig(
            no_call_low=bundle["no_call_low"],
            no_call_high=bundle["no_call_high"],
        )
        method = bundle.get("calibration_method", "isotonic")
        return cls(
            rf=bundle["model"],
            calibrator=bundle["calibrator"],
            config=cfg,
            feature_names=bundle["feature_names"],
            calibration_method=method,
        )


def _probability_fail(rf: RandomForestClassifier, X: sparse.csr_matrix) -> np.ndarray:
    proba = rf.predict_proba(X)
    if proba.shape[1] == 1:
        if len(rf.classes_) == 1 and rf.classes_[0] == 1:
            return proba[:, 0]
        return np.zeros(proba.shape[0], dtype=float)
    fail_idx = list(rf.classes_).index(1)
    return proba[:, fail_idx]


def build_random_forest(config: ModelConfig) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        min_samples_leaf=config.min_samples_leaf,
        max_features=config.max_features,
        class_weight=config.class_weight,
        random_state=config.random_state,
        n_jobs=-1,
    )


def _fit_calibrator(
    raw_probs: np.ndarray,
    y_cal: np.ndarray,
    method: CalibrationMethod,
) -> IsotonicRegression | LogisticRegression | PassthroughCalibrator:
    if len(np.unique(y_cal)) < 2:
        return PassthroughCalibrator()
    if method == "sigmoid":
        lr = LogisticRegression(max_iter=2000)
        lr.fit(raw_probs.reshape(-1, 1), y_cal)
        return lr
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw_probs, y_cal)
    return iso


def _calibration_data(
    rf: RandomForestClassifier,
    X_train: sparse.csr_matrix,
    y_train: np.ndarray,
    X_cal: sparse.csr_matrix,
    y_cal: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, sparse.csr_matrix]:
    if len(np.unique(y_cal)) >= 2:
        return _probability_fail(rf, X_cal), y_cal, X_cal
    if len(np.unique(y_train)) >= 2:
        return _probability_fail(rf, X_train), y_train, X_train
    return _probability_fail(rf, X_cal), y_cal, X_cal


def train_calibrated_random_forest(
    X_train: sparse.csr_matrix,
    y_train: np.ndarray,
    X_cal: sparse.csr_matrix,
    y_cal: np.ndarray,
    feature_names: list[str],
    config: ModelConfig | None = None,
    *,
    oversample: bool = True,
) -> CalibratedRandomForest:
    cfg = config or ModelConfig()
    X_fit, y_fit = (oversample_minority(X_train, y_train, random_state=cfg.random_state) if oversample else (X_train, y_train))

    rf = build_random_forest(cfg)
    rf.fit(X_fit, y_fit)

    raw_cal, y_for_cal, _ = _calibration_data(rf, X_train, y_train, X_cal, y_cal)
    if len(np.unique(y_for_cal)) < 2:
        method: CalibrationMethod = "passthrough"
        calibrator: IsotonicRegression | LogisticRegression | PassthroughCalibrator = PassthroughCalibrator()
    else:
        method = "sigmoid" if len(y_for_cal) < cfg.sigmoid_calibration_max_n else cfg.calibration_method  # type: ignore[assignment]
        calibrator = _fit_calibrator(raw_cal, y_for_cal, method)

    return CalibratedRandomForest(
        rf=rf,
        calibrator=calibrator,
        config=cfg,
        feature_names=feature_names,
        calibration_method=method,
    )


def top_supporting_features(
    model: CalibratedRandomForest,
    x: sparse.csr_matrix,
    k: int = 5,
) -> list[str]:
    active_idx = x.nonzero()[1]
    if len(active_idx) == 0:
        return []
    importances = model.rf.feature_importances_
    ranked = sorted(active_idx, key=lambda i: importances[i], reverse=True)
    names: list[str] = []
    for idx in ranked[:k]:
        fid = model.feature_names[idx]
        if importances[idx] <= 0:
            continue
        names.append(fid)
    return names
