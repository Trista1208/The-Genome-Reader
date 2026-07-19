"""Synthetic-data tests for the two-tier split builder and audits.

Cluster layout (single linkage at ANI>=99.5 & AF>=80):

- A: g1-g2-g3-g4 chain (size 4)
- B: g5-g6-g7 chain (size 3)
- C: g8-g9 (size 2)
- D: g10-g11 (size 2)
- singletons g12, g13 (no edges)

Blocked merges: g4-g5 fails the AF gate (70 < 80), g8-g10 fails the ANI
gate (98.0 < 99.5).
"""

import pandas as pd
import pytest

from pipeline import splits as S


def make_edges() -> pd.DataFrame:
    rows = [
        ("g1", "g2", 99.8, 95.0, 96.0),
        ("g2", "g3", 99.7, 88.0, 90.0),
        ("g3", "g4", 99.9, 92.0, 91.0),
        ("g5", "g6", 99.9, 90.0, 90.0),
        ("g6", "g7", 99.6, 85.0, 87.0),
        ("g8", "g9", 99.8, 90.0, 90.0),
        ("g10", "g11", 99.9, 90.0, 90.0),
        ("g4", "g5", 99.9, 70.0, 90.0),   # AF gate blocks
        ("g8", "g10", 98.0, 95.0, 95.0),  # ANI gate blocks
    ]
    return pd.DataFrame(rows, columns=["ref", "query", "ani", "af_ref", "af_query"])


GENOMES = [f"g{i}" for i in range(1, 14)]


def make_labels():
    return {g: i % 2 for i, g in enumerate(GENOMES)}


def test_build_clusters_threshold_gates():
    clusters = S.build_clusters(make_edges(), GENOMES)
    assert len(set(clusters.values())) == 6
    by_cluster = {}
    for g, c in clusters.items():
        by_cluster.setdefault(c, set()).add(g)
    sizes = sorted(len(v) for v in by_cluster.values())
    assert sizes == [1, 1, 2, 2, 3, 4]
    # AF-gated pair NOT merged despite ANI 99.9
    assert clusters["g4"] != clusters["g5"]
    # ANI-gated pair NOT merged despite AF 95
    assert clusters["g8"] != clusters["g10"]
    # single linkage through the chain
    assert clusters["g1"] == clusters["g4"]
    assert clusters["g12"] != clusters["g13"]


def test_assign_splits_heldout_and_integrity():
    clusters = S.build_clusters(make_edges(), GENOMES)
    splits = S.assign_splits(clusters, make_labels(), n_heldout=2, seed=0)
    # CONTRACT format
    for g, entry in splits.items():
        assert set(entry) == {"cluster_id", "coarse_clade_id", "split"}
        assert entry["split"] in S.SPLIT_NAMES
        assert isinstance(entry["cluster_id"], int)
        assert isinstance(entry["coarse_clade_id"], int)
    # heldout = two largest clusters (A size 4, B size 3)
    heldout = {g for g, e in splits.items() if e["split"] == "heldout_group"}
    assert heldout == {"g1", "g2", "g3", "g4", "g5", "g6", "g7"}
    # no cluster crosses splits
    seen = {}
    for g, e in splits.items():
        assert seen.setdefault(e["cluster_id"], e["split"]) == e["split"]
    # every non-heldout cluster landed in a real split
    assert {e["split"] for e in splits.values()} >= {"train", "heldout_group"}
    # determinism
    assert splits == S.assign_splits(clusters, make_labels(), n_heldout=2, seed=0)
    # clean audit
    audit = S.audit_cross_split_leakage(splits, make_edges())
    assert audit["pass"] is True
    assert audit["crossing_clusters"] == []
    assert audit["violating_edges"] == []


def test_leakage_audit_catches_planted_clone():
    clusters = S.build_clusters(make_edges(), GENOMES)
    splits = S.assign_splits(clusters, make_labels(), n_heldout=2, seed=0)
    # plant a clone: move g1 (cluster A) into train while g2..g4 stay heldout
    splits["g1"]["split"] = "train"
    audit = S.audit_cross_split_leakage(splits, make_edges())
    assert audit["pass"] is False
    assert clusters["g1"] in audit["crossing_clusters"]
    assert audit["max_ani_train_vs_heldout"] == pytest.approx(99.8)
    assert any(
        {e["ref"], e["query"]} == {"g1", "g2"} for e in audit["violating_edges"]
    )


def test_audit_max_ani_none_when_no_edges():
    clusters = S.build_clusters(make_edges(), GENOMES)
    splits = S.assign_splits(clusters, make_labels(), n_heldout=2, seed=0)
    audit = S.audit_cross_split_leakage(splits, None)
    assert audit["pass"] is True
    assert audit["max_ani_train_vs_heldout"] is None


def test_cassette_audit_reports_shared_resistant_features():
    fm = pd.DataFrame(
        {
            "blaTEM": [1, 0, 0, 0],
            "blaCTX-M": [1, 0, 1, 0],
            "blaKPC": [0, 0, 1, 0],
            "aac3": [0, 1, 0, 1],
        },
        index=["g1", "g2", "g8", "g9"],
    )
    labels = {"g1": 1, "g2": 0, "g8": 1, "g9": 0}
    splits = {
        "g1": {"cluster_id": 0, "coarse_clade_id": 0, "split": "train"},
        "g2": {"cluster_id": 0, "coarse_clade_id": 0, "split": "train"},
        "g8": {"cluster_id": 2, "coarse_clade_id": 2, "split": "heldout_group"},
        "g9": {"cluster_id": 2, "coarse_clade_id": 2, "split": "heldout_group"},
    }
    rep = S.audit_cassette_sharing(fm, labels, splits)
    assert rep["shared_features"] == ["blaCTX-M"]
    assert rep["n_shared"] == 1
    assert rep["n_union"] == 3
    assert rep["jaccard"] == pytest.approx(1 / 3)
