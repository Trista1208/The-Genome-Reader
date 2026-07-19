#!/usr/bin/env python3
"""gf_infer.py — Genome Firewall inference core.

Turns an AMRFinderPlus v4 TSV (one genome) into per-drug antibiotic-response
predictions in the shape the Next.js app expects.

Reused by serve.py. The heavy FASTA -> AMRFinderPlus step is done by the caller
(run_amrfinder); this module only does TSV -> features -> model -> app contract.

Model:  Darkroom4364/genome-firewall-ecoli (elastic-net LR, Platt-calibrated).
Output: the model's predict_proba[...,1] is p_fail (probability of resistance).
        The app's `score` means "probability the antibiotic is EFFECTIVE", so
        score = 1 - p_fail. The no-call bands decide work / fail / abstain.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import skops.io as sio

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "features"))

from build_feature_matrix import parse_tsv  # noqa: E402  (reused, verbatim)
import map_evidence as mev  # noqa: E402  (reused, verbatim)

DRUGS = [
    "ciprofloxacin",
    "gentamicin",
    "ampicillin",
    "trimethoprim_sulfamethoxazole",
    "cefotaxime",
]

# UI label (lower-cased) -> model key. The app sends human labels.
LABEL_TO_KEY = {
    "ciprofloxacin": "ciprofloxacin",
    "gentamicin": "gentamicin",
    "ampicillin": "ampicillin",
    "cefotaxime": "cefotaxime",
    "trimethoprim / sulfamethoxazole": "trimethoprim_sulfamethoxazole",
    "trimethoprim/sulfamethoxazole": "trimethoprim_sulfamethoxazole",
    "trimethoprim-sulfamethoxazole": "trimethoprim_sulfamethoxazole",
    "trimethoprim_sulfamethoxazole": "trimethoprim_sulfamethoxazole",
    "sxt": "trimethoprim_sulfamethoxazole",
    "co-trimoxazole": "trimethoprim_sulfamethoxazole",
}

# 600 model features, in the exact order the models were trained on
# (verified: == every model's feature_names_in_).
FEAT_COLS = [c for c in json.load(open(ROOT / "features" / "feature_columns.json")) if c != "genome_id"]

_META = json.load(open(ROOT / "features" / "metadata.json"))
MODEL_VERSION = f"GFR-ECOLI / AMRFinderPlus {_META['tool_version']} / DB {_META['database_version']}"

# --- load models + bands once ---
_MODELS: dict = {}
_BANDS: dict = {}
for _d in DRUGS:
    _p = ROOT / "models" / _d / "model.skops"
    _bundle = sio.load(_p, trusted=sio.get_untrusted_types(file=_p))
    _MODELS[_d] = _bundle["model"]
    _BANDS[_d] = json.load(open(ROOT / "models" / _d / "nocall_bands.json"))

_DRUG_MAP = mev.load_map(ROOT / "features" / "drug_class_map.yaml")


def resolve_drug(name: str) -> str:
    """Map a UI label or key to a canonical model drug key."""
    key = (name or "").strip().lower()
    if key in LABEL_TO_KEY:
        return LABEL_TO_KEY[key]
    if key in DRUGS:
        return key
    raise KeyError(f"unsupported antibiotic: {name!r}")


def features_from_tsv(tsv_path: str | Path) -> pd.DataFrame:
    """AMRFinderPlus TSV (one genome) -> 1x600 aligned binary feature frame."""
    feats = parse_tsv(Path(tsv_path), Counter())
    row = {c: (1 if c in feats else 0) for c in FEAT_COLS}
    return pd.DataFrame([row], columns=FEAT_COLS, dtype="uint8")


def _verdict(drug: str, p_fail: float) -> str:
    low, high = _BANDS[drug]["band"]  # [work_below, fail_above]
    if p_fail <= low:
        return "likely_effective"
    if p_fail >= high:
        return "likely_ineffective"
    return "uncertain"


def _evidence(tsv_path: str | Path, drug: str, verdict: str) -> tuple[str, list[dict]]:
    """Return (evidence_class, detected_genes) for the drug."""
    try:
        canon = mev.norm_drug_name(drug, _DRUG_MAP["drugs"])
        hits = mev.map_hits(mev.read_amrfinder_tsv(str(tsv_path)), _DRUG_MAP["drugs"][canon])
    except (KeyError, ValueError):
        hits = []
    confirmed = [h for h in hits if h.get("confidence") == "confirmed"]
    genes = [
        {"symbol": h["element_symbol"], "name": h["element_name"],
         "tier": h["tier"], "confidence": h["confidence"]}
        for h in hits
    ]
    if confirmed:
        evidence = "known_marker"
    elif hits or verdict != "likely_effective":
        evidence = "statistical_association"
    else:
        evidence = "no_known_signal"
    return evidence, genes


def features_from_dict(features: dict) -> pd.DataFrame:
    """Raw {feature_name: 0/1} dict -> 1x600 aligned binary feature frame."""
    row = {c: (1 if float(features.get(c, 0)) else 0) for c in FEAT_COLS}
    return pd.DataFrame([row], columns=FEAT_COLS, dtype="uint8")


def _build_result(antibiotic: str, drug: str, X: pd.DataFrame, evidence_fn) -> dict:
    p_fail = float(_MODELS[drug].predict_proba(X)[0][1])
    verdict = _verdict(drug, p_fail)
    evidence, genes = evidence_fn(verdict)
    score = round(1.0 - p_fail, 4)
    # Confidence: how decisively p_fail clears the nearest no-call boundary,
    # scaled to [0,1]. A called verdict scores >=0.5; a no-call is inherently low.
    low, high = _BANDS[drug]["band"]
    if verdict == "likely_effective":
        confidence = 0.5 + 0.5 * (low - p_fail) / (low if low > 1e-6 else 1.0)
    elif verdict == "likely_ineffective":
        confidence = 0.5 + 0.5 * (p_fail - high) / ((1.0 - high) if (1.0 - high) > 1e-6 else 1.0)
    else:
        confidence = 0.3
    confidence = max(0.05, min(1.0, confidence))
    return {
        "antibiotic": antibiotic,
        "drug": drug,
        "score": score,
        "pFail": round(p_fail, 4),
        "confidence": round(float(confidence), 4),
        "classification": verdict,
        "noCall": verdict == "uncertain",
        "evidence": evidence,
        "detectedGenes": genes,
        "modelVersion": MODEL_VERSION,
        "bands": {"workBelow": round(low, 4), "failAbove": round(high, 4)},
    }


def predict_one(tsv_path: str | Path, antibiotic: str) -> dict:
    """Full app-contract prediction for one drug from one genome's AMRFinder TSV."""
    drug = resolve_drug(antibiotic)
    X = features_from_tsv(tsv_path)
    return _build_result(antibiotic, drug, X, lambda verdict: _evidence(tsv_path, drug, verdict))


def predict_from_features(features: dict, antibiotic: str) -> dict:
    """Prediction from a precomputed feature vector (skips AMRFinder).
    Without a TSV there is no gene-level evidence, so the evidence class is
    inferred from the verdict."""
    drug = resolve_drug(antibiotic)
    X = features_from_dict(features)

    def ev(verdict: str) -> tuple[str, list[dict]]:
        cls = "no_known_signal" if verdict == "likely_effective" else "statistical_association"
        return cls, []

    return _build_result(antibiotic, drug, X, ev)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--drug", default=None, help="one drug, or all if omitted")
    args = ap.parse_args()
    drugs = [args.drug] if args.drug else DRUGS
    for d in drugs:
        print(json.dumps(predict_one(args.tsv, d), indent=1))
