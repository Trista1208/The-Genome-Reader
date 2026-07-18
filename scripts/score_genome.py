#!/usr/bin/env python3
"""Score one genome and emit JSON (backend API output for frontend)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from genome_firewall.services.inference_service import InferenceService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("genome_id", help="Genome ID (must exist in feature store or AMRFinder output)")
    parser.add_argument(
        "--amrfinder-tsv",
        type=Path,
        default=None,
        help="AMRFinderPlus TSV (default: data/processed/amrfinder/{genome_id}.tsv)",
    )
    parser.add_argument("--fasta", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Write JSON report to file")
    args = parser.parse_args()

    svc = InferenceService()
    tsv = args.amrfinder_tsv or Path(f"data/processed/amrfinder/{args.genome_id}.tsv")
    fasta = args.fasta or Path(f"data/raw/bvbrc/genomes/{args.genome_id}.fna")

    if tsv.exists():
        report = svc.score_from_amrfinder_tsv(
            args.genome_id,
            tsv,
            fasta=fasta if fasta.exists() else None,
        )
    else:
        report = svc.score_from_feature_row(args.genome_id)

    payload = report.to_dict()
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
        print(f"Wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
