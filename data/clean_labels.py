#!/usr/bin/env python3
"""clean_labels.py — audit and clean BV-BRC AST labels for Genome Firewall.

Per species:
  1. AUDIT raw file (rows, genomes, drugs, phenotypes, methods, standards).
  2. Normalize antibiotic names via data/drug_synonyms.yaml
     (unknown buckets are untrusted -> excluded + reported).
  3. MIC-only re-interpretation against data/breakpoints.yaml.
     Drugs whose breakpoint is null are SKIPPED, never guessed.
  4. Deterministic conflict resolution per genome x drug:
     re-derived > newer Testing Standard Year > majority vote > exclude.
  5. Standard-aware I-handling (EUCAST pre/post-2019, CLSI): all I calls
     excluded from binary training, counted by category.
  6. Write data/clean/labels_clean_{species}.csv + data/clean/label_audit_{species}.md

Usage: python clean_labels.py --species ecoli|kpneumoniae|ngonorrhoeae|all
"""

import argparse
import collections
import os
import re
import sys

import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN_DIR = os.path.join(HERE, "clean")

SPECIES_FILES = {
    "ecoli": "labels_ecoli.csv",
    "kpneumoniae": "labels_kpneumoniae.csv",
    "ngonorrhoeae": "labels_ngonorrhoeae.csv",
}

# Human-readable BV-BRC headers we rely on.
COL_GENOME = "Genome ID"
COL_DRUG = "Antibiotic"
COL_PHENO = "Resistant Phenotype"
COL_MEAS = "Measurement"
COL_SIGN = "Measurement Sign"
COL_VALUE = "Measurement Value"
COL_UNIT = "Measurement Unit"
COL_METHOD = "Laboratory Typing Method"
COL_PLATFORM = "Laboratory Typing Platform"
COL_STD = "Testing Standard"
COL_YEAR = "Testing Standard Year"
COL_EVIDENCE = "Evidence"
COL_PMID = "PubMed"

MIC_LIKE_METHODS = {"broth dilution", "agar dilution", "microdilution", "broth microdilution"}
MIC_LIKE_PLATFORMS = ("vitek", "phoenix", "sensititre", "microscan", "etest", "micronaut")

REDEFINED_I_YEAR = 2019  # EUCAST redefined "I" from 2019 onwards

MISSING_COLS_NOTE = "column missing from input"


# ---------------------------------------------------------------------------
# parsing helpers (all defensive: weird input -> None, never an exception)
# ---------------------------------------------------------------------------

def norm_drug_bucket(raw):
    """Normalize a raw Antibiotic bucket for synonym lookup."""
    if raw is None:
        return ""
    s = str(raw).replace("Â", "")  # mojibake seen in the dumps
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def parse_float(x):
    if x is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(x))
    return float(m.group(0)) if m else None


def parse_mic(row):
    """Return (value, sign) or None. Prefers Measurement Value + Sign;
    falls back to parsing the combined 'Measurement' field (e.g. '<=2')."""
    value = parse_float(row.get(COL_VALUE))
    sign = str(row.get(COL_SIGN) or "").strip()
    if value is None:
        m = re.match(r"^\s*(<=|>=|<|>|=)?\s*(\d+(?:\.\d+)?)\s*$",
                     str(row.get(COL_MEAS) or ""))
        if m:
            sign = m.group(1) or "="
            value = float(m.group(2))
    if value is None:
        return None
    if sign not in ("<=", ">=", "<", ">", "="):
        sign = "="  # missing/garbled sign: treat as exact, note nothing
    return value, sign


def is_mic_like(method, platform):
    m = (method or "").strip().lower()
    p = (platform or "").strip().lower()
    if "mic" in m or m in MIC_LIKE_METHODS:
        return True
    return any(k in p for k in MIC_LIKE_PLATFORMS)


def norm_standard(raw):
    s = (raw or "").strip().lower()
    if not s:
        return ""
    has_eu = "eucast" in s
    has_cl = "clsi" in s
    if has_eu and has_cl:
        return "EUCAST+CLSI"
    if has_eu:
        return "EUCAST"
    if has_cl:
        return "CLSI"
    return str(raw).strip()  # e.g. NARMS, AGSP, BSAC: kept verbatim


