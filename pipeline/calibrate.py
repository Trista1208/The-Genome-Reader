"""Platt/sigmoid calibration for Genome Firewall per-drug models.

Uses CalibratedClassifierCV around a FrozenEstimator (sklearn >= 1.6 pattern):
the base estimator is ALREADY FIT on train and frozen; only the 2-parameter
sigmoid is learned on the calibration split.

Isotonic is deliberately NOT used: at this calibration-set size (a few
hundred genomes over ~30 effective ANI clusters) isotonic's nonparametric
step fit has far too many effective degrees of freedom — it overfits the
calibration fold and degrades on heldout_group, where the whole point is
unseen-lineage generalization. The sigmoid's 2 parameters are the right
capacity for this n.
"""

from __future__ import annotations

from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator


def platt_calibrate(estimator, X_cal, y_cal) -> CalibratedClassifierCV:
    """Fit a sigmoid on top of an already-fitted binary ``estimator``.

    ``estimator`` must be fitted (e.g. elastic-net LogisticRegression from
    the train split) and is not retrained; X_cal/y_cal come from the
    calibration split only. Returns the fitted CalibratedClassifierCV whose
    ``predict_proba(X)[:, 1]`` is the calibrated P(resistant).
    """
    cal = CalibratedClassifierCV(FrozenEstimator(estimator), method="sigmoid")
    cal.fit(X_cal, y_cal)
    return cal
