"""Synthetic-data tests for Platt calibration (FrozenEstimator pattern)."""

import numpy as np
from sklearn.linear_model import LogisticRegression

from pipeline.calibrate import platt_calibrate


def _data(seed=0, n=200, shift=0.0):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 3)
    y = (X[:, 0] + shift + rng.randn(n) * 0.5 > 0).astype(int)
    return X, y


def test_platt_calibrate_frozen():
    X_tr, y_tr = _data(seed=0)
    X_cal, y_cal = _data(seed=1)
    base = LogisticRegression().fit(X_tr, y_tr)
    proba_before = base.predict_proba(X_cal)[:, 1].copy()

    cal = platt_calibrate(base, X_cal, y_cal)
    p = cal.predict_proba(X_cal)[:, 1]

    assert p.shape == (len(y_cal),)
    assert ((p >= 0) & (p <= 1)).all()
    # base estimator was frozen, not refit
    np.testing.assert_allclose(base.predict_proba(X_cal)[:, 1], proba_before)
    # sigmoid is monotone in the base model's raw probability
    order = np.argsort(proba_before)
    diffs = np.diff(p[order])
    assert (diffs >= -1e-9).all()


def test_platt_calibrate_uses_cal_split_only():
    X_tr, y_tr = _data(seed=0)
    # calibration distribution shifted: base model is systematically off here
    X_cal, y_cal = _data(seed=2, shift=-1.0)
    base = LogisticRegression().fit(X_tr, y_tr)
    cal = platt_calibrate(base, X_cal, y_cal)
    # a fitted sigmoid on shifted cal data should move probabilities
    p_raw = base.predict_proba(X_cal)[:, 1]
    p_cal = cal.predict_proba(X_cal)[:, 1]
    assert not np.allclose(p_raw, p_cal)
