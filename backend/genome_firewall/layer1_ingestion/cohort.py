from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd


def normalize_genome_id(raw: str | float) -> str:
    """Keep BV-BRC genome IDs stable (avoid float truncation like 562.144150 → 562.14415)."""
    return str(raw).strip()


def load_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype={"genome_id": str})
    df["genome_id"] = df["genome_id"].map(normalize_genome_id)
    df["y"] = (df["label"] == "likely_to_fail").astype(int)
    return df


def load_genome_list(path: Path) -> list[str]:
    return [
        normalize_genome_id(line)
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_split(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            out[normalize_genome_id(row["genome_id"])] = row["split"]
    return out


def load_drug_targets(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text())
    return {name: meta["required_genes"] for name, meta in data["drugs"].items()}


def load_cohort_summary(path: Path) -> dict:
    return json.loads(path.read_text())
