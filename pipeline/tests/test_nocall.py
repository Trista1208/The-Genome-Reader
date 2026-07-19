"""Synthetic-data tests for the no-call layer (conformal + distance override)."""

import numpy as np
import pytest

from pipeline import nocall as N


@pytest.fixture
def det_bands():
    """Deterministic calibration set, 20 per class.

    y=0: p = 0.01..0.20 -> q_S: k = ceil(21*0.98) = 21 -> capped at 20 -> max = 0.20
    y=1: p = 0.80..0.99 -> scores 1-p = 0.01..0.20 -> k = ceil(21*0.90) = 19
         -> 19th smallest = 0.19 -> q_R = 0.19
    """
    p = np.concatenate([np.linspace(0.01, 0.20, 20), np.linspace(0.80, 0.99, 20)])
    y = np.array([0] * 20 + [1] * 20)
    return N.fit_conformal_bands(p, y)


def test_conformal_quantiles_exact(det_bands):
    assert det_bands.q_susceptible == pytest.approx(0.20)
    assert det_bands.q_resistant == pytest.approx(0.19)
    assert det_bands.alpha_susceptible == 0.02 < det_bands.alpha_resistant == 0.10
    lo, hi = det_bands.band
    # normalized (work_below, fail_above): gap geometry, no-call in between
    assert (lo, hi) == (pytest.approx(0.20), pytest.approx(0.81))


def test_mask_behavior(det_bands):
    p = np.array([0.05, 0.20, 0.50, 0.75, 0.81, 0.90])
    mask = N.apply_nocall(p, det_bands)
    # called S, called S (boundary), gap no-call, gap no-call, called R, called R
    assert mask.tolist() == [False, False, True, True, False, False]


def test_ambiguous_set_is_nocall():
    # overlapping bands -> mid p belongs to BOTH class sets -> no-call
    bands = N.NoCallBands(q_susceptible=0.60, q_resistant=0.55)
    mask = N.apply_nocall(np.array([0.50]), bands)
    assert mask.tolist() == [True]


def test_distance_override_fires():
    bands = N.NoCallBands(q_susceptible=0.20, q_resistant=0.19, dist_threshold=0.01)
    p = np.array([0.05, 0.99])           # both confidently callable by conformal
    d = np.array([0.001, 0.05])          # second is far from training
    mask = N.apply_nocall(p, bands, distances=d)
    assert mask.tolist() == [False, True]
    # near genomes unaffected
    assert not N.apply_nocall(p, bands, distances=np.array([0.001, 0.009])).any()
    # distances without a threshold -> error
    with pytest.raises(ValueError):
        N.apply_nocall(p, N.NoCallBands(0.20, 0.19), distances=d)


def test_distance_threshold_quantile():
    d = np.arange(1, 101, dtype=float)
    assert N.fit_distance_threshold(d, 0.90) == pytest.approx(90.1)


def test_seeded_error_rates_respect_asymmetry():
    rng = np.random.RandomState(42)
    n = 400
    cal_p = np.concatenate([rng.beta(1, 10, n), rng.beta(10, 1, n)])
    cal_y = np.array([0] * n + [1] * n)
    bands = N.fit_conformal_bands(cal_p, cal_y)
    test_p = np.concatenate([rng.beta(1, 10, n), rng.beta(10, 1, n)])
    test_y = np.array([0] * n + [1] * n)
    mask = N.apply_nocall(test_p, bands)
    called = ~mask
    called_s = called & (test_p < 0.5)
    called_r = called & (test_p >= 0.5)
    err_s = float((test_y[called_s] == 1).mean()) if called_s.any() else 0.0
    err_r = float((test_y[called_r] == 0).mean()) if called_r.any() else 0.0
    assert err_s <= 0.05    # alpha_S = 0.02 with slack
    assert err_r <= 0.15    # alpha_R = 0.10 with slack
    assert mask.mean() < 0.5  # sane no-call rate on in-distribution data


def test_bands_roundtrip(tmp_path, det_bands):
    det_bands.dist_threshold = 0.01
    path = det_bands.save(tmp_path / "nocall.json")
    loaded = N.NoCallBands.load(path)
    assert loaded == det_bands
    assert loaded.band == det_bands.band