def parse_year(raw):
    if raw is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(raw))
    return int(m.group(0)) if m else None


def rederive_call(value, sign, bp):
    """Re-derive S(0)/R(1) from an MIC against one breakpoint entry.
    Returns None when the measurement is inconclusive or bp is null."""
    if not bp or bp.get("s_max_mg_l") is None or bp.get("r_min_mg_l") is None:
        return None
    s_max = float(bp["s_max_mg_l"])
    r_min = float(bp["r_min_mg_l"])
    if sign in (">", ">="):
        # true MIC is > value: conclusive only for resistance
        return 1 if value >= r_min else None
    if sign in ("<", "<="):
        # true MIC is <= value: conclusive only for susceptibility
        return 0 if value <= s_max else None
    # exact value
    if value > r_min:
        return 1
    if value <= s_max:
        return 0
    return None


def submitted_call(phenotype):
    p = (phenotype or "").strip().lower()
    if p == "resistant":
        return 1
    if p == "susceptible":
        return 0
    return None  # Intermediate / SDD / Nonsusceptible / empty / other


def i_category(standard, year):
    """Standard-aware category for an 'Intermediate' call (all excluded)."""
    if standard == "EUCAST":
        if year is not None and year >= REDEFINED_I_YEAR:
            return "I EUCAST >=2019 (susceptible, increased exposure)"
        return "I EUCAST pre-2019/unknown-year (uncertain)"
    if standard == "CLSI":
        return "I CLSI (uncertain)"
    return "I other/unknown standard"


# ---------------------------------------------------------------------------
# config loading
# ---------------------------------------------------------------------------

def load_configs():
    with open(os.path.join(HERE, "drug_synonyms.yaml")) as f:
        syn_cfg = yaml.safe_load(f) or {}
    with open(os.path.join(HERE, "breakpoints.yaml")) as f:
        bp_cfg = yaml.safe_load(f) or {}
    synonyms = {norm_drug_bucket(k): v.strip().lower()
                for k, v in (syn_cfg.get("synonyms") or {}).items()}
    canonicals = {c.strip().lower() for c in (syn_cfg.get("known_canonical") or [])}
    return synonyms, canonicals, bp_cfg


# ---------------------------------------------------------------------------
# per-species pipeline
# ---------------------------------------------------------------------------

