#!/usr/bin/env python3
"""Select one bacterial species + 3–5 antibiotics from BV-BRC lab AMR phenotypes.

Follows challenge guidance:
- laboratory-measured phenotypes only (prefer rows with measurement / lab typing)
- one species, ~1k–3k genomes when possible
- standardized antibiotic names with enough resistant + susceptible labels
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

# Prefer clinical priority pathogens with rich public AST data.
SPECIES_PRIORITY = [
    "Escherichia coli",
    "Klebsiella pneumoniae",
    "Staphylococcus aureus",
    "Pseudomonas aeruginosa",
    "Salmonella enterica",
    "Acinetobacter baumannii",
    "Streptococcus pneumoniae",
]


def normalize_pheno(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    if "resistant" in s and "intermediate" not in s:
        return "resistant"
    if s in {"r", "res"}:
        return "resistant"
    if "susceptible" in s or "sensitive" in s:
        return "susceptible"
    if s in {"s", "sus"}:
        return "susceptible"
    if "intermediate" in s:
        return "intermediate"
    return None


def species_from_row(row: dict[str, str], forced: str | None = None) -> str:
    if forced:
        return forced
    if row.get("species"):
        return row["species"].strip()
    name = (row.get("genome_name") or "").strip()
    parts = name.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else name


def is_lab_like(row: dict[str, str]) -> bool:
    """Prefer laboratory antibiogram rows; exclude obvious computational predictions."""
    source = (row.get("source") or row.get("evidence") or "").lower()
    method = (row.get("laboratory_typing_method") or row.get("lab_typing_method") or "").lower()
    measurement = row.get("measurement") or row.get("measurement_value") or ""
    if "computational" in source or "predicted" in source or "model" in source:
        return False
    pheno = row.get("resistant_phenotype") or row.get("resistance_phenotype") or ""
    if not pheno:
        return False
    # Prefer rows with MIC/measurement or lab typing method (challenge: lab-measured only).
    return bool(measurement or method)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--amr",
        type=Path,
        default=Path("data/raw/bvbrc/RELEASE_NOTES/PATRIC_genomes_AMR.txt"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/raw/bvbrc/RELEASE_NOTES/genome_metadata"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/cohort"),
    )
    parser.add_argument("--min-genomes", type=int, default=800)
    parser.add_argument("--max-genomes", type=int, default=3000)
    parser.add_argument("--n-antibiotics", type=int, default=5)
    parser.add_argument(
        "--species",
        default=None,
        help="Force a species (default: auto-pick from priority list)",
    )
    args = parser.parse_args()

    if not args.amr.exists():
        raise SystemExit(f"Missing AMR table: {args.amr}. Run download_bvbrc_release_notes.py first.")

    print(f"Scanning {args.amr} ...")
    genome_col, drug_col, pheno_col = "genome_id", "antibiotic", "resistant_phenotype"

    species_drug_pheno: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    species_genomes: dict[str, set[str]] = defaultdict(set)
    species_drug_genomes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    kept = 0
    with args.amr.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not is_lab_like(row):
                continue
            gid = (row.get(genome_col) or "").strip()
            drug = (row.get(drug_col) or "").strip().lower()
            pheno = normalize_pheno(row.get(pheno_col, ""))
            if not gid or not drug or pheno not in {"resistant", "susceptible"}:
                continue
            species = species_from_row(row, None).strip()
            if args.species and species != args.species:
                continue
            if not species:
                continue
            species_drug_pheno[species][drug][pheno] += 1
            species_genomes[species].add(gid)
            species_drug_genomes[species][drug].add(gid)
            kept += 1

    print(f"Kept lab-measured R/S rows: {kept:,}")
    print(f"Species with any R/S labels: {len(species_genomes):,}")

    def score_species(sp: str) -> tuple:
        n = len(species_genomes[sp])
        # antibiotics with both classes and enough genomes
        good_drugs = []
        for drug, genomes in species_drug_genomes[sp].items():
            c = species_drug_pheno[sp][drug]
            if c["resistant"] >= 50 and c["susceptible"] >= 50 and len(genomes) >= 200:
                good_drugs.append((drug, len(genomes), c["resistant"], c["susceptible"]))
        good_drugs.sort(key=lambda x: x[1], reverse=True)
        in_priority = sp in SPECIES_PRIORITY
        priority_rank = SPECIES_PRIORITY.index(sp) if in_priority else 999
        # Prefer species in target genome range
        size_penalty = 0
        if n < args.min_genomes:
            size_penalty = args.min_genomes - n
        elif n > args.max_genomes:
            size_penalty = n - args.max_genomes
        return (
            -len(good_drugs),
            priority_rank,
            size_penalty,
            -n,
            sp,
            good_drugs,
        )

    candidates = []
    for sp in species_genomes:
        if args.species and sp != args.species:
            continue
        sc = score_species(sp)
        candidates.append(sc)
    candidates.sort()

    if not candidates:
        raise SystemExit("No species candidates found.")

    best = candidates[0]
    species = best[4]
    good_drugs = best[5][: args.n_antibiotics]
    if not good_drugs:
        # Fall back to top antibiotics by genome count even if unbalanced
        ranked = sorted(
            (
                (d, len(g), species_drug_pheno[species][d]["resistant"], species_drug_pheno[species][d]["susceptible"])
                for d, g in species_drug_genomes[species].items()
            ),
            key=lambda x: x[1],
            reverse=True,
        )
        good_drugs = ranked[: args.n_antibiotics]

    antibiotics = [d[0] for d in good_drugs]
    print(f"\nSelected species: {species}")
    print(f"Genomes with any R/S label: {len(species_genomes[species]):,}")
    print("Antibiotics:")
    for d, n, r, s in good_drugs:
        print(f"  - {d}: genomes={n:,} R={r:,} S={s:,}")

    # Second pass: emit labels for selected species + antibiotics
    selected_genomes: set[str] = set()
    labels: list[dict[str, str]] = []
    antibiotics_set = set(antibiotics)
    with args.amr.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not is_lab_like(row):
                continue
            gid = (row.get(genome_col) or "").strip()
            drug = (row.get(drug_col) or "").strip().lower()
            pheno = normalize_pheno(row.get(pheno_col, ""))
            if drug not in antibiotics_set or pheno not in {"resistant", "susceptible"}:
                continue
            sp = species_from_row(row, None).strip()
            if sp != species:
                continue
            selected_genomes.add(gid)
            labels.append(
                {
                    "genome_id": gid,
                    "antibiotic": drug,
                    "phenotype": pheno,  # resistant=likely to fail, susceptible=likely to work
                    "label": "likely_to_fail" if pheno == "resistant" else "likely_to_work",
                }
            )

    # Cap genome count for manageable first download (challenge suggests 1k–3k)
    genome_ids = sorted(selected_genomes)
    if len(genome_ids) > args.max_genomes:
        # Keep genomes with the most selected-drug labels
        counts = Counter(x["genome_id"] for x in labels)
        genome_ids = [g for g, _ in counts.most_common(args.max_genomes)]
        keep = set(genome_ids)
        labels = [x for x in labels if x["genome_id"] in keep]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    genome_list = args.out_dir / "genome_list.txt"
    genome_list.write_text("\n".join(genome_ids) + "\n")
    labels_path = args.out_dir / "genome_antibiotic_labels.tsv"
    with labels_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["genome_id", "antibiotic", "phenotype", "label"],
            delimiter="\t",
        )
        w.writeheader()
        w.writerows(labels)

    summary = {
        "species": species,
        "n_genomes": len(genome_ids),
        "antibiotics": [
            {
                "name": d,
                "n_genomes": n,
                "n_resistant": r,
                "n_susceptible": s,
            }
            for d, n, r, s in good_drugs
        ],
        "label_rows": len(labels),
        "paths": {
            "genome_list": str(genome_list),
            "labels": str(labels_path),
        },
        "notes": [
            "resistant -> likely_to_fail; susceptible -> likely_to_work",
            "Use laboratory phenotypes only; exclude computational predictions where flagged",
            "Organizer fixed split should replace this cohort when available",
        ],
    }
    summary_path = args.out_dir / "cohort_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nWrote {genome_list} ({len(genome_ids):,} genomes)")
    print(f"Wrote {labels_path} ({len(labels):,} labels)")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
