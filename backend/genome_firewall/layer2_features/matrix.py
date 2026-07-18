from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from genome_firewall.layer1_ingestion.cohort import normalize_genome_id


def normalize_field(value: str | None) -> str:
    s = (value or "").strip().lower()
    return s if s else "na"


def feature_id_from_row(row: dict[str, str]) -> str:
    parts = [
        normalize_field(row.get("Element symbol") or row.get("Gene symbol")),
        normalize_field(row.get("Element name")),
        normalize_field(row.get("Subtype")),
        normalize_field(row.get("Method")),
    ]
    return "|".join(parts)


def parse_amrfinder_tsv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            fid = feature_id_from_row(row)
            if fid == "na|na|na|na":
                continue
            rows.append(
                {
                    "feature_id": fid,
                    "element_symbol": row.get("Element symbol") or row.get("Gene symbol") or "",
                    "element_name": row.get("Element name") or "",
                    "scope": row.get("Scope") or "",
                    "type": row.get("Type") or "",
                    "subtype": row.get("Subtype") or "",
                    "class": row.get("Class") or "",
                    "subclass": row.get("Subclass") or "",
                    "method": row.get("Method") or "",
                }
            )
    return rows


def load_feature_store(
    feature_dir: Path,
) -> tuple[list[str], sparse.csr_matrix, pd.DataFrame]:
    index = pd.read_csv(feature_dir / "genome_index.tsv", sep="\t", dtype={"genome_id": str})
    genome_ids = [normalize_genome_id(g) for g in index["genome_id"].tolist()]
    matrix = sparse.load_npz(feature_dir / "feature_matrix.npz")
    catalog = pd.read_csv(feature_dir / "feature_catalog.tsv", sep="\t")
    return genome_ids, matrix, catalog


def vectorize_hits(
    hits: list[dict[str, str]],
    catalog: pd.DataFrame,
) -> sparse.csr_matrix:
    feat_index = {fid: i for i, fid in enumerate(catalog["feature_id"].tolist())}
    n = len(feat_index)
    cols = sorted({feat_index[h["feature_id"]] for h in hits if h["feature_id"] in feat_index})
    row = np.zeros(n, dtype=np.int8)
    if cols:
        row[cols] = 1
    return sparse.csr_matrix(row)


def build_feature_matrix(
    amrfinder_dir: Path,
    out_dir: Path,
    *,
    database: Path,
    organism: str,
) -> tuple[list[str], sparse.csr_matrix, pd.DataFrame]:
    from datetime import datetime, timezone
    import json

    tsv_files = sorted(amrfinder_dir.glob("*.tsv"))
    if not tsv_files:
        raise FileNotFoundError(f"No AMRFinderPlus TSV files in {amrfinder_dir}")

    genome_ids: list[str] = []
    feature_rows: dict[str, dict[str, str]] = {}
    genome_features: dict[str, set[str]] = {}

    for tsv in tsv_files:
        gid = normalize_genome_id(tsv.stem)
        genome_ids.append(gid)
        hits = parse_amrfinder_tsv(tsv)
        fset = {h["feature_id"] for h in hits}
        for hit in hits:
            feature_rows.setdefault(hit["feature_id"], hit)
        genome_features[gid] = fset

    genome_ids = sorted(set(genome_ids))
    feature_ids = sorted(feature_rows.keys())
    feat_index = {fid: i for i, fid in enumerate(feature_ids)}

    row_idx: list[int] = []
    col_idx: list[int] = []
    for row_i, gid in enumerate(genome_ids):
        for fid in genome_features.get(gid, set()):
            row_idx.append(row_i)
            col_idx.append(feat_index[fid])

    matrix = sparse.csr_matrix(
        (np.ones(len(row_idx), dtype=np.int8), (row_idx, col_idx)),
        shape=(len(genome_ids), len(feature_ids)),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = pd.DataFrame(
        [feature_rows[fid] for fid in feature_ids],
        columns=[
            "feature_id",
            "element_symbol",
            "element_name",
            "scope",
            "type",
            "subtype",
            "class",
            "subclass",
            "method",
        ],
    )
    catalog.to_csv(out_dir / "feature_catalog.tsv", sep="\t", index=False)
    sparse.save_npz(out_dir / "feature_matrix.npz", matrix)
    pd.DataFrame({"genome_id": genome_ids, "matrix_row": range(len(genome_ids))}).to_csv(
        out_dir / "genome_index.tsv", sep="\t", index=False
    )
    manifest = {
        "schema_version": "1.0",
        "n_genomes": len(genome_ids),
        "n_features": len(feature_ids),
        "amrfinder_db": str(database),
        "organism": organism,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return genome_ids, matrix, catalog
