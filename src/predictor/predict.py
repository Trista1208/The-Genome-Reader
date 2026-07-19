from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import joblib
from scipy import sparse

from src.common import SUPPORTED_ANTIBIOTICS
from src.decision_report.report import build_report
from src.genome_reader.amrfinder import parse_amrfinder_tsv, run_amrfinder
from src.genome_reader.fasta import validate_fasta
from src.predictor.target_gate import TargetGate


def _encode_one(feature_names: list[str], annotations) -> sparse.csr_matrix:
    feature_index = {name: index for index, name in enumerate(feature_names)}
    columns = sorted({
        feature_index[item.feature_name]
        for item in annotations
        if item.feature_name in feature_index
    })
    return sparse.csr_matrix(
        ([1] * len(columns), ([0] * len(columns), columns)),
        shape=(1, len(feature_names)),
        dtype="uint8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict AMR from one assembled FASTA.")
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--target-gate", required=True)
    parser.add_argument("--genome-id")
    parser.add_argument("--species", default="Escherichia coli")
    parser.add_argument("--amrfinder", default="amrfinder")
    parser.add_argument("--database")
    parser.add_argument("--amrfinder-tsv", help="Reuse an existing annotation TSV")
    parser.add_argument("--output")
    args = parser.parse_args()

    fasta = Path(args.fasta)
    genome_id = str(args.genome_id or fasta.stem)
    stats = validate_fasta(fasta)
    if stats.invalid_characters:
        raise ValueError(f"Invalid DNA characters: {stats.invalid_characters}")

    if args.amrfinder_tsv:
        annotations = parse_amrfinder_tsv(args.amrfinder_tsv, genome_id)
    else:
        with tempfile.TemporaryDirectory(prefix="genome_firewall_") as temporary:
            annotation_path = Path(temporary) / "amrfinder.tsv"
            run_amrfinder(fasta, annotation_path, args.amrfinder, args.database)
            annotations = parse_amrfinder_tsv(annotation_path, genome_id)

    gate = TargetGate.from_yaml(args.target_gate)
    present_features = {item.feature_name for item in annotations}
    reports = []
    for antibiotic in SUPPORTED_ANTIBIOTICS:
        model_path = Path(args.models) / f"{antibiotic.replace('/', '_')}.joblib"
        if not model_path.exists():
            continue
        model = joblib.load(model_path)
        matrix = _encode_one(model.feature_names, annotations)
        gate_result = gate.evaluate(antibiotic, args.species, present_features)
        prediction = model.predict(matrix) if gate_result.pass_gate else None
        supporting = model.supporting_features(matrix) if prediction is not None else []
        reports.append(
            build_report(genome_id, args.species, antibiotic, gate_result, prediction, supporting)
        )

    payload = {
        "genome_id": genome_id,
        "species": args.species,
        "fasta_qc": {
            "contigs": stats.records,
            "bases": stats.bases,
            "gc_fraction": stats.gc_fraction,
        },
        "predictions": reports,
    }
    rendered = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
