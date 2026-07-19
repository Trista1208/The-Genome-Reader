"""target_gate.py — target-locus callability / WT-intactness gate.

The challenge brief requires that a "likely to work" call accounts for the
presence of the drug's molecular target: it may never rest solely on "no
resistance marker was found". Within one species the target is never truly
absent (synthesis v2, roast change 4), so the gate is a *locus callability /
WT-intactness* check (APHL wording), not a target-presence search.

Signal inventory (verified 2026-07-19):
  The production batch TSVs (``amrfinder -O Escherichia --plus``) report only
  curated resistance mutations actually FOUND — for a locus with no row,
  "screened, wild-type" and "never screened" are indistinguishable.
  ``--mutation_all`` (compared on 562.100000 -> data/mutall_check.tsv, 310
  rows vs 36) additionally emits one row per screened curated position tagged
  [WILDTYPE] / [UNKNOWN], i.e. positive evidence the locus was called.
The corpus was therefore re-screened with ``--mutation_all`` into
``features/amrfinder_mutall/`` (same pinned image); those TSVs are the
PRIMARY callability signal: any row at a locus (curated mutation, WT, or
unknown-variant) proves AMRFinderPlus found and screened the locus, and a
locus with no row in a --mutation_all TSV is genuinely not called (found
only in broken assemblies — the genes are essential). A spaced-k-mer check
of the reference locus in the assembly (same algorithm/parameters as
demo/build_cache.py) remains as fallback for genomes without a
--mutation_all TSV; it is deliberately strict (exact 31-mers over ~1-2%
within-species divergence), hence only a fallback.

Statuses (gate_status(genome_id, drug) -> {"status", "detail"}):
  pass                  curated point-mutation loci exist for the drug and
                        every one is callable (screening evidence above)
  absence_of_evidence   no curated locus for this drug (gentamicin,
                        ampicillin, SXT, cefotaxime — resistance here is
                        dominated by acquired genes; their targets are
                        essential core genes) AND assembly QC passes; the
                        "likely to work" call stands but is LABELED
                        absence-of-evidence, never a silent pass
  not_callable          a curated locus is unverified, or assembly QC fails
                        -> the eval path turns "likely to work" into NO-CALL
                        with reason "target locus not callable"

Assembly QC (E. coli): total length in [4, 6] Mb and <= 500 contigs,
computed from the .fna (data/manifest.json carries no per-genome QC fields).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import nocall

STATUS_PASS = "pass"
STATUS_NOT_CALLABLE = "not_callable"
STATUS_ABSENCE = "absence_of_evidence"
NO_CALL_REASON = "target locus not callable"

# Curated AMRFinderPlus -O Escherichia point-mutation loci per drug.
# Only ciprofloxacin is gated at locus level in this dry run:
#   * gyrA/parC/parE carry the overwhelming majority of curated quinolone
#     POINT hits; gyrB has zero curated POINT hits in this corpus (checked
#     2026-07-19), so no reference locus can be bootstrapped for it.
#   * 16S (aminoglycoside), folP/folA (SXT) and ftsI (beta-lactam) curated
#     mutations exist but are rare secondary mechanisms for our drugs; the
#     design (and the demo panel) routes those drugs through the
#     absence-of-evidence + assembly-QC path instead.
# Add loci here to promote another drug to the curated-locus path.
DRUG_LOCI: dict[str, tuple[str, ...]] = {
    "ciprofloxacin": ("gyrA", "parC", "parE"),
}

# k-mer locus check — mirrors demo/build_cache.py exactly (donor, k, count,
# threshold) so pipeline gate and demo panel cannot disagree.
KMER_K = 31
KMER_PER_LOCUS = 48
CALLABLE_FRAC = 0.75
LOCUS_DONOR = "562.100000"  # TSV carries confirmed POINT hits at all 3 loci

# Assembly QC for the absence-of-evidence drugs (E. coli ~4.6-5.6 Mb;
# short-read BV-BRC assemblies are typically far under 500 contigs).
QC_MIN_BP = 4_000_000
QC_MAX_BP = 6_000_000
QC_MAX_CONTIGS = 500


def read_fasta(path: str | Path) -> dict[str, str]:
    """contig name -> sequence (uppercase)."""
    contigs: dict[str, list[str]] = {}
    name = None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(">"):
                name = line[1:].split()[0]
                contigs[name] = []
            elif name is not None:
                contigs[name].append(line.upper())
    return {k: "".join(v) for k, v in contigs.items()}


def revcomp(s: str) -> str:
    return s.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


class Gate:
    """Deterministic per-(genome, drug) gate. Caches all per-genome work.

    tsv_dir: batch AMRFinderPlus TSVs (features/amrfinder).
    mutall_tsv_dir: --mutation_all TSVs (features/amrfinder_mutall); the
        PRIMARY callability signal. When a genome has one, the screen is
        authoritative: a locus with no row there was genuinely not called
        and the k-mer fallback is not consulted for that genome.
    """

    def __init__(self, tsv_dir: str | Path, fna_dir: str | Path,
                 mutall_tsv_dir: str | Path | None = None,
                 drug_loci: dict[str, tuple[str, ...]] | None = None,
                 donor: str = LOCUS_DONOR):
        self.tsv_dir = Path(tsv_dir)
        self.fna_dir = Path(fna_dir)
        self.mutall_tsv_dir = (Path(mutall_tsv_dir) if mutall_tsv_dir
                               and Path(mutall_tsv_dir).is_dir() else None)
        self.drug_loci = drug_loci if drug_loci is not None else DRUG_LOCI
        self.donor = donor
        self._ref_kmers: dict[str, dict[str, set[str]]] | None = None
        self._rows_cache: dict = {}
        self._asm_cache: dict[str, dict] = {}

    # -------------------------------------------------------- reference
    def reference_kmers(self) -> dict[str, dict[str, set[str]]]:
        """Spaced k-mers of each curated locus, bootstrapped from the donor
        genome's own assembly using its TSV coordinates (a confirmed call).
        Both strands stored: contig orientation is random across assemblies."""
        if self._ref_kmers is not None:
            return self._ref_kmers
        tsv = self.tsv_dir / f"{self.donor}.tsv"
        fna = self.fna_dir / f"{self.donor}.fna"
        contigs = read_fasta(fna)
        rows = pd.read_csv(tsv, sep="\t")
        loci = sorted({l for ls in self.drug_loci.values() for l in ls})
        out: dict[str, dict[str, set[str]]] = {}
        for locus in loci:
            hits = rows[rows["Element symbol"].str.startswith(locus + "_", na=False)]
            if hits.empty:
                raise ValueError(f"donor {self.donor} has no {locus} POINT hit; "
                                 f"pick a new LOCUS_DONOR")
            r = hits.iloc[0]
            seq = contigs[str(r["Contig id"])]
            locus_seq = seq[int(r["Start"]) - 1:int(r["Stop"])]
            step = max(1, (len(locus_seq) - KMER_K) // KMER_PER_LOCUS)
            fwd = {locus_seq[i:i + KMER_K]
                   for i in range(0, len(locus_seq) - KMER_K + 1, step)}
            out[locus] = {"fwd": fwd, "rc": {revcomp(k) for k in fwd}}
        self._ref_kmers = out
        return out

    # -------------------------------------------------------- per-genome
    def _locus_rows(self, genome_id: str) -> tuple[dict[str, dict[str, list[str]]], bool]:
        """(classified rows, has_mutall).

        classified rows: locus -> {"mutation": [...], "wt": [...],
        "unknown": [...]} from POINT-subtype rows at that locus. Tag comes
        from the Element name: [WILDTYPE] / [UNKNOWN] appear only in
        --mutation_all TSVs; untagged rows are curated resistance mutations.
        has_mutall: a --mutation_all TSV exists for this genome, making the
        screen authoritative (a locus absent from it was genuinely NOT
        called — the k-mer fallback must not override that).
        """
        if genome_id in self._rows_cache:
            return self._rows_cache[genome_id]
        loci = sorted({l for ls in self.drug_loci.values() for l in ls})
        out: dict[str, dict[str, set[str]]] = {
            l: {"mutation": set(), "wt": set(), "unknown": set()} for l in loci}
        paths = [self.tsv_dir / f"{genome_id}.tsv"]
        mutall_path = (self.mutall_tsv_dir / f"{genome_id}.tsv"
                       if self.mutall_tsv_dir is not None else None)
        has_mutall = mutall_path is not None and mutall_path.exists()
        if has_mutall:
            paths.append(mutall_path)
        for path in paths:
            if not path.exists():
                continue
            rows = pd.read_csv(path, sep="\t")
            point = rows[rows["Subtype"].astype(str).str.startswith("POINT")]
            for sym, name in zip(point["Element symbol"].astype(str),
                                 point["Element name"].astype(str)):
                for locus in loci:
                    if sym.startswith(locus + "_"):
                        if "[WILDTYPE]" in name:
                            out[locus]["wt"].add(sym)
                        elif "[UNKNOWN]" in name:
                            out[locus]["unknown"].add(sym)
                        else:
                            out[locus]["mutation"].add(sym)
        res = ({l: {k: sorted(v) for k, v in d.items()}
                for l, d in out.items() if any(d.values())}, has_mutall)
        self._rows_cache[genome_id] = res
        return res

    def _assembly(self, genome_id: str, want_kmers: bool) -> dict:
        """FASTA-derived facts, read once per genome and cached.

        {"total_bp", "n_contigs", "fracs": {locus: float} | None}
        fracs is None when the k-mer check was not requested (or no FASTA).
        """
        cached = self._asm_cache.get(genome_id)
        if cached is not None and (cached["fracs"] is not None or not want_kmers):
            return cached
        fna = self.fna_dir / f"{genome_id}.fna"
        info = {"total_bp": None, "n_contigs": None, "fracs": None}
        if fna.exists():
            contigs = read_fasta(fna)
            info["total_bp"] = int(sum(len(s) for s in contigs.values()))
            info["n_contigs"] = len(contigs)
            if want_kmers:
                hay = ("N" * 64).join(contigs.values())
                fracs = {}
                for locus, strands in self.reference_kmers().items():
                    n_ref = len(strands["fwd"])
                    fwd = sum(1 for k in strands["fwd"] if k in hay)
                    if fwd / n_ref >= CALLABLE_FRAC:
                        fracs[locus] = round(fwd / n_ref, 4)
                        continue  # pass already decided; skip the other strand
                    rc = sum(1 for k in strands["rc"] if k in hay)
                    fracs[locus] = round(max(fwd, rc) / n_ref, 4)
                info["fracs"] = fracs
        self._asm_cache[genome_id] = info
        return info

    def assembly_qc(self, genome_id: str) -> dict:
        """{"ok": bool, "detail": str, "total_bp", "n_contigs"} from the .fna."""
        a = self._assembly(genome_id, want_kmers=False)
        if a["total_bp"] is None:
            return {"ok": False, "total_bp": None, "n_contigs": None,
                    "detail": "assembly FASTA missing"}
        mb = a["total_bp"] / 1e6
        problems = []
        if not (QC_MIN_BP <= a["total_bp"] <= QC_MAX_BP):
            problems.append(
                f"length {mb:.2f} Mb outside {QC_MIN_BP / 1e6:.0f}-"
                f"{QC_MAX_BP / 1e6:.0f} Mb")
        if a["n_contigs"] > QC_MAX_CONTIGS:
            problems.append(f"{a['n_contigs']} contigs > {QC_MAX_CONTIGS}")
        detail = (f"{mb:.2f} Mb, {a['n_contigs']} contigs"
                  + ("; " + "; ".join(problems) if problems else ""))
        return {"ok": not problems, "total_bp": a["total_bp"],
                "n_contigs": a["n_contigs"], "detail": detail}

    # -------------------------------------------------------- the gate
    def gate_status(self, genome_id: str, drug: str) -> dict[str, str]:
        """{"status": pass|not_callable|absence_of_evidence, "detail": str}."""
        loci = self.drug_loci.get(drug)
        if loci:
            return self._curated_status(genome_id, drug, loci)
        qc = self.assembly_qc(genome_id)
        if not qc["ok"]:
            return {"status": STATUS_NOT_CALLABLE,
                    "detail": f"{NO_CALL_REASON}: assembly QC fail "
                              f"({qc['detail']})"}
        return {"status": STATUS_ABSENCE,
                "detail": f"no curated point-mutation locus for {drug}; "
                          f"assembly QC pass ({qc['detail']}) — "
                          f"absence-of-evidence call, target assumed present "
                          f"(essential core gene)"}

    def _curated_status(self, genome_id: str, drug: str,
                        loci: tuple[str, ...]) -> dict[str, str]:
        rows, has_mutall = self._locus_rows(genome_id)
        # k-mer fallback only when the authoritative screen is unavailable
        need_kmers = (not has_mutall) and any(l not in rows for l in loci)
        asm = self._assembly(genome_id, want_kmers=need_kmers)
        fracs = asm["fracs"] or {}
        parts, bad = [], []
        for locus in loci:
            r = rows.get(locus)
            if r:
                if r["mutation"]:
                    parts.append(f"{locus}: curated mutation "
                                 f"{', '.join(r['mutation'])}")
                elif r["wt"]:
                    parts.append(f"{locus}: screened WT (--mutation_all, "
                                 f"e.g. {r['wt'][0]} [WILDTYPE])")
                else:
                    parts.append(f"{locus}: screened, variant of unknown "
                                 f"significance (--mutation_all, e.g. "
                                 f"{r['unknown'][0]} [UNKNOWN])")
                continue
            if has_mutall:
                bad.append(f"{locus} not found by the AMRFinderPlus "
                           f"--mutation_all screen (locus absent from TSV)")
                continue
            frac = fracs.get(locus)
            if frac is None:
                bad.append(f"{locus} unverified (no AMRFinderPlus row; "
                           f"assembly FASTA missing)")
            elif frac >= CALLABLE_FRAC:
                parts.append(f"{locus}: WT-intact (locus k-mers {frac:.2f} "
                             f">= {CALLABLE_FRAC}; no --mutation_all TSV, "
                             f"k-mer fallback)")
            else:
                bad.append(f"{locus} not found in assembly "
                           f"(locus k-mers {frac:.2f} < {CALLABLE_FRAC})")
        if bad:
            return {"status": STATUS_NOT_CALLABLE,
                    "detail": f"{NO_CALL_REASON}: " + "; ".join(bad)}
        return {"status": STATUS_PASS,
                "detail": f"{drug} target loci callable — " + "; ".join(parts)}


def apply_gate_override(p, bands: nocall.NoCallBands, base_mask,
                        statuses) -> tuple[np.ndarray, int]:
    """Post-hoc override: "likely to work" calls with a not_callable gate
    become NO-CALL. Pure function of (p, bands, mask, statuses).

    ``statuses``: sequence of status strings aligned with ``p``
    (pass / absence_of_evidence / not_callable). absence_of_evidence calls
    STAND (they are labeled, not flipped); resistant-side calls and existing
    no-calls are untouched. Returns (new_mask, n_flipped).
    """
    p = np.asarray(p, dtype=float)
    mask = np.asarray(base_mask, dtype=bool)
    s_called = (nocall.prediction_sets(p, bands) == 1) & ~mask
    flips = s_called & np.array([s == STATUS_NOT_CALLABLE for s in statuses])
    return mask | flips, int(flips.sum())


def write_gate_json(report: dict[str, dict[str, dict]], path: str | Path,
                    drug_loci: dict[str, tuple[str, ...]] | None = None) -> Path:
    """demo/data/gate_status.json: {drug: {genome_id: {status, detail}}}."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "generated_by": "pipeline.target_gate",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("Batch TSVs report only FOUND resistance mutations, so a "
                   "missing row cannot distinguish screened-WT from "
                   "not-screened; --mutation_all adds one row per screened "
                   "curated position tagged [WILDTYPE]/[UNKNOWN] (verified "
                   "on 562.100000). The corpus was re-screened with "
                   "--mutation_all (features/amrfinder_mutall/): any row at "
                   "a curated locus proves it was called (pass); a locus "
                   "absent from a --mutation_all TSV is genuinely "
                   "not-called. A spaced 31-mer locus check (>=0.75 found) "
                   "is the fallback only when no --mutation_all TSV exists. "
                   "Drugs without curated loci use assembly QC (4-6 Mb, "
                   "<=500 contigs) and are labeled absence-of-evidence."),
        "kmer": {"k": KMER_K, "per_locus": KMER_PER_LOCUS,
                 "callable_frac": CALLABLE_FRAC, "donor": LOCUS_DONOR},
        "qc": {"min_bp": QC_MIN_BP, "max_bp": QC_MAX_BP,
               "max_contigs": QC_MAX_CONTIGS},
        "drug_loci": {d: list(l) for d, l in
                      (drug_loci or DRUG_LOCI).items()},
        "no_call_reason": NO_CALL_REASON,
        "drugs": report,
    }
    path.write_text(json.dumps(envelope, indent=1) + "\n")
    return path


