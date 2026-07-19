import pandas as pd
import pytest

from src.splitting.check_group_integrity import assert_group_integrity


def test_group_integrity_passes_for_disjoint_groups():
    genomes = pd.DataFrame({
        "genome_id": ["a", "b", "c"],
        "genetic_group": ["g1", "g1", "g2"],
        "split": ["train", "train", "test"],
    })
    assert assert_group_integrity(genomes)["train_genomes"] == 2


def test_group_integrity_rejects_crossing_group():
    genomes = pd.DataFrame({
        "genome_id": ["a", "b"],
        "genetic_group": ["g1", "g1"],
        "split": ["train", "test"],
    })
    with pytest.raises(ValueError, match="leakage"):
        assert_group_integrity(genomes)
