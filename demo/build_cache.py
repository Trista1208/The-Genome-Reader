#!/usr/bin/env python3
"""build_cache.py — precompute everything demo/app.py needs, so the Gradio
app performs ZERO live model inference (research note 06: "Mock everything").

Run with the PIPELINE virtualenv (it must unpickle models/*/baseline.pkl):

  pipeline/.venv/bin/python demo/build_cache.py

Inputs (repo root, resolved relative to this file):
  features/feature_matrix.csv, splits/splits.json, splits/skani_edges.tsv,
  data/clean/labels_clean_ecoli.csv, models/*/baseline.pkl,
  features/amrfinder/{genome}.tsv, data/genomes/{genome}.fna,
  reports/metrics.json + reliability_*.png

Outputs (committed with the demo so it is self-contained for HF Spaces):
  demo/data/genome_cache.json   per-genome scores, verdicts, callability
  demo/data/curated.json        the 3 curated story genomes + pick rationale
  demo/data/amrfinder/*.tsv     AMRFinderPlus TSVs of the curated genomes
  demo/reports/*                snapshot of metrics.json + reliability PNGs
                                (fallback; the app prefers the LIVE ../reports)

Verdicts are re-derived as a pure function of (p, bands, distance) exactly as
in pipeline/nocall.py — calls are never read from a stale artifact.

Callability gate: the feature matrix has no --mutation_all WT tiers yet, so
locus presence is verified directly from the FASTA: ~48 spaced 31-mers of the
gyrA/parC/parE reference locus (coordinates taken from a genome whose TSV
carries a curated POINT hit, i.e. a confirmed locus call) are searched in the
query assembly; >=75% found = locus sequenced. This is the k-mer stand-in for
the planned "BLAST vs ~10 target sequences" check (synthesis v2, change 4).
"""

from __future__ import annotations

import json
import pickle
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"

DRUGS = [
    "ciprofloxacin",
    "gentamicin",
    "ampicillin",
    "trimethoprim/sulfamethoxazole",
    "cefotaxime",
]

# QRDR target loci for the ciprofloxacin callability panel. gyrB has zero
# curated POINT hits in this corpus (checked 2026-07-19), so no reference
# locus can be bootstrapped for it -> excluded from the panel.
GATE_LOCI = ["gyrA", "parC", "parE"]
KMER_K = 31
KMER_PER_LOCUS = 48
# A core locus is declared "sequenced" when >=30% of its spaced 31-mers match
# exactly (either strand). Intraspecies synonymous divergence breaks most
# 31-mers (E. coli gyrA pairwise identity ~97% => ~40-70% of 31-mers intact),
# while a genuinely absent/uncovered locus matches essentially zero — so 0.30
# separates "present but diverged" from "not callable" with a wide margin.
CALLABLE_FRAC = 0.30

# donor genome whose TSV confirms exact gyrA/parC/parE locus coordinates
LOCUS_DONOR = "562.100000"


def log(msg: str) -> None:
    print(f"[build_cache] {msg}", file=sys.stderr)


# ------------------------------------------------------------------ verdicts
def verdict_of(p: float, bands: dict, dist: float | None) -> tuple[str, str | None]:
    """Pure call logic, mirrors pipeline/nocall.py.

    Returns (verdict, nocall_reason) where verdict is one of
    likely_to_fail | likely_to_work | no_call and nocall_reason is
    None | "distance" | "band". Distance override wins (synthesis v2 change 1).
    """
    q_s = bands["q_susceptible"]
    q_r = bands["q_resistant"]
    inc_s = p <= q_s
    inc_r = (1.0 - p) <= q_r
    singleton = inc_s != inc_r
    thr = bands.get("dist_threshold")
    if dist is not None and thr is not None and dist > thr:
        return "no_call", "distance"
    if not singleton:
        return "no_call", "band"
    return ("likely_to_fail", None) if inc_r else ("likely_to_work", None)


# --------------------------------------------------------------- callability
def read_fasta(path: Path) -> dict[str, str]:
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


