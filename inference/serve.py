#!/usr/bin/env python3
"""Genome Firewall inference API — FASTA -> antibiotic-response prediction.

The Next.js app (via a Convex action) POSTs a genome FASTA + a target antibiotic;
this service runs AMRFinderPlus, builds the 600-feature vector, runs the calibrated
model, and returns the exact contract the app renders.

Run locally (shells out to Docker for AMRFinderPlus):
    ./.venv/bin/uvicorn serve:app --host 0.0.0.0 --port 8000

Deployed (Dockerfile is based on the AMRFinderPlus image, so `amrfinder` is a
local binary and no Docker-in-Docker is needed).

Endpoints:
    GET  /health
    POST /predict   {"fasta": "...", "antibiotic": "Ciprofloxacin"}
                    {"fasta": "...", "drugs": ["ciprofloxacin", ...]}   # all/subset
                    {"features": {...}, "antibiotic": "..."}            # skip AMRFinder
                    {"genome_id": "...", "features": {...}}             # back-compat
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import gf_infer as gf

THIS = Path(__file__).resolve().parent
AMRFINDER_IMAGE = os.environ.get(
    "AMRFINDER_IMAGE", "staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1"
)
AMRFINDER_THREADS = os.environ.get("AMRFINDER_THREADS", "4")
# Optional shared-secret: if set, callers must send it as `Authorization: Bearer <token>`.
API_TOKEN = os.environ.get("INFERENCE_API_TOKEN")

app = FastAPI(
    title="Genome Firewall API",
    version="1.0.0",
    description="Research prototype. Confirm all results with standard laboratory "
    "susceptibility testing.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    fasta: str | None = None
    antibiotic: str | None = None
    drugs: list[str] | None = None
    features: dict[str, float] | None = None
    genome_id: str | None = None


def _have_amrfinder_binary() -> bool:
    return shutil.which("amrfinder") is not None


def run_amrfinder(fasta_text: str) -> str:
    """FASTA text -> path of an AMRFinderPlus v4 TSV. Uses a local binary if present,
    otherwise a one-shot Docker run (local dev)."""
    workdir = Path(tempfile.mkdtemp(prefix="gf_"))
    fna = workdir / "genome.fna"
    tsv = workdir / "genome.tsv"
    fna.write_text(fasta_text)

    if _have_amrfinder_binary():
        cmd = [
            "amrfinder", "-n", str(fna), "-O", "Escherichia", "--plus",
            "-o", str(tsv), "--threads", AMRFINDER_THREADS, "--name", "query",
        ]
    else:
        cmd = [
            "docker", "run", "--rm", "--platform", "linux/amd64",
            "-v", f"{workdir}:/data", AMRFINDER_IMAGE,
            "amrfinder", "-n", "/data/genome.fna", "-O", "Escherichia", "--plus",
            "-o", "/data/genome.tsv", "--threads", AMRFINDER_THREADS, "--name", "query",
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if proc.returncode != 0 or not tsv.exists():
        raise HTTPException(
            502,
            f"AMRFinderPlus failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout or '')[-400:]}",
        )
    return str(tsv)


def _check_auth(authorization: str | None) -> None:
    if API_TOKEN and authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(401, "missing or invalid Authorization bearer token")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "drugs": gf.DRUGS,
        "modelVersion": gf.MODEL_VERSION,
        "amrfinder": "binary" if _have_amrfinder_binary() else "docker",
        "disclaimer": "Research prototype — confirm with standard lab testing.",
    }


@app.post("/predict")
def predict(req: PredictRequest, authorization: str | None = None):
    _check_auth(authorization)

    # Resolve the feature source: FASTA (run AMRFinder) or a raw feature vector.
    tsv_path: str | None = None
    if req.fasta:
        tsv_path = run_amrfinder(req.fasta)
    elif req.features is None:
        raise HTTPException(400, "provide `fasta` or `features`")

    # Which drugs to score.
    if req.antibiotic:
        try:
            targets = [gf.resolve_drug(req.antibiotic)]
        except KeyError as e:
            raise HTTPException(400, str(e))
    elif req.drugs:
        targets = []
        for d in req.drugs:
            try:
                targets.append(gf.resolve_drug(d))
            except KeyError as e:
                raise HTTPException(400, str(e))
    else:
        targets = gf.DRUGS

    def score(drug: str) -> dict:
        if tsv_path is not None:
            return gf.predict_one(tsv_path, drug)
        return gf.predict_from_features(req.features or {}, drug)

    results = {gf.resolve_drug(d): score(d) for d in targets}

    # The app sends a single antibiotic → return that result at the top level so
    # the Convex action can read {score, classification, ...} directly.
    if req.antibiotic:
        top = results[gf.resolve_drug(req.antibiotic)]
        return {**top, "genome_id": req.genome_id, "predictions": results}
    return {"genome_id": req.genome_id, "predictions": results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
