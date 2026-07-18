from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT
    labels: Path = ROOT / "data/processed/cohort/genome_antibiotic_labels.tsv"
    genome_list: Path = ROOT / "data/processed/cohort/genome_list.txt"
    fasta_dir: Path = ROOT / "data/raw/bvbrc/genomes"
    amrfinder_dir: Path = ROOT / "data/processed/amrfinder"
    features_dir: Path = ROOT / "data/processed/features"
    splits_dir: Path = ROOT / "data/processed/splits"
    models_dir: Path = ROOT / "data/processed/models"
    drug_targets: Path = ROOT / "data/reference/drug_targets.json"
    amrfinder_db: Path = ROOT / "data/raw/amrfinderplus/latest"
    amrfinder_bin: Path = ROOT / "tools/bin/amrfinder"


@dataclass(frozen=True)
class ModelConfig:
    algorithm: str = "random_forest"
    n_estimators: int = 300
    max_depth: int | None = 12
    min_samples_leaf: int = 5
    max_features: str = "sqrt"
    class_weight: str = "balanced"
    random_state: int = 42
    calibration_method: str = "isotonic"
    sigmoid_calibration_max_n: int = 25
    no_call_low: float = 0.35
    no_call_high: float = 0.65
    min_train_per_class: int = 2
    min_test_per_class: int = 1


DEFAULT_PATHS = Paths()
DEFAULT_MODEL = ModelConfig()
