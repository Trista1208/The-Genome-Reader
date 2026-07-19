from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from src.common import read_json, write_json
from src.genome_reader.amrfinder import AMRAnnotation


def build_catalog(
    annotations_by_genome: dict[str, list[AMRAnnotation]],
    training_ids: set[str],
    min_training_genomes: int = 1,
) -> list[str]:
    counts: Counter[str] = Counter()
    for genome_id in training_ids:
        counts.update({item.feature_name for item in annotations_by_genome.get(genome_id, [])})
    return sorted(name for name, count in counts.items() if count >= min_training_genomes)


def encode_annotations(
    annotations_by_genome: dict[str, list[AMRAnnotation]],
    genome_ids: list[str],
    catalog: list[str],
) -> sparse.csr_matrix:
    feature_index = {name: index for index, name in enumerate(catalog)}
    rows: list[int] = []
    columns: list[int] = []
    for row_index, genome_id in enumerate(genome_ids):
        for name in {item.feature_name for item in annotations_by_genome.get(genome_id, [])}:
            if name in feature_index:
                rows.append(row_index)
                columns.append(feature_index[name])
    values = np.ones(len(rows), dtype=np.uint8)
    return sparse.csr_matrix((values, (rows, columns)), shape=(len(genome_ids), len(catalog)))


def save_feature_bundle(
    output_dir: str | Path,
    matrix: sparse.csr_matrix,
    sample_index: pd.DataFrame,
    catalog: list[str],
    metadata: dict,
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(output / "features.npz", matrix)
    sample_index.to_csv(output / "samples.csv", index=False)
    write_json(output / "feature_catalog.json", {"features": catalog, **metadata})


def load_feature_bundle(feature_dir: str | Path):
    feature_dir = Path(feature_dir)
    matrix = sparse.load_npz(feature_dir / "features.npz").tocsr()
    samples = pd.read_csv(feature_dir / "samples.csv", dtype={"genome_id": "string", "split": "string"})
    metadata = read_json(feature_dir / "feature_catalog.json")
    catalog = list(metadata.pop("features"))
    if matrix.shape != (len(samples), len(catalog)):
        raise ValueError("Feature matrix shape does not match samples/catalog")
    return matrix, samples, catalog, metadata
