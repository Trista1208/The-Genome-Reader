"""Abstention ("no-call") layer for Genome Firewall.

Two independent mechanisms, combined by OR:

(a) Class-conditional (Mondrian) split-conformal with ASYMMETRIC alpha per
    side — susceptible-side alpha_s=0.02 (a "likely to work" call may be wrong
    at most ~2% of the time on exchangeable data), resistant-side
    alpha_r=0.10. Nonconformity for the true class c is 1 - P(c); per-class
    conformal quantiles give band edges [1 - q_R, q_S]; a genome is CALLED
    only when its prediction set has exactly one member.

    crepes 0.9.1 was evaluated for this (installs cleanly) but its
    ``predict_set`` takes a single global eps — there is no per-class
    asymmetric alpha, and it does not expose pure (p, band) edges, which the
    frozen protocol requires ("submit probabilities for everything; calls are
    a pure function of (p, threshold, band)"). Hence the direct ~30-line
    implementation below.

(b) ANI-distance-to-nearest-training-genome hard OOD override: conformal is
    silent exactly on confident-wrong unseen-lineage errors, so any genome
    farther from the training set than a quantile-derived threshold is forced
    to no-call regardless of p.

Everything downstream of fitting is a pure function of (p, band, distance),
so probabilities can be stored/submitted for ALL genomes and calls re-derived
without the model.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

DEFAULT_ALPHA_SUSCEPTIBLE = 0.02
DEFAULT_ALPHA_RESISTANT = 0.10
DEFAULT_DIST_QUANTILE = 0.99


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Split-conformal quantile with finite-sample correction.

    k = ceil((n + 1) * (1 - alpha)), capped at n; returns the k-th smallest
    score (np.inf when the cap still under-covers, i.e. impossible alpha).
    """
    scores = np.sort(np.asarray(scores, dtype=float))
    n = len(scores)
    if n == 0:
        raise ValueError("need at least one calibration score")
    k = min(math.ceil((n + 1) * (1 - alpha)), n)
    return float(scores[k - 1])


@dataclass
class NoCallBands:
    """Fitted no-call parameters for ONE drug. Serializable to JSON."""

    q_susceptible: float            # conformal quantile of p | y=0
    q_resistant: float              # conformal quantile of 1-p | y=1
    alpha_susceptible: float = DEFAULT_ALPHA_SUSCEPTIBLE
    alpha_resistant: float = DEFAULT_ALPHA_RESISTANT
    dist_threshold: float | None = None
    dist_quantile: float = DEFAULT_DIST_QUANTILE

    @property
    def band(self) -> tuple[float, float]:
        """Acceptance edges [lo, hi]: S-call below lo, R-call above hi."""
        return (1.0 - self.q_resistant, self.q_susceptible)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["band"] = list(self.band)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NoCallBands":
        d = {k: v for k, v in d.items() if k != "band"}
        return cls(**d)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1) + "\n")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "NoCallBands":
        return cls.from_dict(json.loads(Path(path).read_text()))


def fit_conformal_bands(
    cal_probs,
    cal_labels,
    alpha_susceptible: float = DEFAULT_ALPHA_SUSCEPTIBLE,
    alpha_resistant: float = DEFAULT_ALPHA_RESISTANT,
) -> NoCallBands:
    """Class-conditional split-conformal bands from calibration data."""
    p = np.asarray(cal_probs, dtype=float)
    y = np.asarray(cal_labels, dtype=int)
    if p.shape != y.shape:
        raise ValueError("cal_probs and cal_labels must align")
    if not ((y == 0).any() and (y == 1).any()):
        raise ValueError("calibration set needs both classes")
    q_s = _conformal_quantile(p[y == 0], alpha_susceptible)        # score for class 0 is p
    q_r = _conformal_quantile(1.0 - p[y == 1], alpha_resistant)    # score for class 1 is 1-p
    return NoCallBands(q_s, q_r, alpha_susceptible, alpha_resistant)


def prediction_sets(p, bands: NoCallBands) -> np.ndarray:
    """Per-genome prediction set bitmask: bit0 = {S}, bit1 = {R}."""
    p = np.asarray(p, dtype=float)
    include_s = p <= bands.q_susceptible
    include_r = (1.0 - p) <= bands.q_resistant
    return include_s.astype(int) + 2 * include_r.astype(int)


def fit_distance_threshold(
    reference_distances,
    quantile: float = DEFAULT_DIST_QUANTILE,
) -> float:
    """Quantile-derived OOD threshold.

    ``reference_distances`` = each calibration/validation genome's skani
    distance (100 - ANI) to its nearest TRAINING genome. Genomes beyond the
    chosen quantile of that distribution are "further than anything we were
    right about" and get forced no-call.
    """
    d = np.asarray(reference_distances, dtype=float)
    if len(d) == 0:
        raise ValueError("need reference distances")
    return float(np.quantile(d, quantile))


def apply_nocall(p, bands: NoCallBands, distances=None,
                 dist_threshold: float | None = None) -> np.ndarray:
    """Pure combined no-call mask. True = NO-CALL.

    No-call when the conformal prediction set is not a singleton (ambiguous
    or empty), OR when ``distances`` exceeds the threshold (fitted one stored
    on the bands unless overridden).
    """
    p = np.asarray(p, dtype=float)
    sets = prediction_sets(p, bands)
    mask = (sets == 0) | (sets == 3)
    thr = dist_threshold if dist_threshold is not None else bands.dist_threshold
    if distances is not None:
        if thr is None:
            raise ValueError("distances given but no dist_threshold fitted/passed")
        mask = mask | (np.asarray(distances, dtype=float) > thr)
    return mask
