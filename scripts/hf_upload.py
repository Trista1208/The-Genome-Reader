#!/usr/bin/env python3
"""Package Genome Firewall models for Hugging Face Hub and upload.

Usage:
  pipeline/.venv/bin/python scripts/hf_upload.py --prepare   # local staging only (safe)
  pipeline/.venv/bin/python scripts/hf_upload.py --push --repo-id USER/genome-firewall-ecoli

Requires `hf auth login` (or HF_TOKEN env) for --push.
"""
import argparse, json, pickle, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "dist" / "hf_model_repo"
DRUGS = ["ciprofloxacin", "gentamicin", "ampicillin",
         "trimethoprim_sulfamethoxazole", "cefotaxime"]


def build_card(repo_id: str) -> str:
    metrics = json.loads((ROOT / "reports/metrics.json").read_text())
    rows = []
    for drug, d in metrics.items():
        h = d["groups"]["heldout_group"]
        rows.append(
            f"| {drug} | {h['balanced_accuracy']:.3f} | {h['recall_resistant']:.2f} "
            f"| {h['recall_susceptible']:.2f} | {h['auroc']:.3f} | {h['no_call_rate']:.2f} "
            f"| {h['accuracy_after_no_call']:.3f} |")
    table = "\n".join(rows)
    return f"""---
license: mit
tags:
- sklearn
- skops
- antimicrobial-resistance
- genomics
- tabular-classification
library_name: skops
---

# Genome Firewall — E. coli antibiotic response models

Per-drug elastic-net logistic regression models predicting, from AMRFinderPlus
gene/mutation features of a reconstructed E. coli genome, whether an antibiotic is
**likely to fail / likely to work / no-call** (abstain when evidence is weak).

**Research prototype. All predictions must be confirmed with standard laboratory
susceptibility testing. Not a medical device.**

## Metrics (held-out genetic groups — clusters never seen in training)

| drug | balanced acc | R recall | S recall | AUROC | no-call rate | acc when called |
|---|---|---|---|---|---|---|
{table}

Evaluation: skani (ANI >= 99.5%) single-linkage clusters; train/cal/test/hidden split by
cluster. Labels: BV-BRC lab-measured AST re-derived against EUCAST v16.1 breakpoints.

## Contents
- `models/<drug>/model.skops` — the calibrated classifier (skops format, safe to load)
- `models/<drug>/nocall_bands.json` — asymmetric class-conditional conformal bands
- `features/feature_columns.json` — the 600 feature names (AMRFinderPlus 4.2.7 / DB 2026-03-24.1)

## Usage
```python
import skops.io as sio
from huggingface_hub import hf_hub_download
path = hf_hub_download(repo_id="{repo_id}", filename="models/ciprofloxacin/model.skops")
clf = sio.load(path, trusted=True)  # skops: safe deserialization
# X = feature vector aligned with features/feature_columns.json (0/1 per AMR element)
# proba = clf.predict_proba(X)
```

Pipeline to produce features from a FASTA + full report:
https://github.com/Trista1208/The-Genome-Reader (branch sprint/baseline)

Built at Hack-Nation 6th Global AI Hackathon.
"""


def prepare() -> None:
    import skops.io as sio
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "models").mkdir(parents=True)
    for drug in DRUGS:
        src = ROOT / "models" / drug / "baseline.pkl"
        with open(src, "rb") as f:
            clf = pickle.load(f)  # our own artifact, trusted
        dst_dir = STAGE / "models" / drug
        dst_dir.mkdir(parents=True)
        sio.dump(clf, dst_dir / "model.skops")
        bands = ROOT / "models" / drug / "nocall_bands.json"
        if bands.exists():
            shutil.copy(bands, dst_dir / "nocall_bands.json")
        print(f"  {drug}: skops written")
    # feature columns
    import pandas as pd
    cols = list(pd.read_csv(ROOT / "features/feature_matrix.csv", nrows=0).columns)
    (STAGE / "features").mkdir(exist_ok=True)
    (STAGE / "features" / "feature_columns.json").write_text(json.dumps(cols))
    print(f"  features: {len(cols)} columns")


def push(repo_id: str) -> None:
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)
    (STAGE / "README.md").write_text(build_card(repo_id))
    api.upload_folder(repo_id=repo_id, folder_path=str(STAGE), repo_type="model")
    print(f"UPLOADED -> https://huggingface.co/{repo_id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--repo-id", default="")
    a = ap.parse_args()
    if a.prepare:
        prepare()
    if a.push:
        assert a.repo_id, "--repo-id USER/genome-firewall-ecoli required"
        push(a.repo_id)
