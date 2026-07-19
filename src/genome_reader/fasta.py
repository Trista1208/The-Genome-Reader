from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

IUPAC_DNA = frozenset("ACGTRYSWKMBDHVN")


@dataclass(frozen=True)
class FastaStats:
    records: int
    bases: int
    gc_fraction: float
    invalid_characters: tuple[str, ...]


def iter_fasta(path: str | Path) -> Iterator[tuple[str, str]]:
    """Yield all records; callers treat the complete file as one genome."""
    header: str | None = None
    chunks: list[str] = []
    with Path(path).open(encoding="ascii") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(chunks).upper()
                header = line[1:].strip()
                if not header:
                    raise ValueError(f"Empty FASTA header at line {line_number}: {path}")
                chunks = []
            else:
                if header is None:
                    raise ValueError(f"Sequence before first FASTA header at line {line_number}: {path}")
                chunks.append("".join(line.split()))
    if header is not None:
        yield header, "".join(chunks).upper()


def validate_fasta(path: str | Path) -> FastaStats:
    records = bases = gc = 0
    invalid: set[str] = set()
    for _header, sequence in iter_fasta(path):
        records += 1
        if not sequence:
            raise ValueError(f"Empty FASTA record in {path}")
        bases += len(sequence)
        gc += sequence.count("G") + sequence.count("C")
        invalid.update(set(sequence) - IUPAC_DNA)
    if records == 0 or bases == 0:
        raise ValueError(f"No FASTA sequence records found in {path}")
    return FastaStats(records, bases, gc / bases, tuple(sorted(invalid)))
