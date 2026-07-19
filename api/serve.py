#!/usr/bin/env python3
"""Genome Firewall inference API.

Serves per-drug antibiotic-response predictions (likely to fail / likely to work /
no-call) for genomes present in the feature matrix, or for raw feature vectors.

Run:  ../pipeline/.venv/bin/python serve.py  (from api/, or anywhere)
Test: curl -X POST localhost:8000/predict -H 'Content-Type: application/json' \
        -d '{"genome_id": "562.100000"}'
"""
import json, pickle
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DRUGS = ["ciprofloxacin", "gentamicin", "ampicillin",
         "trimethoprim_sulfamethoxazole", "cefotaxime"]

app = FastAPI(title="Genome Firewall API", version="0.2.0",
              description="Research prototype. Confirm all results with standard "
                          "laboratory susceptibility testing.")

# --- load artifacts once at startup ---
MODELS, BANDS = {}, {}
for drug in DRUGS:
    MODELS[drug] = pickle.load(open(ROOT / "models" / drug / "baseline.pkl", "rb"))["calibrated"]
    BANDS[drug] = json.load(open(ROOT / "models" / drug / "nocall_bands.json"))
FM = pd.read_csv(ROOT / "features" / "feature_matrix.csv",
                 dtype={"genome_id": str}).set_index("genome_id")
FEAT_COLS = list(FM.columns)


class PredictRequest(BaseModel):
    genome_id: str | None = None
    features: dict[str, float] | None = None
    drugs: list[str] | None = None


def verdict(drug: str, p: float) -> dict:
    band = BANDS[drug]["band"]  # [work_threshold, fail_threshold]
    if p <= band[0]:
        call = "likely to work"
    elif p >= band[1]:
        call = "likely to fail"
    else:
        call = "no-call"
    return {"p_fail": round(p, 4), "verdict": call,
            "bands": {"work_below": round(band[0], 4), "fail_above": round(band[1], 4)}}


@app.get("/health")
def health():
    return {"status": "ok", "drugs": DRUGS, "genomes_cached": len(FM),
            "disclaimer": "Research prototype — confirm with standard lab testing."}


@app.post("/predict")
def predict(req: PredictRequest):
    if req.genome_id:
        if req.genome_id not in FM.index:
            raise HTTPException(404, f"genome_id {req.genome_id} not in feature matrix")
        X = FM.loc[[req.genome_id]]
    elif req.features:
        X = pd.DataFrame([{c: req.features.get(c, 0) for c in FEAT_COLS}], columns=FEAT_COLS)
    else:
        raise HTTPException(400, "provide genome_id or features")

    out = {}
    for drug in (req.drugs or DRUGS):
        if drug not in MODELS:
            raise HTTPException(400, f"unknown drug {drug}")
        p = float(MODELS[drug].predict_proba(X)[0][1])
        out[drug] = verdict(drug, p)
    return {"genome_id": req.genome_id,
            "predictions": out,
            "disclaimer": "Research prototype — confirm with standard laboratory "
                          "susceptibility testing."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
