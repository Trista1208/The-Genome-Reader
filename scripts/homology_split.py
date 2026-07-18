#!/usr/bin/env python3
"""Cluster genomes by sequence similarity and assign train/cal/test splits."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from Bio import SeqIO
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from genome_firewall.layer1_ingestion.cohort import normalize_genome_id


def iter_kmers(seq: str, k: int = 21) -> set[str]:
    seq = seq.upper()
    valid = set("ACGT")
    out: set[str] = set()
    for i in range(len(seq) - k + 1):
        mer = seq[i : i + k]
        if all(b in valid for b in mer):
            out.add(mer)
    return out


SEEDS = np.random.default_rng(42).integers(1, np.iinfo(np.uint32).max, size=128, dtype=np.uint32)


def minhash_signature(kmers: set[str], n_perm: int = 128) -> np.ndarray:
    if not kmers:
        return np.full(n_perm, np.iinfo(np.uint64).max, dtype=np.uint64)
    sig = np.full(n_perm, np.iinfo(np.uint64).max, dtype=np.uint64)
    seeds = SEEDS[:n_perm]
    for mer in kmers:
        h = hash(mer) & np.iinfo(np.uint64).max
        sig = np.minimum(sig, (h ^ seeds.astype(np.uint64)))
    return sig


def mash_distance(a: np.ndarray, b: np.ndarray, k: int = 21) -> float:
    shared = np.sum(a == b)
    if shared == 0:
        return 1.0
    jaccard_est = shared / len(a)
    return max(0.0, -np.log(2 * jaccard_est / (1 + jaccard_est)) / k)


def genome_signature(fasta: Path, k: int, n_perm: int) -> np.ndarray:
    kmers: set[str] = set()
    for rec in SeqIO.parse(str(fasta), "fasta"):
        kmers |= iter_kmers(str(rec.seq), k=k)
        if len(kmers) > 250_000:
            break
    return minhash_signature(kmers, n_perm=n_perm)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta-dir", type=Path, default=Path("data/raw/bvbrc/genomes"))
    parser.add_argument("--genome-list", type=Path, default=Path("data/processed/cohort/genome_list.txt"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed/splits"))
    parser.add_argument("--k", type=int, default=21, help="k-mer size (Mash-like)")
    parser.add_argument("--n-perm", type=int, default=128, help="MinHash permutations")
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.05,
        help="Mash-distance cutoff for clustering (lower = stricter de-duplication)",
    )
    parser.add_argument("--train-frac", type=float, default=0.70)
    parser.add_argument("--cal-frac", type=float, default=0.15)
    parser.add_argument(
        "--annotated-only",
        action="store_true",
        help="Restrict to genomes with AMRFinderPlus TSV (faster interim splits)",
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/processed/cohort/genome_antibiotic_labels.tsv"),
        help="Used to reserve resistant-genome clusters for the test split",
    )
    args = parser.parse_args()

    genome_ids = [
        normalize_genome_id(line)
        for line in args.genome_list.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    available = [gid for gid in genome_ids if (args.fasta_dir / f"{gid}.fna").exists()]
    if args.annotated_only:
        amr_dir = Path("data/processed/amrfinder")
        annotated = {p.stem for p in amr_dir.glob("*.tsv")}
        available = [gid for gid in available if gid in annotated]
    if len(available) < 10:
        raise SystemExit(f"Need >=10 FASTA files; found {len(available)} in {args.fasta_dir}")

    print(f"Computing MinHash signatures for {len(available)} genomes ...")
    sigs: dict[str, np.ndarray] = {}
    for i, gid in enumerate(available, 1):
        sigs[gid] = genome_signature(args.fasta_dir / f"{gid}.fna", args.k, args.n_perm)
        if i % 50 == 0 or i == len(available):
            print(f"  {i}/{len(available)}")

    ids = available
    n = len(ids)
    dist = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = mash_distance(sigs[ids[i]], sigs[ids[j]], k=args.k)
            dist[i, j] = dist[j, i] = d

    condensed = squareform(dist, checks=False)
    z = linkage(condensed, method="average")
    cluster_labels = fcluster(z, t=args.distance_threshold, criterion="distance")

    clusters: dict[int, list[str]] = defaultdict(list)
    for gid, cl in zip(ids, cluster_labels):
        clusters[int(cl)].append(gid)

    resistant_genomes: set[str] = set()
    if args.labels.exists():
        import pandas as pd

        lab = pd.read_csv(args.labels, sep="\t", dtype={"genome_id": str})
        resistant_genomes = set(lab.loc[lab["label"] == "likely_to_fail", "genome_id"])

    cluster_has_resistant = {
        cl: any(g in resistant_genomes for g in members) for cl, members in clusters.items()
    }
    resistant_cluster_ids = [cl for cl, flag in cluster_has_resistant.items() if flag]
    other_cluster_ids = [cl for cl in clusters if cl not in resistant_cluster_ids]

    rng = random.Random(args.seed)
    rng.shuffle(resistant_cluster_ids)
    rng.shuffle(other_cluster_ids)

    n_clusters = len(clusters)
    n_train = max(1, int(round(n_clusters * args.train_frac)))
    n_cal = max(1, int(round(n_clusters * args.cal_frac)))
    if n_train + n_cal >= n_clusters:
        n_cal = max(1, n_clusters - n_train - 1)
    n_test = max(1, n_clusters - n_train - n_cal)

    test_clusters: set[int] = set()
    for cl in resistant_cluster_ids:
        if len(test_clusters) >= max(2, n_test // 2):
            break
        test_clusters.add(cl)

    pool = [cl for cl in resistant_cluster_ids if cl not in test_clusters] + other_cluster_ids
    rng.shuffle(pool)
    for cl in pool:
        if len(test_clusters) >= n_test:
            break
        test_clusters.add(cl)

    remaining = [cl for cl in clusters if cl not in test_clusters]
    rng.shuffle(remaining)
    train_clusters = set(remaining[:n_train])
    cal_clusters = set(remaining[n_train : n_train + n_cal])

    split_map: dict[str, str] = {}
    for cl, members in clusters.items():
        if cl in train_clusters:
            split = "train"
        elif cl in cal_clusters:
            split = "calibration"
        else:
            split = "test"
        for gid in members:
            split_map[gid] = split

    args.out_dir.mkdir(parents=True, exist_ok=True)
    split_path = args.out_dir / "genome_split.tsv"
    with split_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["genome_id", "cluster_id", "split"])
        for gid in sorted(split_map):
            idx = ids.index(gid)
            w.writerow([gid, cluster_labels[idx], split_map[gid]])

    summary = {
        "n_genomes": len(split_map),
        "n_clusters": n_clusters,
        "distance_threshold": args.distance_threshold,
        "k": args.k,
        "n_perm": args.n_perm,
        "split_counts": {
            "train": sum(v == "train" for v in split_map.values()),
            "calibration": sum(v == "calibration" for v in split_map.values()),
            "test": sum(v == "test" for v in split_map.values()),
        },
        "cluster_size": {
            "min": min(len(v) for v in clusters.values()),
            "max": max(len(v) for v in clusters.values()),
            "median": int(np.median([len(v) for v in clusters.values()])),
        },
        "justification": (
            "MinHash k-mer distance approximates Mash ANI for de-duplication. "
            f"Clusters with linkage distance <= {args.distance_threshold} are kept in one split. "
            "Clusters containing lab-resistant genomes are preferentially represented in test."
        ),
        "resistant_clusters": len(resistant_cluster_ids),
        "test_resistant_clusters": sum(1 for cl in test_clusters if cluster_has_resistant.get(cl)),
    }
    summary_path = args.out_dir / "split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {split_path}")


if __name__ == "__main__":
    main()
