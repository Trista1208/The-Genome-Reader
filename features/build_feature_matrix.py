#!/usr/bin/env python3
"""build_feature_matrix.py — AMRFinderPlus v4 TSVs -> binary feature matrix.

Per CONTRACT.md (features/feature_matrix.csv): first column ``genome_id``,
remaining columns binary (0/1) presence of AMRFinderPlus "Element symbol"
entries, with the three evidence tiers as separate column families:

  - ``<symbol>``        full/called hit (EXACT / ALLELE / BLAST methods)
  - ``POINT:<symbol>``  curated point mutation (Subtype POINT / POINT_DISRUPT)
  - ``DEG:<symbol>``    degraded evidence (PARTIAL / PARTIAL_CONTIG_END /
                        INTERNAL_STOP / HMM methods)

All scopes/types are kept (the batch runs ``amrfinder -O Escherichia --plus``,
so plus-scope STRESS/VIRULENCE elements are present); per-type counts are
recorded in metadata.json so downstream can filter if desired.

Method suffixes (X/P/N search-type) are stripped before tiering, matching
features/map_evidence.py:method_base.

Usage:
  python features/build_feature_matrix.py \
      --file-list /tmp/amrfinder_snapshot.txt \
      --out features/feature_matrix.csv --metadata features/metadata.json

Without --file-list, every *.tsv in --tsv-dir is used (glob order).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

POINT_SUBTYPES = {"POINT", "POINT_DISRUPT"}
DEGRADED_METHODS = {"PARTIAL", "PARTIAL_CONTIG_END", "INTERNAL_STOP", "HMM"}

# Batch provenance (docker ps, 2026-07-19): staphb/ncbi-amrfinderplus image,
# command `amrfinder -n <genome>.fna -O Escherichia --plus --threads 2`.
TOOL_PROVENANCE = {
    "tool": "NCBI AMRFinderPlus",
    "tool_version": "4.2.7",
    "database_version": "2026-03-24.1",
    "docker_image": "staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1",
    "organism_option": "Escherichia",
    "plus_scope": True,
    "command_template": "amrfinder -n {genome}.fna -O Escherichia --plus -o {genome}.tsv",
}


def method_base(method: str) -> str:
    """Strip the X/P/N search-type suffix (EXACTX->EXACT, POINTN->POINT)."""
    m = method.strip().upper()
    if m.endswith(("X", "P", "N")) and m[:-1] in (
        {"EXACT", "ALLELE", "BLAST", "POINT"} | DEGRADED_METHODS
    ):
        return m[:-1]
    return m


def feature_name(symbol: str, subtype: str, method: str) -> str:
    """Column name for one hit: tier prefix + Element symbol."""
    symbol = symbol.strip()
    if subtype.strip().upper() in POINT_SUBTYPES or method_base(method) == "POINT":
        return f"POINT:{symbol}"
    if method_base(method) in DEGRADED_METHODS:
        return f"DEG:{symbol}"
    return symbol


def parse_tsv(path: Path, counts: Counter) -> set[str]:
    """One TSV -> set of feature names. Updates running ``counts``."""
    feats: set[str] = set()
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        missing = {"Element symbol", "Subtype", "Method", "Type"} - set(
            reader.fieldnames or []
        )
        if missing:
            raise ValueError(f"{path}: not an AMRFinderPlus v4 TSV — missing {sorted(missing)}")
        for row in reader:
            symbol = (row.get("Element symbol") or "").strip()
            if not symbol:
                continue
            f = feature_name(symbol, row.get("Subtype", ""), row.get("Method", ""))
            feats.add(f)
            counts[f"type:{(row.get('Type') or '').strip()}"] += 1
            counts[f"subtype:{(row.get('Subtype') or '').strip()}"] += 1
            counts[f"method:{method_base(row.get('Method', ''))}"] += 1
    return feats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tsv-dir", default="features/amrfinder",
                    help="dir of AMRFinderPlus TSVs (default: features/amrfinder)")
    ap.add_argument("--file-list", default=None,
                    help="text file with one TSV path per line (snapshot); "
                         "default: all *.tsv in --tsv-dir")
    ap.add_argument("--out", default="features/feature_matrix.csv")
    ap.add_argument("--metadata", default="features/metadata.json")
    args = ap.parse_args(argv)

    if args.file_list:
        paths = [Path(line.strip()) for line in
                 Path(args.file_list).read_text().splitlines() if line.strip()]
    else:
        paths = sorted(Path(args.tsv_dir).glob("*.tsv"))
    if not paths:
        print("error: no TSVs found", file=sys.stderr)
        return 2

    counts: Counter = Counter()
    rows: dict[str, set[str]] = {}
    skipped: list[str] = []
    for p in paths:
        gid = p.stem
        try:
            rows[gid] = parse_tsv(p, counts)
        except (OSError, ValueError) as e:
            print(f"warning: skipping {p}: {e}", file=sys.stderr)
            skipped.append(str(p))

    all_feats = sorted({f for feats in rows.values() for f in feats})
    mat = pd.DataFrame(
        [[1 if f in rows[g] else 0 for f in all_feats] for g in sorted(rows)],
        index=pd.Index(sorted(rows), name="genome_id"),
        columns=all_feats,
        dtype="uint8",
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mat.to_csv(out)

    n_point = sum(1 for f in all_feats if f.startswith("POINT:"))
    n_deg = sum(1 for f in all_feats if f.startswith("DEG:"))
    metadata = {
        **TOOL_PROVENANCE,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_file_list": args.file_list,
        "n_genomes": int(len(mat)),
        "n_features": int(len(all_feats)),
        "n_plain_features": len(all_feats) - n_point - n_deg,
        "n_point_features": n_point,
        "n_degraded_features": n_deg,
        "n_genomes_zero_hits": int((mat.sum(axis=1) == 0).sum()),
        "skipped_files": skipped,
        "hit_counts": {k: v for k, v in sorted(counts.items())},
    }
    meta_path = Path(args.metadata)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=1) + "\n")

    print(f"wrote {out}: {mat.shape[0]} genomes x {mat.shape[1]} features "
          f"({n_point} POINT, {n_deg} DEG); metadata -> {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