def main(argv=None) -> int:
    """Standalone CLI, e.g. to regenerate the demo gate panel for any set:

      pipeline/.venv/bin/python -m pipeline.target_gate \
        --genomes 562.100000,562.100001 --drugs ciprofloxacin,gentamicin \
        --out demo/data/gate_status.json
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--genomes", required=True,
                    help="comma list or path to a file with one id per line")
    ap.add_argument("--drugs", required=True, help="comma list")
    ap.add_argument("--tsv-dir", default="features/amrfinder")
    ap.add_argument("--fna-dir", default="data/genomes")
    ap.add_argument("--mutall-dir", default="features/amrfinder_mutall")
    ap.add_argument("--out", default="demo/data/gate_status.json")
    args = ap.parse_args(argv)

    g = args.genomes
    if Path(g).is_file():
        genomes = [ln.strip() for ln in Path(g).read_text().splitlines()
                   if ln.strip()]
    else:
        genomes = [s.strip() for s in g.split(",") if s.strip()]
    drugs = [s.strip() for s in args.drugs.split(",") if s.strip()]

    gate = Gate(args.tsv_dir, args.fna_dir, args.mutall_dir)
    report: dict[str, dict[str, dict]] = {}
    for drug in drugs:
        report[drug] = {}
        for gid in genomes:
            report[drug][gid] = gate.gate_status(gid, drug)
        counts = pd.Series([v["status"] for v in report[drug].values()]
                           ).value_counts().to_dict()
        print(f"{drug}: {counts}", file=sys.stderr)
    write_gate_json(report, args.out)
    print(f"wrote {args.out} ({len(genomes)} genomes x {len(drugs)} drugs)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
