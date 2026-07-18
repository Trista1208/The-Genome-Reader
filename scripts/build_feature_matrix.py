#!/usr/bin/env python3
"""Build sparse AMR feature matrix from AMRFinderPlus TSV outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from genome_firewall.config import DEFAULT_PATHS  # noqa: E402
from genome_firewall.layer2_features.matrix import build_feature_matrix  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amrfinder-dir", type=Path, default=DEFAULT_PATHS.amrfinder_dir)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_PATHS.features_dir)
    parser.add_argument("--database", type=Path, default=DEFAULT_PATHS.amrfinder_db)
    parser.add_argument("--organism", default="Escherichia")
    args = parser.parse_args()

    genome_ids, matrix, catalog = build_feature_matrix(
        args.amrfinder_dir,
        args.out_dir,
        database=args.database,
        organism=args.organism,
    )
    print(f"Genomes: {len(genome_ids):,}")
    print(f"Features: {len(catalog):,}")
    print(f"Matrix density: {matrix.nnz / max(matrix.size, 1):.4%}")


if __name__ == "__main__":
    main()
