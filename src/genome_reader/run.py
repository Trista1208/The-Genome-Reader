from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from src.common import write_json
from src.genome_reader.amrfinder import AMRAnnotation, parse_amrfinder_tsv, run_amrfinder
from src.genome_reader.encoding import build_catalog, encode_annotations, save_feature_bundle
from src.genome_reader.fasta import validate_fasta
from src.splitting.check_group_integrity import assert_group_integrity, load_genomes


def _process_genome(row, fasta_dir, annotation_dir, executable, database, amrfinder_threads, reuse):
    genome_id = str(row["genome_id"])
    fasta = fasta_dir / f"{genome_id}.fna"
    if not fasta.exists():
        raise FileNotFoundError(f"Missing FASTA: {fasta}")
    stats = validate_fasta(fasta)
    if stats.invalid_characters:
        raise ValueError(f"Invalid DNA characters in {fasta}: {stats.invalid_characters}")
    expected_length = int(row["genome_length"])
    if abs(stats.bases - expected_length) / expected_length > 0.01:
        raise ValueError(f"FASTA length differs from metadata by >1% for {genome_id}")
    output = annotation_dir / f"{genome_id}.tsv"
    if not (reuse and output.exists()):
        run_amrfinder(fasta, output, executable, database, threads=amrfinder_threads)
    return genome_id, parse_amrfinder_tsv(output, genome_id), asdict(stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create AMRFinderPlus sparse features.")
    parser.add_argument("--input", required=True, help="Directory containing <genome_id>.fna files")
    parser.add_argument("--genomes", required=True, help="Master genome metadata CSV")
    parser.add_argument("--output", required=True, help="Output feature-bundle directory")
    parser.add_argument("--annotations", help="AMRFinderPlus TSV directory; defaults under output")
    parser.add_argument("--amrfinder", default="amrfinder")
    parser.add_argument("--database")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--amrfinder-threads", type=int, default=1)
    parser.add_argument("--min-training-genomes", type=int, default=1)
    parser.add_argument("--reuse-annotations", action="store_true")
    args = parser.parse_args()

    genomes = load_genomes(args.genomes)
    assert_group_integrity(genomes)
    fasta_dir = Path(args.input)
    output_dir = Path(args.output)
    annotation_dir = Path(args.annotations) if args.annotations else output_dir / "amrfinder"
    annotation_dir.mkdir(parents=True, exist_ok=True)

    annotations_by_genome: dict[str, list[AMRAnnotation]] = {}
    qc: dict[str, dict] = {}
    records = genomes.to_dict("records")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _process_genome, row, fasta_dir, annotation_dir, args.amrfinder,
                args.database, args.amrfinder_threads, args.reuse_annotations,
            ): str(row["genome_id"])
            for row in records
        }
        for index, future in enumerate(as_completed(futures), 1):
            genome_id, annotations, stats = future.result()
            annotations_by_genome[genome_id] = annotations
            qc[genome_id] = stats
            print(f"[{index}/{len(futures)}] {genome_id}: {len(annotations)} AMR features", flush=True)

    genome_ids = genomes["genome_id"].astype(str).tolist()
    training_ids = set(genomes.loc[genomes["split"] == "train", "genome_id"].astype(str))
    catalog = build_catalog(annotations_by_genome, training_ids, args.min_training_genomes)
    matrix = encode_annotations(annotations_by_genome, genome_ids, catalog)
    samples = genomes[["genome_id", "split", "genetic_group"]].copy()
    samples["genome_id"] = samples["genome_id"].astype("string")
    save_feature_bundle(
        output_dir, matrix, samples, catalog,
        {
            "source": "AMRFinderPlus",
            "catalog_fit_split": "train",
            "min_training_genomes": args.min_training_genomes,
            "n_genomes": len(genome_ids),
            "n_features": len(catalog),
        },
    )
    write_json(output_dir / "fasta_qc.json", qc)
    with (output_dir / "annotations.jsonl").open("w", encoding="utf-8") as handle:
        for genome_id in genome_ids:
            for annotation in annotations_by_genome[genome_id]:
                payload = asdict(annotation)
                payload.pop("raw", None)
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
    print(f"Saved {matrix.shape[0]} genomes x {matrix.shape[1]} features to {output_dir}")


if __name__ == "__main__":
    main()
