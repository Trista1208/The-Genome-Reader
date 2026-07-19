# Genome Firewall inference service

FASTA → antibiotic-response prediction. This is the service the Convex action
(`convex/analysis.ts`) calls. It runs the real trained E. coli models from
[`Darkroom4364/genome-firewall-ecoli`](https://huggingface.co/Darkroom4364/genome-firewall-ecoli).

## Pipeline

1. `POST /predict` receives an assembled genome FASTA + a target antibiotic.
2. **AMRFinderPlus 4.2.7** (NCBI) detects resistance genes / point mutations.
3. Hits become a 600-dim binary feature vector (`features/build_feature_matrix.py`).
4. The per-drug calibrated elastic-net model gives `p_fail` (probability of resistance).
5. No-call bands (`models/<drug>/nocall_bands.json`) decide work / fail / abstain.
6. Evidence genes are mapped per drug (`features/map_evidence.py` + `drug_class_map.yaml`).

Response `score = 1 − p_fail` (probability the drug is **effective**). Contract: see
[`../convex/README.md`](../convex/README.md).

Supported drugs: `ciprofloxacin`, `gentamicin`, `ampicillin`, `cefotaxime`,
`trimethoprim_sulfamethoxazole` (UI labels are mapped in `gf_infer.py:LABEL_TO_KEY`).

## Contents

| Path | What |
|---|---|
| `serve.py` | FastAPI service (`/health`, `/predict`) |
| `gf_infer.py` | Inference core: TSV/features → model → app contract |
| `features/` | `build_feature_matrix.py`, `map_evidence.py`, `drug_class_map.yaml`, `feature_columns.json`, `metadata.json` (reused from branch `sprint/baseline`) |
| `models/<drug>/` | `model.skops` + `nocall_bands.json` (from Hugging Face) |
| `requirements.txt`, `Dockerfile`, `.dockerignore` | packaging |

## Deploy (recommended — container has AMRFinderPlus + DB baked in)

```bash
cd inference
docker build --platform linux/amd64 -t genome-firewall-api .
docker run --platform linux/amd64 -p 8000:8000 \
  -e INFERENCE_API_TOKEN=<optional-shared-secret> \
  genome-firewall-api
```

Then set `INFERENCE_API_URL` (the public URL of this host) in the Convex dashboard.
Host needs an amd64 runtime with enough RAM/CPU for AMRFinderPlus (a genome takes ~1–3 min).

## Local dev (host Python; AMRFinderPlus via Docker)

```bash
cd inference
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
./.venv/bin/uvicorn serve:app --host 0.0.0.0 --port 8000
```

When the `amrfinder` binary is not on `PATH`, `serve.py` runs AMRFinderPlus via
`docker run staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1` automatically. `GET /health`
reports `"amrfinder": "binary"` or `"docker"` accordingly.

```bash
curl -s localhost:8000/health | jq
curl -s localhost:8000/predict -H 'content-type: application/json' \
  -d "{\"fasta\": \"$(sed ':a;N;$!ba;s/\n/\\n/g' genome.fna)\", \"antibiotic\": \"Ampicillin\"}" | jq
```

> Research prototype. All predictions must be confirmed with standard laboratory
> susceptibility testing. Not a medical device.
