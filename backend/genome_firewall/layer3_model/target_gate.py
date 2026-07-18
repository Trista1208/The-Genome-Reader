from __future__ import annotations

from pathlib import Path

from Bio import SeqIO


def passes_target_gate(
    fasta: Path,
    *,
    min_length: int = 4_000_000,
    max_contigs: int = 800,
) -> tuple[bool, str]:
    """Deterministic gate: incomplete assemblies should not receive work predictions."""
    recs = list(SeqIO.parse(str(fasta), "fasta"))
    total_len = sum(len(r) for r in recs)
    if total_len < min_length:
        return False, "assembly_too_short"
    if len(recs) > max_contigs:
        return False, "overfragmented_assembly"
    return True, "complete_ecoli_assembly"
