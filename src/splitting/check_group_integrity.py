from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VALID_SPLITS = {"train", "calibration", "test"}


def load_genomes(path: str | Path) -> pd.DataFrame:
    genomes = pd.read_csv(path, dtype={"genome_id": "string", "genetic_group": "string", "split": "string"})
    required = {"genome_id", "genetic_group", "split"}
    missing = required - set(genomes.columns)
    if missing:
        raise ValueError(f"Genome table is missing columns: {sorted(missing)}")
    if genomes["genome_id"].isna().any() or genomes["genome_id"].duplicated().any():
        raise ValueError("genome_id must be non-null and unique in the genome table")
    unknown = set(genomes["split"].dropna().unique()) - VALID_SPLITS
    if unknown:
        raise ValueError(f"Unknown split values: {sorted(unknown)}")
    if genomes[["genetic_group", "split"]].isna().any().any():
        raise ValueError("genetic_group and split must be populated for every genome")
    return genomes


def assert_group_integrity(genomes: pd.DataFrame) -> dict[str, int]:
    crossings = genomes.groupby("genetic_group", observed=True)["split"].nunique()
    bad = crossings[crossings > 1]
    if not bad.empty:
        examples = bad.index.astype(str).tolist()[:10]
        raise ValueError(f"Genetic-group leakage detected in {len(bad)} groups; examples: {examples}")
    counts = genomes.groupby("split", observed=True).agg(
        genomes=("genome_id", "nunique"), genetic_groups=("genetic_group", "nunique")
    )
    return {
        f"{split}_{metric}": int(value)
        for split, row in counts.iterrows()
        for metric, value in row.items()
    }


def assert_label_integrity(labels_path: str | Path, genomes: pd.DataFrame) -> pd.DataFrame:
    labels = pd.read_csv(
        labels_path,
        dtype={"genome_id": "string", "genetic_group": "string", "split": "string", "antibiotic": "string"},
    )
    required = {"genome_id", "antibiotic", "target_resistant", "split", "genetic_group"}
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"Label table is missing columns: {sorted(missing)}")
    if labels.duplicated(["genome_id", "antibiotic"]).any():
        raise ValueError("Duplicate genome-antibiotic labels detected")
    if not set(labels["target_resistant"].dropna().astype(int).unique()) <= {0, 1}:
        raise ValueError("target_resistant must contain only 0/1")
    reference = genomes.set_index("genome_id")[["split", "genetic_group"]]
    joined = labels.join(reference, on="genome_id", rsuffix="_genomes", validate="many_to_one")
    if joined["split_genomes"].isna().any():
        ids = joined.loc[joined["split_genomes"].isna(), "genome_id"].astype(str).unique()[:10]
        raise ValueError(f"Labels reference missing genome IDs: {ids.tolist()}")
    mismatch = (joined["split"] != joined["split_genomes"]) | (
        joined["genetic_group"] != joined["genetic_group_genomes"]
    )
    if mismatch.any():
        raise ValueError("Label split/genetic_group values do not match the genome table")
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Genome Firewall precomputed splits.")
    parser.add_argument("--genomes", required=True)
    parser.add_argument("--labels")
    args = parser.parse_args()
    genomes = load_genomes(args.genomes)
    result = assert_group_integrity(genomes)
    if args.labels:
        labels = assert_label_integrity(args.labels, genomes)
        result["labels"] = len(labels)
    print("Group-integrity check passed")
    for key, value in sorted(result.items()):
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
