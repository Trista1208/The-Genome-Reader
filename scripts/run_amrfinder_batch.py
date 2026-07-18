#!/usr/bin/env python3
"""Batch-run AMRFinderPlus (nucleotide mode) on cohort FASTA files."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_amrfinder_bin() -> Path:
    return repo_root() / "tools/bin/amrfinder"


def default_db_dir() -> Path:
    return repo_root() / "data/raw/amrfinderplus/latest"


def run_one(
    fasta: Path,
    out_tsv: Path,
    amrfinder: Path,
    db_dir: Path,
    organism: str,
    threads: int,
) -> tuple[str, str]:
    genome_id = fasta.stem
    if out_tsv.exists() and out_tsv.stat().st_size > 0:
        return genome_id, "skip"

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(amrfinder),
        "-n",
        str(fasta),
        "-o",
        str(out_tsv),
        "-d",
        str(db_dir),
        "-O",
        organism,
        "--threads",
        str(threads),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error").strip().splitlines()[-1]
        return genome_id, f"fail: {err}"
    return genome_id, "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fasta-dir",
        type=Path,
        default=Path("data/raw/bvbrc/genomes"),
        help="Directory of {genome_id}.fna files",
    )
    parser.add_argument(
        "--genome-list",
        type=Path,
        default=Path("data/processed/cohort/genome_list.txt"),
        help="Optional genome ID list (default: all *.fna in --fasta-dir)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/amrfinder"),
    )
    parser.add_argument("--organism", default="Escherichia")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="Process at most N genomes (0=all)")
    parser.add_argument(
        "--labeled-first",
        action="store_true",
        help="Prioritize genomes that appear in lab labels and lack AMRFinder output",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/cohort/genome_antibiotic_labels.tsv"),
    )
    parser.add_argument(
        "--amrfinder",
        type=Path,
        default=default_amrfinder_bin(),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=default_db_dir(),
    )
    args = parser.parse_args()

    if not args.amrfinder.exists():
        raise SystemExit(
            f"AMRFinderPlus binary not found at {args.amrfinder}. "
            "Run: bash scripts/setup_amrfinder.sh"
        )
    if not args.database.exists():
        raise SystemExit(
            f"AMRFinderPlus database not found at {args.database}. "
            "Run: python3 scripts/download_amrfinder_db.py && bash scripts/setup_amrfinder.sh"
        )

    if args.genome_list.exists():
        genome_ids = [
            line.strip()
            for line in args.genome_list.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        genome_ids = sorted(p.stem for p in args.fasta_dir.glob("*.fna"))

    jobs: list[tuple[Path, Path]] = []
    for gid in genome_ids:
        fasta = args.fasta_dir / f"{gid}.fna"
        if not fasta.exists():
            continue
        jobs.append((fasta, args.out_dir / f"{gid}.tsv"))

    if args.labeled_first and args.labels.exists():
        labeled = {
            line.split("\t")[0]
            for line in args.labels.read_text().splitlines()[1:]
            if line.strip()
        }
        pending = [j for j in jobs if j[0].stem in labeled and not j[1].exists()]
        done = [j for j in jobs if j not in pending]
        jobs = pending + done
        print(f"Prioritized {len(pending)} labeled genomes without AMRFinder output")

    if args.limit:
        jobs = jobs[: args.limit]

    if not jobs:
        raise SystemExit("No FASTA files found to process.")

    print(f"AMRFinderPlus batch: {len(jobs)} genomes, workers={args.workers}")
    ok = skip = fail = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                run_one,
                fasta,
                out_tsv,
                args.amrfinder,
                args.database,
                args.organism,
                args.threads,
            ): fasta.stem
            for fasta, out_tsv in jobs
        }
        for i, fut in enumerate(as_completed(futures), 1):
            gid, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                print(f"[fail] {gid}: {status}", file=sys.stderr)
            if i % 25 == 0 or i == len(jobs):
                print(f"  progress {i}/{len(jobs)} (ok={ok}, skip={skip}, fail={fail})")

    print(f"Done. ok={ok}, skip={skip}, fail={fail}, out={args.out_dir}")


if __name__ == "__main__":
    main()
