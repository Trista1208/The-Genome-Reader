"""Synthetic-data tests for the metrics harness (hand-computed toy values)."""

import json

import numpy as np
import pytest

from pipeline import metrics as M

# Toy example: preds at threshold 0.5 -> [0,1,0,1,0,1]
# TP=2 (idx 3,5), FN=1 (idx 2), TN=2 (idx 0,4), FP=1 (idx 1)
Y = [0, 0, 1, 1, 0, 1]
P = [0.2, 0.7, 0.4, 0.8, 0.3, 0.6]


def test_binary_metrics_hand_computed():
    m = M.binary_metrics(Y, P)
    assert m["n"] == 6
    assert m["n_resistant"] == 3
    assert m["n_susceptible"] == 3
    assert m["recall_resistant"] == pytest.approx(2 / 3)
    assert m["recall_susceptible"] == pytest.approx(2 / 3)
    assert m["balanced_accuracy"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(4 / 6)  # 2TP / (2TP + FP + FN)
    # AUROC: 7 of 9 pos/neg pairs concordant
    assert m["auroc"] == pytest.approx(7 / 9)
    # Brier: (0.04 + 0.49 + 0.36 + 0.04 + 0.09 + 0.16) / 6
    assert m["brier"] == pytest.approx(1.18 / 6)
    assert not np.isnan(m["pr_auc"])


def test_binary_metrics_single_class_nan():
    m = M.binary_metrics([1, 1, 1], [0.7, 0.8, 0.9])
    assert np.isnan(m["balanced_accuracy"])
    assert np.isnan(m["auroc"])
    assert m["recall_resistant"] == pytest.approx(1.0)
    assert np.isnan(m["recall_susceptible"])


def test_nocall_metrics_hand_computed():
    mask = [False, False, True, False, False, False]
    m = M.apply_nocall_metrics(Y, P, mask)
    assert m["no_call_rate"] == pytest.approx(1 / 6)
    assert m["n_called"] == 5
    # called idx 0,1,3,4,5 -> correct except idx 1 -> 4/5
    assert m["accuracy_after_no_call"] == pytest.approx(0.8)


def test_risk_coverage_curve():
    y = [0, 1, 1, 0]
    p = [0.1, 0.9, 0.4, 0.6]  # conf: .9,.9,.6,.6; top-2 correct, bottom-2 wrong
    rc = M.risk_coverage(y, p)
    assert rc["coverage"][0] == pytest.approx(1.0)
    assert rc["accuracy"][0] == pytest.approx(0.5)   # all four
    assert rc["accuracy"][-1] == pytest.approx(1.0)  # most confident only
    # sorted non-increasing coverage
    assert all(a >= b for a, b in zip(rc["coverage"], rc["coverage"][1:]))


def test_reliability_bins():
    y = [0, 1] * 5
    p = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    rel = M.reliability_data(y, p, n_bins=10)
    assert sum(rel["count"]) == 10
    assert rel["fraction_positive"][0] == 0.0
    assert rel["fraction_positive"][-1] == 1.0
    assert len(rel["bin_edges"]) == 11


def _toy_splits(n=24):
    # 8 clusters of 3; two clusters per split tier
    names = ["train", "train", "calibration", "calibration",
             "test", "test", "heldout_group", "heldout_group"]
    splits = {}
    for i in range(n):
        cid = i // 3
        splits[f"g{i}"] = {
            "cluster_id": cid,
            "coarse_clade_id": cid,
            "split": names[cid],
        }
    return splits


def test_bootstrap_group_ci_runs_and_is_ordered():
    splits = _toy_splits()
    rng = np.random.RandomState(0)
    y = np.array([i % 2 for i in range(24)])
    p = np.clip(0.25 + 0.5 * y + rng.normal(0, 0.05, 24), 0, 1)
    groups = [splits[f"g{i}"]["cluster_id"] for i in range(24)]
    ci = M.bootstrap_group_ci(y, p, groups, n_boot=200, seed=0)
    assert ci is not None
    assert ci[0] <= ci[1]
    assert M.bootstrap_group_ci(y[:3], p[:3], [0, 0, 0]) is None  # <2 clusters


def test_evaluate_all_end_to_end(tmp_path):
    splits = _toy_splits()
    rng = np.random.RandomState(1)
    genomes = list(splits)
    y = {g: i % 2 for i, g in enumerate(genomes)}
    p = {g: float(np.clip(0.25 + 0.5 * y[g] + rng.normal(0, 0.1), 0.01, 0.99))
         for g in genomes}
    nocall = {g: (i % 7 == 0) for i, g in enumerate(genomes)}
    res = M.evaluate_all(p, y, splits, nocall, out_dir=tmp_path, n_boot=100)
    assert (tmp_path / "metrics.json").exists()
    loaded = json.loads((tmp_path / "metrics.json").read_text())
    drug = loaded["drug"]
    for split in ("train", "calibration", "test", "heldout_group"):
        assert split in drug["splits"]
        blk = drug["splits"][split]
        for key in ("balanced_accuracy", "recall_resistant", "recall_susceptible",
                    "f1", "auroc", "pr_auc", "brier", "no_call_rate",
                    "accuracy_after_no_call", "risk_coverage", "reliability",
                    "balanced_accuracy_ci95_over_clusters"):
            assert key in blk
    assert set(drug["groups"]) == {"seen", "heldout_group"}
    # hand-check one number: test split = clusters 4,5 = g12..g17;
    # nocall at i%7==0 -> i in {0,7,14,21} -> only g14 lands in test
    test = drug["splits"]["test"]
    assert test["n"] == 6
    assert test["no_call_rate"] == pytest.approx(1 / 6)
    # reliability PNG written
    assert (tmp_path / drug["reliability_png"].split("/")[-1]).exists() or \
        (tmp_path / "reliability_drug.png").exists()


def test_evaluate_all_multi_drug_dict(tmp_path):
    splits = _toy_splits()
    genomes = list(splits)
    probs = {"amp": {g: 0.3 for g in genomes}, "cip": {g: 0.6 for g in genomes}}
    labs = {"amp": {g: i % 2 for i, g in enumerate(genomes)},
            "cip": {g: (i + 1) % 2 for i, g in enumerate(genomes)}}
    res = M.evaluate_all(probs, labs, splits, None, out_dir=tmp_path, n_boot=50)
    assert set(res) == {"amp", "cip"}
    assert (tmp_path / "reliability_amp.png").exists()
    assert (tmp_path / "reliability_cip.png").exists()
