#!/usr/bin/env python3
"""Build demo_bundle.json for the Colab notebook: curated genomes with features,
lab labels, per-drug probabilities + verdicts + bands, evidence hits, and the
held-out metrics summary. Uploaded to the HF model repo so the notebook needs
nothing local."""
import json, pickle
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DRUGS = ["ciprofloxacin", "gentamicin", "ampicillin",
         "trimethoprim_sulfamethoxazole", "cefotaxime"]
DRUG_DISPLAY = {"trimethoprim_sulfamethoxazole": "trimethoprim/sulfamethoxazole"}
CURATED = {
    "resistant": "562.140931",
    "susceptible": "562.100280",
    "refusal": "562.100124",
}

fm = pd.read_csv(ROOT / "features/feature_matrix.csv", dtype={"genome_id": str}).set_index("genome_id")
lab = pd.read_csv(ROOT / "data/clean/labels_clean_ecoli.csv", dtype={"genome_id": str})
metrics = json.loads((ROOT / "reports/metrics.json").read_text())

models, bands = {}, {}
for d in DRUGS:
    models[d] = pickle.load(open(ROOT / "models" / d / "baseline.pkl", "rb"))["calibrated"]
    bands[d] = json.load(open(ROOT / "models" / d / "nocall_bands.json"))["band"]

# evidence hits per genome from its AMRFinderPlus TSV
import csv
def hits(gid):
    p = ROOT / "features/amrfinder" / f"{gid}.tsv"
    if not p.exists():
        return []
    out = []
    for row in csv.DictReader(open(p), delimiter="\t"):
        if row.get("Scope") == "core" and row.get("Subtype") not in ("AMR", "POINT", "POINT_DISRUPT"):
            continue
        if row.get("Subtype") in ("AMR", "POINT", "POINT_DISRUPT"):
            out.append({"symbol": row["Element symbol"], "subtype": row["Subtype"],
                        "class": row.get("Class", ""), "subclass": row.get("Subclass", ""),
                        "method": row.get("Method", "")})
    return out

bundle = {"drugs": DRUGS, "drug_display": DRUG_DISPLAY, "feature_columns": list(fm.columns),
          "genomes": {}, "metrics_heldout": {}}
for story, gid in CURATED.items():
    X = fm.loc[[gid]]
    glab = lab[lab.genome_id == gid].set_index("antibiotic")["label"].to_dict()
    preds = {}
    for d in DRUGS:
        p = float(models[d].predict_proba(X)[0][1])
        lo, hi = bands[d]
        verdict = "likely to work" if p <= lo else ("likely to fail" if p >= hi else "no-call")
        preds[d] = {"p_fail": round(p, 4), "verdict": verdict, "band": [round(lo, 4), round(hi, 4)]}
    bundle["genomes"][story] = {
        "genome_id": gid, "features": {c: int(v) for c, v in X.iloc[0].items() if v != 0},
        "lab_labels": glab, "predictions": preds, "evidence_hits": hits(gid),
        "n_resistance_features": int((X.iloc[0] != 0).sum()),
    }
for d in DRUGS:
    mkey = DRUG_DISPLAY.get(d, d)
    h = metrics[mkey]["groups"]["heldout_group"] if mkey in metrics else metrics[d]["groups"]["heldout_group"]
    bundle["metrics_heldout"][d] = {k: h[k] for k in
        ["n", "n_resistant", "balanced_accuracy", "recall_resistant", "recall_susceptible",
         "auroc", "pr_auc", "brier", "no_call_rate", "accuracy_after_no_call"]}

out = ROOT / "dist" / "demo_bundle.json"
out.write_text(json.dumps(bundle))
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
for story, g in bundle["genomes"].items():
    print(f"  {story}: {g['genome_id']} | {g['n_resistance_features']} resistance features | cipro {g['predictions']['ciprofloxacin']}")
