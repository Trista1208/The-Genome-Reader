from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AMRAnnotation:
    genome_id: str
    feature_name: str
    feature_kind: str
    gene_symbol: str
    sequence_name: str
    element_type: str
    element_subtype: str
    drug_class: str
    method: str
    raw: dict[str, str] = field(repr=False)


def _value(row: dict[str, str], *names: str) -> str:
    lowered = {key.lower().strip(): (value or "").strip() for key, value in row.items()}
    return next((lowered[name.lower()] for name in names if lowered.get(name.lower())), "")


def _slug(text: str) -> str:
    return "_".join(text.strip().replace("/", "_").split())


def parse_amrfinder_tsv(path: str | Path, genome_id: str) -> list[AMRAnnotation]:
    annotations: list[AMRAnnotation] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            return annotations
        for row in reader:
            gene = _value(row, "Gene symbol", "Gene", "Element symbol")
            sequence_name = _value(
                row, "Sequence name", "Name of closest sequence", "Name",
                "Element name", "Closest reference name",
            )
            element_type = _value(row, "Element type", "Type")
            element_subtype = _value(row, "Element subtype", "Subtype")
            drug_class = _value(row, "Class", "Subclass")
            method = _value(row, "Method")
            mutation_like = "POINT" in element_type.upper() or "MUTATION" in element_subtype.upper()
            if mutation_like:
                identity = sequence_name or gene or "unknown_mutation"
                kind = "mutation"
                name = f"mutation::{_slug(gene or 'unknown_gene')}::{_slug(identity)}"
            else:
                identity = gene or sequence_name or "unknown_gene"
                kind = "gene"
                name = f"gene::{_slug(identity)}"
            annotations.append(
                AMRAnnotation(
                    genome_id=str(genome_id), feature_name=name, feature_kind=kind,
                    gene_symbol=gene, sequence_name=sequence_name, element_type=element_type,
                    element_subtype=element_subtype, drug_class=drug_class, method=method, raw=dict(row),
                )
            )
    return annotations


def run_amrfinder(
    fasta_path: str | Path,
    output_path: str | Path,
    executable: str = "amrfinder",
    database: str | None = None,
    organism: str = "Escherichia",
    threads: int = 1,
) -> None:
    command = [
        executable, "-n", str(fasta_path), "-o", str(output_path), "--plus",
        "--organism", organism, "--threads", str(threads),
    ]
    if database:
        command.extend(["--database", database])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"AMRFinderPlus failed for {fasta_path} (exit {completed.returncode}):\n{completed.stderr}"
        )
