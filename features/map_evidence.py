#!/usr/bin/env python3
"""map_evidence.py — map AMRFinderPlus hits to per-drug spectrum-confirmed resistance evidence.

Reads an AMRFinderPlus v4 TSV (headers: Element symbol, Element name, Scope,
Type, Subtype, Class, Subclass, Method, ...) and a curated mapping table
(drug_class_map.yaml, same directory by default), and prints the hits that
count as evidence category (i) "spectrum-confirmed known resistance" for the
requested drug, each annotated with:
  - the mapping rule that fired and its confidence (confirmed | review)
  - evidence tier: full_gene (EXACT/ALLELE/BLAST method), degraded
    (PARTIAL/PARTIAL_CONTIG_END/INTERNAL_STOP/HMM), point (curated mutation)

Usage:
  python map_evidence.py AMRFINDER.tsv --drug ciprofloxacin
  python map_evidence.py AMRFINDER.tsv --drug sxt --confirmed-only --format json
  python map_evidence.py --selftest          # no inputs needed

Exit codes: 0 ok (also when zero hits), 2 usage/data error, 1 selftest failure.
Stdlib + PyYAML only.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import yaml

DEFAULT_MAP = Path(__file__).resolve().parent / "drug_class_map.yaml"

POINT_SUBTYPES = {"POINT", "POINT_DISRUPT"}
FULL_GENE_METHODS = {"EXACT", "ALLELE", "BLAST"}
DEGRADED_METHODS = {"PARTIAL", "PARTIAL_CONTIG_END", "INTERNAL_STOP", "HMM"}


def norm_drug_name(name: str, drugs: dict) -> str:
    """Resolve a drug name/alias to the canonical key in the YAML."""
    key = name.strip().lower()
    if key in drugs:
        return key
    for canon, spec in drugs.items():
        if key in [a.lower() for a in spec.get("aliases", [])]:
            return canon
    raise KeyError(name)


def method_base(method: str) -> str:
    """Strip the X/P/N search-type suffix (EXACTX->EXACT, POINTN->POINT)."""
    m = method.strip().upper()
    if m.endswith(("X", "P", "N")) and m[:-1] in (
        FULL_GENE_METHODS | DEGRADED_METHODS | {"POINT"}
    ):
        return m[:-1]
    return m


def tier_of(hit: dict) -> str:
    subtype = hit.get("Subtype", "").strip().upper()
    method = hit.get("Method", "").strip()
    if subtype in POINT_SUBTYPES or method_base(method) == "POINT":
        return "point"
    base = method_base(method)
    if base in FULL_GENE_METHODS:
        return "full_gene"
    if base in DEGRADED_METHODS:
        return "degraded"
    return "unknown"


class CompiledRule:
    def __init__(self, rule: dict):
        self.name = rule["name"]
        self.confidence = rule.get("confidence", "review")
        self.component = rule.get("component")
        self.note = rule.get("note", "")
        m = rule.get("match", {})
        self.subtype = m.get("subtype")  # None | "AMR" | "POINT"
        self.symbol_re = re.compile(m["symbol_regex"]) if "symbol_regex" in m else None
        self.class_re = re.compile(m["class_regex"]) if "class_regex" in m else None
        self.subclass_re = (
            re.compile(m["subclass_regex"]) if "subclass_regex" in m else None
        )

    def matches(self, hit: dict) -> bool:
        subtype = hit.get("Subtype", "").strip().upper()
        if self.subtype == "AMR" and subtype != "AMR":
            return False
        if self.subtype == "POINT" and subtype not in POINT_SUBTYPES:
            return False
        if self.symbol_re and not self.symbol_re.search(hit.get("Element symbol", "")):
            return False
        if self.class_re and not self.class_re.search(hit.get("Class", "")):
            return False
        if self.subclass_re and not self.subclass_re.search(hit.get("Subclass", "")):
            return False
        return True


def load_map(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def map_hits(hits: list[dict], drug_spec: dict) -> list[dict]:
    """Return hits matching any rule of drug_spec, annotated."""
    rules = [CompiledRule(r) for r in drug_spec.get("rules", [])]
    excl = drug_spec.get("exclude_symbol_regex")
    excl_re = re.compile(excl) if excl else None
    out = []
    for hit in hits:
        symbol = hit.get("Element symbol", "")
        if excl_re and excl_re.search(symbol):
            continue
        for rule in rules:
            if rule.matches(hit):
                row = {
                    "element_symbol": symbol,
                    "element_name": hit.get("Element name", ""),
                    "rule": rule.name,
                    "confidence": rule.confidence,
                    "tier": tier_of(hit),
                    "method": hit.get("Method", ""),
                    "subtype": hit.get("Subtype", ""),
                    "class": hit.get("Class", ""),
                    "subclass": hit.get("Subclass", ""),
                    "component": rule.component or "",
                }
                out.append(row)
                break  # first matching rule wins; rules are ORed
    return out


def read_amrfinder_tsv(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        missing = {"Element symbol", "Subtype", "Class", "Subclass", "Method"} - set(
            reader.fieldnames or []
        )
        if missing:
            raise ValueError(
                f"{path}: not an AMRFinderPlus v4 TSV — missing headers: {sorted(missing)}"
            )
        return list(reader)


# --------------------------------------------------------------------- selftest
def _hit(symbol, name, subtype, cls, subcls, method):
    return {
        "Element symbol": symbol,
        "Element name": name,
        "Subtype": subtype,
        "Class": cls,
        "Subclass": subcls,
        "Method": method,
    }


SELFTEST_CASES = [
    # (hit, drug, expect_match, expect_confidence, expect_tier)
    # -- required case 1: QRDR points -> ciprofloxacin
    (_hit("gyrA_S83L", "quinolone resistant GyrA", "POINT", "QUINOLONE", "QUINOLONE", "POINTX"),
     "ciprofloxacin", True, "confirmed", "point"),
    (_hit("parC_E84V", "quinolone resistant ParC", "POINT", "QUINOLONE", "QUINOLONE", "POINTX"),
     "ciprofloxacin", True, "confirmed", "point"),
    (_hit("gyrA_D87N", "quinolone resistant GyrA", "POINT", "QUINOLONE", "QUINOLONE", "POINTX"),
     "ciprofloxacin", True, "confirmed", "point"),
    (_hit("parE_I529L", "quinolone resistant ParE", "POINT", "QUINOLONE", "QUINOLONE", "POINTX"),
     "ciprofloxacin", True, "confirmed", "point"),
    # -- required case 2: narrow-spectrum blaTEM must NOT map to cefotaxime
    (_hit("blaTEM-1", "broad-spectrum class A beta-lactamase TEM-1", "AMR", "BETA-LACTAM", "BETA-LACTAM", "ALLELEX"),
     "cefotaxime", False, None, None),
    (_hit("blaTEM-1", "broad-spectrum class A beta-lactamase TEM-1", "AMR", "BETA-LACTAM", "BETA-LACTAM", "ALLELEX"),
     "ampicillin", True, "confirmed", "full_gene"),
    # ESBL TEM allele DOES map (allele-awareness sanity)
    (_hit("blaTEM-68", "extended-spectrum class A beta-lactamase TEM-68", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "ALLELEX"),
     "cefotaxime", True, "confirmed", "full_gene"),
    # -- CTX-M: 3GC yes, carbapenem no
    (_hit("blaCTX-M-15", "extended-spectrum class A beta-lactamase CTX-M-15", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "ALLELEX"),
     "cefotaxime", True, "confirmed", "full_gene"),
    (_hit("blaCTX-M-15", "extended-spectrum class A beta-lactamase CTX-M-15", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "ALLELEX"),
     "ceftazidime", True, "confirmed", "full_gene"),
    (_hit("blaCTX-M-15", "extended-spectrum class A beta-lactamase CTX-M-15", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "ALLELEX"),
     "meropenem", False, None, None),
    # partial CTX-M still maps but as degraded evidence
    (_hit("blaCTX-M-15", "extended-spectrum class A beta-lactamase CTX-M-15", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "PARTIALX"),
     "cefotaxime", True, "confirmed", "degraded"),
    # -- carbapenemases
    (_hit("blaKPC-3", "carbapenem-hydrolyzing class A beta-lactamase KPC-3", "AMR", "BETA-LACTAM", "CARBAPENEM", "ALLELEX"),
     "meropenem", True, "confirmed", "full_gene"),
    (_hit("blaKPC-3", "carbapenem-hydrolyzing class A beta-lactamase KPC-3", "AMR", "BETA-LACTAM", "CARBAPENEM", "ALLELEX"),
     "cefotaxime", True, "confirmed", "full_gene"),
    (_hit("blaOXA-48", "carbapenem-hydrolyzing class D beta-lactamase OXA-48", "AMR", "BETA-LACTAM", "CARBAPENEM", "ALLELEX"),
     "meropenem", True, "confirmed", "full_gene"),
    (_hit("blaOXA-48", "carbapenem-hydrolyzing class D beta-lactamase OXA-48", "AMR", "BETA-LACTAM", "CARBAPENEM", "ALLELEX"),
     "cefotaxime", False, None, None),  # OXA-48: carbapenems only, NOT 3GC
    # -- intrinsic blaEC must map to nothing (every E. coli carries it)
    (_hit("blaEC", "BlaEC family class C beta-lactamase", "AMR", "BETA-LACTAM", "BETA-LACTAM", "BLASTX"),
     "cefotaxime", False, None, None),
    (_hit("blaEC-5", "cephalosporin-hydrolyzing class C beta-lactamase EC-5", "AMR", "BETA-LACTAM", "CEPHALOSPORIN", "ALLELEX"),
     "cefotaxime", False, None, None),
    (_hit("blaEC", "BlaEC family class C beta-lactamase", "AMR", "BETA-LACTAM", "BETA-LACTAM", "BLASTX"),
     "ampicillin", False, None, None),
    # -- aminoglycosides: substrate awareness
    (_hit("ant(2'')-Ia", "aminoglycoside nucleotidyltransferase ANT(2'')-Ia", "AMR", "AMINOGLYCOSIDE", "GENTAMICIN/KANAMYCIN/TOBRAMYCIN", "EXACTX"),
     "gentamicin", True, "confirmed", "full_gene"),
    (_hit("aac(3)-IIa", "aminoglycoside N-acetyltransferase AAC(3)-IIa", "AMR", "AMINOGLYCOSIDE", "GENTAMICIN", "EXACTX"),
     "gentamicin", True, "confirmed", "full_gene"),
    (_hit("aac(6')-Ib", "aminoglycoside N-acetyltransferase AAC(6')-Ib", "AMR", "AMINOGLYCOSIDE", "AMIKACIN/KANAMYCIN/TOBRAMYCIN", "EXACTX"),
     "gentamicin", False, None, None),  # canonical aac(6')-Ib: tobra/amik only
    (_hit("rmtB", "16S rRNA methyltransferase RmtB", "AMR", "AMINOGLYCOSIDE", "AMINOGLYCOSIDE", "EXACTX"),
     "gentamicin", True, "confirmed", "full_gene"),  # generic subclass -> symbol rule
    (_hit("aph(3')-IIa", "aminoglycoside O-phosphotransferase APH(3')-IIa", "AMR", "AMINOGLYCOSIDE", "KANAMYCIN", "EXACTX"),
     "gentamicin", True, "review", "full_gene"),  # sources conflict -> review
    (_hit("aadA5", "ANT(3'')-Ia family aminoglycoside nucleotidyltransferase AadA5", "AMR", "AMINOGLYCOSIDE", "STREPTOMYCIN", "EXACTX"),
     "gentamicin", False, None, None),
    # -- qnr / aac(6')-Ib-cr -> ciprofloxacin
    (_hit("qnrB19", "quinolone resistance pentapeptide repeat protein QnrB19", "AMR", "QUINOLONE", "QUINOLONE", "EXACTX"),
     "ciprofloxacin", True, "confirmed", "full_gene"),
    (_hit("aac(6')-Ib-cr", "aminoglycoside N-acetyltransferase AAC(6')-Ib-cr", "AMR", "AMINOGLYCOSIDE/QUINOLONE", "AMIKACIN/KANAMYCIN/QUINOLONE/TOBRAMYCIN", "EXACTX"),
     "ciprofloxacin", True, "confirmed", "full_gene"),
    # -- SXT components
    (_hit("sul1", "sulfonamide-resistant dihydropteroate synthase Sul1", "AMR", "SULFONAMIDE", "SULFONAMIDE", "EXACTX"),
     "sxt", True, "confirmed", "full_gene"),
    (_hit("dfrA17", "trimethoprim-resistant dihydrofolate reductase DfrA17", "AMR", "TRIMETHOPRIM", "TRIMETHOPRIM", "EXACTX"),
     "sxt", True, "confirmed", "full_gene"),
    (_hit("folP_F28L", "sulfamethoxazole resistant FolP", "POINT", "SULFONAMIDE", "SULFONAMIDE", "POINTX"),
     "trimethoprim-sulfamethoxazole", True, "confirmed", "point"),
    # degraded INTERNAL_STOP gene still maps, tier degraded
    (_hit("sul2", "sulfonamide-resistant dihydropteroate synthase Sul2", "AMR", "SULFONAMIDE", "SULFONAMIDE", "INTERNAL_STOPX"),
     "sxt", True, "confirmed", "degraded"),
]


def run_selftest(map_path: Path) -> int:
    spec = load_map(map_path)
    drugs = spec["drugs"]
    failures = []
    for hit, drug, want_match, want_conf, want_tier in SELFTEST_CASES:
        canon = norm_drug_name(drug, drugs)
        res = map_hits([hit], drugs[canon])
        got_match = bool(res)
        sym = hit["Element symbol"]
        if got_match != want_match:
            failures.append(
                f"{sym} vs {drug}: match={got_match}, want {want_match}"
            )
            continue
        if got_match and (want_conf or want_tier):
            row = res[0]
            if want_conf and row["confidence"] != want_conf:
                failures.append(
                    f"{sym} vs {drug}: confidence={row['confidence']}, want {want_conf}"
                )
            if want_tier and row["tier"] != want_tier:
                failures.append(
                    f"{sym} vs {drug}: tier={row['tier']}, want {want_tier}"
                )
    # SXT component labels
    sxt = drugs[norm_drug_name("sxt", drugs)]
    comps = {
        r["element_symbol"]: r["component"]
        for r in map_hits(
            [
                _hit("sul1", "", "AMR", "SULFONAMIDE", "SULFONAMIDE", "EXACTX"),
                _hit("dfrA17", "", "AMR", "TRIMETHOPRIM", "TRIMETHOPRIM", "EXACTX"),
            ],
            sxt,
        )
    }
    if comps.get("sul1") != "sulfamethoxazole" or comps.get("dfrA17") != "trimethoprim":
        failures.append(f"SXT component labels wrong: {comps}")
    if failures:
        print("SELFTEST FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"selftest: {len(SELFTEST_CASES) + 1} checks passed", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Map AMRFinderPlus v4 TSV hits to per-drug spectrum-confirmed resistance evidence."
    )
    ap.add_argument("tsv", nargs="?", help="AMRFinderPlus v4 output TSV")
    ap.add_argument("--drug", help="drug name or alias (e.g. ciprofloxacin, sxt, meropenem)")
    ap.add_argument("--map", default=str(DEFAULT_MAP), help="path to drug_class_map.yaml")
    ap.add_argument("--confirmed-only", action="store_true", help="drop confidence=review hits")
    ap.add_argument("--format", choices=["tsv", "json"], default="tsv")
    ap.add_argument("--list-drugs", action="store_true", help="print known drugs and exit")
    ap.add_argument("--selftest", action="store_true", help="run built-in checks and exit")
    args = ap.parse_args(argv)

    map_path = Path(args.map)
    if args.selftest:
        return run_selftest(map_path)

    spec = load_map(map_path)
    drugs = spec["drugs"]
    if args.list_drugs:
        for canon, d in drugs.items():
            print(f"{canon}\t{','.join(d.get('aliases', []))}")
        return 0
    if not args.tsv or not args.drug:
        ap.error("TSV and --drug are required (or use --selftest / --list-drugs)")
    try:
        canon = norm_drug_name(args.drug, drugs)
    except KeyError:
        print(f"error: unknown drug '{args.drug}' (try --list-drugs)", file=sys.stderr)
        return 2
    try:
        hits = read_amrfinder_tsv(args.tsv)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    rows = map_hits(hits, drugs[canon])
    if args.confirmed_only:
        rows = [r for r in rows if r["confidence"] == "confirmed"]

    if args.format == "json":
        json.dump({"drug": canon, "n_hits": len(rows), "hits": rows}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        cols = [
            "element_symbol", "rule", "confidence", "tier", "method",
            "subtype", "class", "subclass", "component", "element_name",
        ]
        w = csv.DictWriter(sys.stdout, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    n_conf = sum(1 for r in rows if r["confidence"] == "confirmed")
    n_rev = len(rows) - n_conf
    tiers = {}
    for r in rows:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    tier_s = ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())) or "none"
    print(
        f"# {canon}: {len(rows)} evidence hits ({n_conf} confirmed, {n_rev} review); tiers: {tier_s}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