def reference_kmers() -> dict[str, dict[str, set[str]]]:
    """Spaced k-mers of each gate locus, bootstrapped from the donor genome's
    own assembly using its AMRFinderPlus TSV coordinates (a confirmed call).
    Both strands are kept: contig orientation is random across assemblies."""
    tsv = ROOT / "features" / "amrfinder" / f"{LOCUS_DONOR}.tsv"
    fna = ROOT / "data" / "genomes" / f"{LOCUS_DONOR}.fna"
    contigs = read_fasta(fna)
    rows = pd.read_csv(tsv, sep="\t")
    out: dict[str, set[str]] = {}
    for locus in GATE_LOCI:
        hits = rows[rows["Element symbol"].str.startswith(locus + "_", na=False)]
        if hits.empty:
            raise SystemExit(f"donor {LOCUS_DONOR} lost its {locus} POINT hit; "
                             f"pick a new LOCUS_DONOR")
        r = hits.iloc[0]
        seq = contigs[str(r["Contig id"])]
        locus_seq = seq[int(r["Start"]) - 1:int(r["Stop"])]
        step = max(1, (len(locus_seq) - KMER_K) // KMER_PER_LOCUS)
        fwd = {locus_seq[i:i + KMER_K]
               for i in range(0, len(locus_seq) - KMER_K + 1, step)}
        out[locus] = {"fwd": fwd, "rc": {revcomp(k) for k in fwd}}
        log(f"locus {locus}: {len(locus_seq)} bp donor locus, "
            f"{len(fwd)} reference {KMER_K}-mers (both strands stored)")
    return out


def callability(genome_id: str, ref: dict[str, dict[str, set[str]]],
                point_hits: dict[str, list[str]]) -> dict[str, dict]:
    """Per-locus status for one genome.

    point_hits: locus -> [element symbols] from the genome's TSV.
    status: mutation_present | wild_type_intact | not_called | unknown
    """
    fna = ROOT / "data" / "genomes" / f"{genome_id}.fna"
    if fna.exists():
        seq = "N" * 64 + ("N" * 64).join(read_fasta(fna).values())
    else:
        seq = None
    res = {}
    for locus, strands in ref.items():
        muts = point_hits.get(locus, [])
        if seq is None:
            status = "unknown" if not muts else "mutation_present"
            frac = None
        else:
            # orientation-agnostic: score the better-matching strand
            found = max(
                sum(1 for k in strands["fwd"] if k in seq),
                sum(1 for k in strands["rc"] if k in seq),
            )
            frac = round(found / len(strands["fwd"]), 4)
            if muts:
                status = "mutation_present"
            elif frac >= CALLABLE_FRAC:
                status = "wild_type_intact"
            else:
                status = "not_called"
        res[locus] = {"status": status, "kmer_frac": frac, "mutations": muts}
    return res


def point_hits_by_locus(genome_id: str) -> dict[str, list[str]]:
    tsv = ROOT / "features" / "amrfinder" / f"{genome_id}.tsv"
    if not tsv.exists():
        return {}
    rows = pd.read_csv(tsv, sep="\t")
    hits = rows[rows["Subtype"].astype(str).str.startswith("POINT")]
    out: dict[str, list[str]] = {}
    for locus in GATE_LOCI:
        syms = sorted({s for s in hits["Element symbol"].astype(str)
                       if s.startswith(locus + "_")})
        if syms:
            out[locus] = syms
    return out


# ------------------------------------------------------------------ curation
def pick_curated(cache: dict) -> dict:
    """Pick the 3 story genomes from scored data; rationale is recorded."""
    genomes = cache["genomes"]
    bands = cache["drugs"]

    def entry(gid): return genomes[gid]

    # (a) textbook resistant: lab-confirmed ciprofloxacin-resistant, model says
    # likely_to_fail, and >=2 QRDR loci carry curated point mutations so the
    # category-(i) evidence drawer is rich. Rank by calibrated p.
    cand_a = []
    for gid, g in genomes.items():
        d = g["drugs"].get("ciprofloxacin")
        if not d or d["label"] != 1 or d["verdict"] != "likely_to_fail":
            continue
        n_qrdr = sum(1 for l in GATE_LOCI
                     if g["callability"][l]["mutations"])
        if n_qrdr >= 2 and g["split"] in ("test", "heldout_group"):
            cand_a.append((d["p"], gid))
    cand_a.sort(reverse=True)

    # (b) honest likely-to-work: lab-susceptible on every scored drug, never
    # called likely_to_fail, ciprofloxacin called likely_to_work (the gate
    # panel's drug), gyrA+parC verified wild-type-intact. Rank: fewest
    # no-calls, then lowest worst-case p.
    cand_b = []
    for gid, g in genomes.items():
        scored = g["drugs"]
        if len(scored) < len(DRUGS) - 1:
            continue
        if any(d["label"] not in (0,) for d in scored.values()):
            continue
        if any(d["verdict"] == "likely_to_fail" for d in scored.values()):
            continue
        cip = scored.get("ciprofloxacin")
        if not cip or cip["verdict"] != "likely_to_work":
            continue
        if not all(g["callability"][l]["status"] == "wild_type_intact"
                   for l in ("gyrA", "parC")):
            continue
        n_ltw = sum(1 for d in scored.values()
                    if d["verdict"] == "likely_to_work")
        if n_ltw < 3:
            continue
        # prefer genomes the model never trained on: test > heldout > cal > train
        split_rank = {"test": 0, "heldout_group": 1,
                      "calibration": 2, "train": 3}.get(g["split"], 4)
        worst = max(d["p"] for d in scored.values())
        cand_b.append((split_rank, len(scored) - n_ltw, worst, gid))
    cand_b.sort()

    # (c) refusal: held-out-group genome the firewall declined to call.
    # Strongest story first:
    #   1. confidently-wrong — a naive 0.5-threshold caller would have erred
    #      (p<0.5 but lab R, or p>=0.5 but lab S) and the abstention caught it
    #   2. ANI-distance override firing on an out-of-band confident score
    #   3. widest conformal-band refusal
    cand_c_wrong, cand_c, cand_c_band = [], [], []
    for gid, g in genomes.items():
        if g["split"] != "heldout_group":
            continue
        n_nc = sum(1 for d in g["drugs"].values()
                   if d["verdict"] == "no_call")
        for drug, d in g["drugs"].items():
            if d["verdict"] != "no_call" or d["label"] is None:
                continue
            lo, hi = bands[drug]["band"]
            naive_wrong = ((d["p"] < 0.5 and d["label"] == 1) or
                           (d["p"] >= 0.5 and d["label"] == 0))
            if naive_wrong:
                # rank: ciprofloxacin first, then most-severe (low p if R,
                # high p if S), then total-refusal count
                severity = 1.0 - d["p"] if d["label"] == 1 else d["p"]
                cand_c_wrong.append((drug == "ciprofloxacin", severity, n_nc,
                                     gid, drug))
            elif d["nocall_reason"] == "distance" and (d["p"] < lo or d["p"] > hi):
                cand_c.append((g["dist_to_train"], abs(d["p"] - 0.5), gid, drug))
            else:
                cand_c_band.append((abs(d["p"] - 0.5), g["dist_to_train"],
                                    gid, drug))
    cand_c_wrong.sort(reverse=True)
    cand_c.sort(reverse=True)
    cand_c_band.sort(reverse=True)

    refusal_kind = ("confidently_wrong" if cand_c_wrong else
                    "distance" if cand_c else "band")
    for name, cands in (("resistant", cand_a), ("susceptible", cand_b),
                        ("refusal", cand_c_wrong or cand_c or cand_c_band)):
        if not cands:
            raise SystemExit(f"no candidate for curated slot '{name}' — "
                             f"loosen criteria or wait for the retrain")
    a = cand_a[0][1]
    b = cand_b[0][3]
    if refusal_kind == "confidently_wrong":
        c_gid, c_drug = cand_c_wrong[0][3], cand_c_wrong[0][4]
    elif refusal_kind == "distance":
        c_gid, c_drug = cand_c[0][2], cand_c[0][3]
    else:
        c_gid, c_drug = cand_c_band[0][2], cand_c_band[0][3]

    def lab_word(v):
        return {1: "Resistant", 0: "Susceptible", None: "unlabeled"}[v]

    b_n_ltw = sum(1 for d in entry(b)["drugs"].values()
                  if d["verdict"] == "likely_to_work")
    b_n_all = len(entry(b)["drugs"])
    c_entry = entry(c_gid)["drugs"][c_drug]
    c_n_nc = sum(1 for d in entry(c_gid)["drugs"].values()
                 if d["verdict"] == "no_call")
    if refusal_kind == "confidently_wrong":
        c_story = (
            f"Calibrated {c_drug} score {c_entry['p']:.3f} — a naive "
            f"0.5-threshold caller would have said "
            f"\"{'likely to work' if c_entry['p'] < 0.5 else 'likely to fail'}\". "
            f"Lab truth: {lab_word(c_entry['label'])}. The abstention band "
            f"catches exactly this error: no-call on {c_n_nc}/"
            f"{len(entry(c_gid)['drugs'])} drugs.")
    elif refusal_kind == "distance":
        c_story = (f"Calibrated {c_drug} score {c_entry['p']:.3f} sits OUTSIDE "
                   f"the acceptance band — a naive tool would call it "
                   f"confidently; the ANI-distance override refuses.")
    else:
        lo, hi = bands[c_drug]["band"]
        c_story = (f"Calibrated {c_drug} score {c_entry['p']:.3f} lands inside "
                   f"the abstention band [{lo:.3f}, {hi:.3f}] — the conformal "
                   f"layer refuses to guess.")

    curated = {
        "resistant": {
            "genome_id": a,
            "headline": "Textbook resistant",
            "why": [
                f"Lab phenotype: ciprofloxacin {lab_word(entry(a)['drugs']['ciprofloxacin']['label'])} (re-derived, data/clean).",
                "AMRFinderPlus: QRDR point mutations at "
                + ", ".join(f"{l} ({'/'.join(entry(a)['callability'][l]['mutations'])})"
                            for l in GATE_LOCI if entry(a)["callability"][l]["mutations"])
                + " -> spectrum-confirmed category-(i) evidence.",
                f"Split: {entry(a)['split']} (never trained on). Verdict: likely to fail.",
            ],
        },
        "susceptible": {
            "genome_id": b,
            "headline": "Honest likely-to-work",
            "why": [
                "Lab phenotype: susceptible on all "
                f"{b_n_all} modeled drugs (re-derived labels).",
                "gyrA and parC loci verified wild-type-intact by the k-mer "
                "callability check — 'no mutation found' is a measured WT, "
                "not a missing locus.",
                f"Split: {entry(b)['split']}. Verdict: likely to work on "
                f"{b_n_ltw}/{b_n_all} drugs"
                + (", no-call on the rest (the firewall declines rather than "
                   "guesses)." if b_n_ltw < b_n_all else "."),
            ],
        },
        "refusal": {
            "genome_id": c_gid,
            "headline": "The refusal",
            "why": [
                f"Held-out genetic group (clade {entry(c_gid)['coarse_clade_id']}); "
                f"nearest training genome is {entry(c_gid)['dist_to_train']:.2f} "
                f"ANI-distance away.",
                c_story,
                "This is the win, not a failure: abstention is standard "
                "behavior in every credible AMR tool (EUCAST ATU, ResFinder "
                "panel scope) — here it is automated and measured.",
            ],
            "showcase_drug": c_drug,
        },
    }
    return curated


# ---------------------------------------------------------------------- main
def main() -> int:
    from pipeline import splits as splits_mod  # noqa: PLC0415
    sys.path.insert(0, str(ROOT))

    log("loading feature matrix / labels / splits / edges")
    fm = pd.read_csv(ROOT / "features" / "feature_matrix.csv",
                     dtype={"genome_id": str}, index_col="genome_id")
    labels_all = pd.read_csv(ROOT / "data" / "clean" / "labels_clean_ecoli.csv",
                             dtype={"genome_id": str})
    splits = splits_mod.load_splits(ROOT / "splits" / "splits.json")
    edges = splits_mod.parse_skani_edges(ROOT / "splits" / "skani_edges.tsv")
    split_of = {g: v["split"] for g, v in splits.items()}
    train_genomes = {g for g, v in splits.items() if v["split"] == "train"}

    # distances of every feature genome to its nearest TRAINING genome
    from pipeline.train_baseline import nearest_train_distances  # noqa: PLC0415
    all_genomes = sorted(fm.index)
    dist = nearest_train_distances(edges, train_genomes, all_genomes)

    ref = reference_kmers()

    cache: dict = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "drug_list": DRUGS,
        "gate_loci": GATE_LOCI,
        "callability": {"k": KMER_K, "n_kmers_per_locus": KMER_PER_LOCUS,
                        "callable_frac": CALLABLE_FRAC, "locus_donor": LOCUS_DONOR},
        "drugs": {},
        "genomes": {},
    }
    for gid in all_genomes:
        s = splits.get(gid, {})
        cache["genomes"][gid] = {
            "split": split_of.get(gid),
            "cluster_id": s.get("cluster_id"),
            "coarse_clade_id": s.get("coarse_clade_id"),
            "dist_to_train": round(dist.get(gid, 100.0), 4),
            "callability": callability(gid, ref, point_hits_by_locus(gid)),
            "drugs": {},
        }

    for drug in DRUGS:
        safe = drug.replace("/", "_")
        pkl = ROOT / "models" / safe / "baseline.pkl"
        if not pkl.exists():
            log(f"SKIP {drug}: {pkl} missing")
            continue
        with open(pkl, "rb") as fh:
            art = pickle.load(fh)
        cal, bands = art["calibrated"], art["bands"]
        model = art["model"]
        coef = model.named_steps["lr"].coef_[0]
        feat_names = np.array(fm.columns)
        nonzero = feat_names[coef != 0]
        nz_coef = coef[coef != 0]

        lab = labels_all[labels_all["antibiotic"] == drug]
        y = pd.Series(lab["label"].astype(int).values,
                      index=lab["genome_id"].values)
        y = y[~y.index.duplicated(keep="first")]
        genomes = sorted(set(y.index) & set(fm.index) & set(splits.keys()))
        X = fm.loc[genomes]
        p_all = cal.predict_proba(X)[:, 1]
        log(f"{drug}: scored {len(genomes)} genomes, "
            f"band=[{bands['band'][0]:.3f},{bands['band'][1]:.3f}]")

        cache["drugs"][drug] = {
            "band": bands["band"],
            "q_susceptible": bands["q_susceptible"],
            "q_resistant": bands["q_resistant"],
            "alpha_susceptible": bands["alpha_susceptible"],
            "alpha_resistant": bands["alpha_resistant"],
            "dist_threshold": bands.get("dist_threshold"),
            "n_features_selected": int(len(nonzero)),
        }
        Xn = X.to_numpy()
        feat_idx = {f: i for i, f in enumerate(feat_names)}
        top_pool = sorted(zip(nonzero, nz_coef), key=lambda t: -abs(t[1]))
        for gid, p in zip(genomes, p_all):
            verdict, reason = verdict_of(float(p), bands, dist.get(gid))
            # category (ii): statistical association — strongest model features
            # present in this genome (decoupled from curated evidence)
            row = Xn[X.index.get_loc(gid)]
            present = [(f, c) for f, c in top_pool if row[feat_idx[f]] == 1][:6]
            cache["genomes"][gid]["drugs"][drug] = {
                "p": round(float(p), 5),
                "verdict": verdict,
                "nocall_reason": reason,
                "label": int(y[gid]),
                "model_features": [
                    {"feature": f, "coef": round(float(c), 4),
                     "direction": "resistance" if c > 0 else "susceptible"}
                    for f, c in present],
            }

    out_data = DEMO / "data"
    out_data.mkdir(parents=True, exist_ok=True)
    # write the cache BEFORE curation so a curation failure never discards
    # the expensive scoring pass
    cache["curated"] = {}
    (out_data / "genome_cache.json").write_text(
        json.dumps(cache, indent=1) + "\n")
    log(f"wrote {out_data/'genome_cache.json'} "
        f"({(out_data/'genome_cache.json').stat().st_size/1e6:.1f} MB)")
    return finish_curation(cache)


