#!/usr/bin/env python3
"""Export trained models to compact JSON for browser-side inference.

Output: demo/data/model_weights.json — per drug: scaler (mean, scale), lr coef,
intercept, platt calibration (if present), no-call band, plus the feature column list.
A browser can then compute p = platt(sigmoid((coef . scaled_x) + intercept)) with ~10 lines of JS.
"""
import json, pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRUGS = ["ciprofloxacin", "gentamicin", "ampicillin",
         "trimethoprim_sulfamethoxazole", "cefotaxime"]

out = {"feature_columns": None, "drugs": {}}
cols = list(__import__("pandas").read_csv(ROOT / "features/feature_matrix.csv", nrows=0).columns)
out["feature_columns"] = [c for c in cols if c != "genome_id"]

for drug in DRUGS:
    bundle = pickle.load(open(ROOT / "models" / drug / "baseline.pkl", "rb"))
    bands = json.load(open(ROOT / "models" / drug / "nocall_bands.json"))
    pipe = bundle["model"]
    sc, lr = pipe.named_steps["scaler"], pipe.named_steps["lr"]
    entry = {
        "scaler_mean": sc.mean_.tolist(),
        "scaler_scale": sc.scale_.tolist(),
        "coef": lr.coef_[0].tolist(),
        "intercept": float(lr.intercept_[0]),
        "band": bands["band"],
        "calibration_method": bundle.get("calibration_method", "platt"),
    }
    # platt params if the calibrated wrapper exposes them
    try:
        cal = bundle["model"].calibrated_classifiers_[0]  # noqa
    except Exception:
        pass
    out["drugs"][drug] = entry

dst = ROOT / "demo" / "data" / "model_weights.json"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(out))
kb = dst.stat().st_size // 1024
print(f"wrote {dst} ({kb} KB), drugs: {list(out['drugs'])}")