def process_species(species, synonyms, canonicals, bp_cfg):
    path = os.path.join(HERE, SPECIES_FILES[species])
    bp_species = (bp_cfg or {}).get(species) or {}

    A = collections.Counter()          # flat audit counters
    per_drug_raw = collections.Counter()
    pheno_dist = collections.Counter()
    method_cat = collections.Counter()
    std_year = collections.Counter()
    synonym_hits = collections.Counter()   # (raw, canonical) -> rows
    untrusted = collections.Counter()      # raw bucket -> rows
    mic_rows_per_drug = collections.Counter()
    skipped_bp = collections.Counter()     # drug -> MIC rows skipped (null bp)
    i_excl = collections.Counter()
    other_pheno = collections.Counter()
    flip = collections.defaultdict(lambda: [0, 0])  # drug -> [flips, comparable]
    resolve_stats = collections.Counter()

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    A["input_rows"] = len(df)
    missing = [c for c in (COL_GENOME, COL_DRUG, COL_PHENO, COL_MEAS, COL_SIGN,
                           COL_VALUE, COL_UNIT, COL_METHOD, COL_PLATFORM,
                           COL_STD, COL_YEAR, COL_EVIDENCE) if c not in df.columns]
    for c in missing:  # degrade gracefully: fill absent columns with ""
        df[c] = ""
    A["missing_columns"] = len(missing)

    # evidence check (rows are said to be pre-filtered; verify anyway)
    ev_bad = df[df[COL_EVIDENCE].str.strip() != "Laboratory Method"]
    A["rows_non_lab_evidence"] = len(ev_bad)
    df = df[df[COL_EVIDENCE].str.strip() == "Laboratory Method"]

    A["unique_genomes_raw"] = df[COL_GENOME].nunique()

    rows = []  # per-row working records
    for r in df.itertuples(index=False):
        rec = dict(zip(df.columns, r))
        raw_drug = rec[COL_DRUG]
        bucket = norm_drug_bucket(raw_drug)
        per_drug_raw[bucket] += 1

        # --- drug normalization ---
        if bucket in synonyms:
            drug = synonyms[bucket]
            synonym_hits[(bucket, drug)] += 1
        elif bucket in canonicals:
            drug = bucket
        else:
            untrusted[bucket] += 1
            continue

        pheno = rec[COL_PHENO].strip()
        pheno_dist[pheno or "(empty)"] += 1

        method = rec[COL_METHOD].strip()
        mic_like = is_mic_like(method, rec[COL_PLATFORM])
        if mic_like:
            method_cat["MIC-like"] += 1
        elif "disk" in method.lower():
            method_cat["Disk diffusion"] += 1
        else:
            method_cat["Other/unknown"] += 1

        std = norm_standard(rec[COL_STD])
        year = parse_year(rec[COL_YEAR])
        std_year[(std or "(none)", year if year is not None else "(none)")] += 1

        # --- MIC re-interpretation ---
        mic = parse_mic(rec) if mic_like else None
        rederived = None
        if mic is not None and (rec[COL_UNIT].strip() in ("mg/L", "")):
            mic_rows_per_drug[drug] += 1
            bp = bp_species.get(drug)
            if not bp or bp.get("s_max_mg_l") is None or bp.get("r_min_mg_l") is None:
                skipped_bp[drug] += 1
            else:
                rederived = rederive_call(mic[0], mic[1], bp)

        sub = submitted_call(pheno)
        if sub is not None and rederived is not None:
            flip[drug][1] += 1
            if sub != rederived:
                flip[drug][0] += 1

        # --- I / non-binary handling (counted here, excluded from pool) ---
        p_low = pheno.lower()
        if p_low == "intermediate":
            i_excl[i_category(std, year)] += 1
        elif sub is None and p_low not in ("",):
            other_pheno[pheno] += 1

        rows.append({
            "genome_id": rec[COL_GENOME].strip(),
            "drug": drug,
            "sub": sub,
            "rederived": rederived,
            "std": std,
            "year": year,
        })

    A["rows_trusted_drugs"] = len(rows)
    A["rows_untrusted_drugs"] = sum(untrusted.values())

    # ------------------------------------------------------------------
    # conflict resolution per genome x drug
    # ------------------------------------------------------------------
    groups = collections.defaultdict(list)
    for rec in rows:
        groups[(rec["genome_id"], rec["drug"])].append(rec)

    final = []
    conflicts_excluded = collections.Counter()  # drug -> groups excluded
    for (gid, drug), grecs in groups.items():
        pool = [r for r in grecs if r["rederived"] is not None]
        source = "rederived"
        if not pool:
            pool = [r for r in grecs if r["sub"] is not None]
            source = "submitted"
        if not pool:
            resolve_stats["groups_no_binary_call"] += 1
            continue
        resolve_stats[f"groups_pool_{source}"] += 1

        # newer Testing Standard Year wins: drop rows with older known years
        years = [r["year"] for r in pool if r["year"] is not None]
        if years:
            ymax = max(years)
            dated = [r for r in pool if r["year"] == ymax]
            if dated:
                pool = dated
                resolve_stats["groups_year_filtered"] += 1

        votes = collections.Counter(r["rederived"] if source == "rederived"
                                    else r["sub"] for r in pool)
        label, top = votes.most_common(1)[0]
        if len(votes) > 1 and list(votes.values()).count(top) > 1:
            conflicts_excluded[drug] += 1
            resolve_stats["groups_excluded_conflict"] += 1
            continue
        if len(votes) > 1:
            resolve_stats["groups_majority_vote"] += 1

        winner = next(r for r in pool
                      if (r["rederived"] if source == "rederived" else r["sub"]) == label)
        final.append({
            "genome_id": gid,
            "antibiotic": drug,
            "label": label,
            "label_source": source,
            "testing_standard": winner["std"],
            "testing_standard_year": winner["year"] if winner["year"] is not None else "",
            "n_source_rows": len(grecs),
        })

    resolve_stats["groups_total"] = len(groups)

    # ------------------------------------------------------------------
    # outputs
    # ------------------------------------------------------------------
    os.makedirs(CLEAN_DIR, exist_ok=True)
    out_csv = os.path.join(CLEAN_DIR, f"labels_clean_{species}.csv")
    out_df = pd.DataFrame(final, columns=[
        "genome_id", "antibiotic", "label", "label_source",
        "testing_standard", "testing_standard_year", "n_source_rows"])
    out_df = out_df.sort_values(["genome_id", "antibiotic"]).reset_index(drop=True)
    out_df.to_csv(out_csv, index=False)

    final_counts = collections.Counter()
    final_genomes = set()
    for r in final:
        final_counts[(r["antibiotic"], r["label"])] += 1
        final_genomes.add(r["genome_id"])

    audit_path = os.path.join(CLEAN_DIR, f"label_audit_{species}.md")
    write_audit(audit_path, species, A, per_drug_raw, pheno_dist, method_cat,
                std_year, synonym_hits, untrusted, mic_rows_per_drug, skipped_bp,
                i_excl, other_pheno, flip, resolve_stats, conflicts_excluded,
                final_counts, len(final_genomes), len(out_df), missing, out_csv)
    return out_csv, audit_path, len(out_df)