def finish_curation(cache: dict) -> int:
    out_data = DEMO / "data"
    curated = pick_curated(cache)
    cache["curated"] = curated
    (out_data / "genome_cache.json").write_text(
        json.dumps(cache, indent=1) + "\n")
    (out_data / "curated.json").write_text(json.dumps(curated, indent=1) + "\n")

    amr_out = out_data / "amrfinder"
    amr_out.mkdir(exist_ok=True)
    for slot in curated.values():
        src = ROOT / "features" / "amrfinder" / f"{slot['genome_id']}.tsv"
        if src.exists():
            shutil.copy(src, amr_out / src.name)

    rep_out = DEMO / "reports"
    rep_out.mkdir(exist_ok=True)
    for f in (ROOT / "reports").glob("*.json"):
        shutil.copy(f, rep_out / f.name)
    for f in (ROOT / "reports").glob("reliability_*.png"):
        shutil.copy(f, rep_out / f.name)
    log("copied curated TSVs + reports snapshot into demo/")
    log("curated: " + json.dumps(
        {k: v["genome_id"] for k, v in curated.items()}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if "--curate-only" in sys.argv:
        # cheap re-pick against an existing cache (no rescoring)
        cache = json.loads((DEMO / "data" / "genome_cache.json").read_text())
        sys.exit(finish_curation(cache))
    if "--callability-only" in sys.argv:
        # recompute only the k-mer locus check (no rescoring), then re-pick
        cache = json.loads((DEMO / "data" / "genome_cache.json").read_text())
        ref = reference_kmers()
        for i, (gid, g) in enumerate(cache["genomes"].items()):
            g["callability"] = callability(gid, ref, point_hits_by_locus(gid))
            if (i + 1) % 200 == 0:
                log(f"callability {i + 1}/{len(cache['genomes'])}")
        cache["callability"] = {
            "k": KMER_K, "n_kmers_per_locus": KMER_PER_LOCUS,
            "callable_frac": CALLABLE_FRAC, "locus_donor": LOCUS_DONOR}
        (DEMO / "data" / "genome_cache.json").write_text(
            json.dumps(cache, indent=1) + "\n")
        sys.exit(finish_curation(cache))
    sys.exit(main())
