# Genome Firewall

**An honest AI defense system against superbugs.** Predicts from a reconstructed
bacterial genome which antibiotics are **likely to fail / likely to work / no-call** —
with calibrated confidence, cited evidence, and principled abstention — days before
standard lab susceptibility results arrive.

Hack-Nation 6th Global AI Hackathon · Challenge 06 · strictly defensive research
prototype. **Every prediction must be confirmed with standard laboratory testing.**

## Live artifacts

| What | Where |
|---|---|
| Models (skops, open) | https://huggingface.co/Darkroom4364/genome-firewall-ecoli |
| Interactive demo (static Space) | https://huggingface.co/spaces/Darkroom4364/genome-firewall |
| Colab demo notebook | `notebooks/GenomeFirewall_Demo.ipynb` |
| Team repo | https://github.com/Trista1208/The-Genome-Reader (branch `sprint/baseline`) |

## Current numbers (held-out genetic groups — lineages never seen in training)

| drug | balanced acc | R-recall | S-recall | no-call rate | acc when called |
|---|---|---|---|---|---|
| ciprofloxacin | 0.956 | 0.93 | 0.98 | 0.57 | 0.967 |
| trimethoprim/SXT | 0.906 | 0.93 | 0.88 | 0.59 | 0.970 |
| gentamicin | 0.877 | 0.81 | 0.94 | 0.66 | 0.814 |
| ampicillin | 0.838 | 0.79 | 0.89 | 0.62 | 0.884 |
| cefotaxime | 0.694 | 0.39 | 1.00 | 0.58 | 0.948 |

Cefotaxime is the honest weak spot: the held-out outbreak clone carries ESBL alleles
absent from all training lineages — the system detects its own weakness and abstains
rather than guessing. v3 retrain on the full 3,000-genome corpus is in progress.

## How it works

```
FASTA ──AMRFinderPlus 4.2.7──▶ resistance genes/mutations (per genome)
      ──feature matrix───────▶ 0/1 grid (~900 gene/mutation features)
      ──per-drug model───────▶ elastic-net logistic regression + Platt calibration
      ──honesty layers───────▶ asymmetric conformal no-call · ANI-distance override
                                · target-locus callability gate
      ──evaluation───────────▶ skani (ANI ≥99.5%) cluster splits; metrics on
                                held-out genetic groups only
```

Labels: BV-BRC lab-measured AST only, MIC rows re-derived against EUCAST v16.1
breakpoints (flip-rate 0.39%). No model-generated phenotypes.

## Quickstart

```bash
# inference API (local)
cd api && ../pipeline/.venv/bin/python serve.py
curl -X POST localhost:8000/predict -H 'Content-Type: application/json' \
  -d '{"genome_id": "562.140931", "drugs": ["ciprofloxacin"]}'

# dashboards
pipeline/.venv/bin/python learnwatch.py   # training view
python3 scoreboard.py                     # metrics watcher

# tests
pipeline/.venv/bin/python -m pytest pipeline/tests -q
```

## Repo map

- `data/` — BV-BRC pull scripts, label cleaning (EUCAST re-derivation), breakpoints
- `features/` — AMRFinderPlus batch runner, feature matrix, drug→determinant map
- `pipeline/` — skani splits, training, calibration, no-call, target gate, metrics
- `models/`, `reports/` — trained bundles + scorecards (gitignored, regenerable)
- `demo/` — Gradio app (local) + static build (HF Space)
- `api/` — FastAPI inference server
- `notebooks/` — Colab demo
- `scripts/` — HF upload, Space deploy, bundle/weights export
- `CONTRACT.md` conventions · `PREBUILT.md` disclosure · `CONTEXT.md` team handoff

## Responsibility

Defensive by construction: predicts and explains resistance that already exists;
never generates, designs, or suggests changes to any organism. Decision support only.