def write_audit(path, species, A, per_drug_raw, pheno_dist, method_cat,
                std_year, synonym_hits, untrusted, mic_rows_per_drug, skipped_bp,
                i_excl, other_pheno, flip, resolve_stats, conflicts_excluded,
                final_counts, n_final_genomes, n_final_labels, missing_cols, out_csv):
    L = []
    w = L.append
    w(f"# Label audit — {species}")
    w("")
    w("## 1. Raw file")
    w(f"- input rows (lab-evidence kept): **{A['input_rows']}**")
    w(f"- rows dropped, Evidence != 'Laboratory Method': {A['rows_non_lab_evidence']}")
    w(f"- unique genomes (raw): **{A['unique_genomes_raw']}**")
    if missing_cols:
        w(f"- MISSING COLUMNS (filled with empty strings, degraded gracefully): "
          f"{', '.join(missing_cols)}")
    w("")
    w("## 2. Phenotype distribution (trusted-drug rows)")
    for k, v in pheno_dist.most_common():
        w(f"- {k}: {v}")
    w("")
    w("## 3. Method distribution (trusted-drug rows)")
    for k, v in method_cat.most_common():
        w(f"- {k}: {v}")
    w("")
    w("## 4. Testing standard x year (trusted-drug rows)")
    for (std, yr), v in sorted(std_year.items(), key=lambda x: -x[1]):
        w(f"- {std} / {yr}: {v}")
    w("")
    w("## 5. Drug-name normalization")
    w(f"- rows kept on trusted drugs: {A['rows_trusted_drugs']}")
    w(f"- rows on UNTRUSTED buckets (excluded): {A['rows_untrusted_drugs']}")
    if synonym_hits:
        w("")
        w("Synonym mappings applied (raw bucket -> canonical: rows):")
        for (raw, canon), v in sorted(synonym_hits.items(), key=lambda x: -x[1]):
            w(f"- `{raw}` -> `{canon}`: {v}")
    if untrusted:
        w("")
        w("Untrusted buckets (NOT in synonym map / canonical list — excluded, flagged):")
        for raw, v in untrusted.most_common():
            w(f"- `{raw}`: {v}")
    w("")
    w("## 6. Per-drug raw row counts (all buckets, pre-normalization)")
    w("| raw bucket | rows |")
    w("|---|---|")
    for k, v in per_drug_raw.most_common():
        w(f"| {k} | {v} |")
    w("")
    w("## 7. MIC re-interpretation")
    w(f"- MIC-parseable rows per drug (mg/L, MIC-like method/platform):")
    if mic_rows_per_drug:
        for k, v in mic_rows_per_drug.most_common():
            w(f"  - {k}: {v}")
    else:
        w("  - none")
    w("")
    w("- Drugs SKIPPED because their breakpoint is null in breakpoints.yaml")
    w("  (placeholder entries — TODO: fill from current EUCAST table; never guessed):")
    if skipped_bp:
        for k, v in skipped_bp.most_common():
            w(f"  - **{k}**: {v} MIC rows skipped")
    else:
        w("  - none")
    w("")
    w("### Flip-rate (submitted S/R call vs re-derived call, same row)")
    any_comparable = any(v[1] for v in flip.values())
    if any_comparable:
        tot_f = sum(v[0] for v in flip.values())
        tot_c = sum(v[1] for v in flip.values())
        w(f"- HEADLINE: {tot_f}/{tot_c} comparable rows disagree "
          f"({100.0 * tot_f / tot_c:.2f}%)")
        w("- per drug (flips/comparable, %):")
        for drug, (f, c) in sorted(flip.items()):
            if c:
                w(f"  - {drug}: {f}/{c} ({100.0 * f / c:.2f}%)")
    else:
        w("- N/A: no rows have both a submitted call and a re-derived call "
          "(all breakpoints are null placeholders — see skipped list above).")
    w("")
    w("## 8. I-handling exclusions (standard-aware, all excluded from binary training)")
    for k, v in i_excl.most_common():
        w(f"- {k}: {v}")
    if not i_excl:
        w("- none")
    w("")
    w("Other non-binary phenotypes (excluded, counted):")
    for k, v in other_pheno.most_common():
        w(f"- {k}: {v}")
    if not other_pheno:
        w("- none")
    w("")
    w("## 9. Conflict resolution per genome x drug")
    w(f"- genome x drug groups: {resolve_stats['groups_total']}")
    w(f"- groups entering re-derived MIC pool: {resolve_stats['groups_pool_rederived']}")
    w(f"- groups entering submitted-call pool: {resolve_stats['groups_pool_submitted']}")
    w("  (pool counts are taken before tie-exclusion, so excluded groups are included here)")
    w(f"- year-filter applied (newer Testing Standard Year kept): {resolve_stats['groups_year_filtered']}")
    w(f"- decided by majority vote: {resolve_stats['groups_majority_vote']}")
    w(f"- EXCLUDED as still-conflicting (tie after all steps): {resolve_stats['groups_excluded_conflict']}")
    if conflicts_excluded:
        w("- excluded groups per drug:")
        for k, v in conflicts_excluded.most_common():
            w(f"  - {k}: {v}")
    w(f"- groups with no binary call at all (I/empty/other only): {resolve_stats['groups_no_binary_call']}")
    w("")
    w("## 10. Final clean labels")
    w(f"- unique genomes with >=1 label: **{n_final_genomes}**")
    w(f"- final labels (one per genome x drug): **{n_final_labels}**")
    w(f"- output: `{out_csv}`")
    w("")
    w("| antibiotic | R (1) | S (0) | total |")
    w("|---|---|---|---|")
    drugs = sorted({d for d, _ in final_counts})
    for d in drugs:
        r_ = final_counts.get((d, 1), 0)
        s_ = final_counts.get((d, 0), 0)
        w(f"| {d} | {r_} | {s_} | {r_ + s_} |")
    w("")
    with open(path, "w") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", required=True,
                    choices=list(SPECIES_FILES) + ["all"])
    args = ap.parse_args()
    synonyms, canonicals, bp_cfg = load_configs()
    targets = list(SPECIES_FILES) if args.species == "all" else [args.species]
    for sp in targets:
        csv_path, audit_path, n = process_species(sp, synonyms, canonicals, bp_cfg)
        print(f"[{sp}] {n} clean labels -> {csv_path}")
        print(f"[{sp}] audit -> {audit_path}")


if __name__ == "__main__":
    sys.exit(main())
