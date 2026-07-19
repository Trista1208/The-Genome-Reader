# GENOME FIREWALL — context for the team (as of 19 Jul, ~05:30)

**What it is:** Hack-Nation × OpenAI challenge 06. Predict from a bacterial genome
(FASTA) which antibiotics will fail / work / can't-tell (no-call), with calibrated
confidence and evidence — days before lab results. Strictly defensive; every report
says "confirm with standard lab testing."

**Status: WORKING END-TO-END.** Models trained, honestly evaluated, published.

## Numbers (held-out genetic groups — strains never seen in training)

| drug | balanced acc | log-loss | note |
|---|---|---|---|
| ciprofloxacin | 0.956 | 0.135 | anchor |
| trimethoprim/SXT | 0.906 | 0.266 | strong |
| gentamicin | 0.877 | 0.378 | recovered after calibration fix |
| ampicillin | 0.838 | 0.384 | steady |
| cefotaxime | 0.694 | 0.303 | weak by nature (unseen ESBL alleles) → abstains 58% |

Blind checks: 8/8 hand-picked held-out genomes correct; 50-random-per-drug: 88–94%.

## Live artifacts

- Models (open source, skops): https://huggingface.co/Darkroom4364/genome-firewall-ecoli
- Code: github.com/Trista1208/The-Genome-Reader (branches: sprint/baseline, prep/*)
  mirror: github.com/Darkroom4364/genome-firewall
- Local API: `cd genome-firewall/api && ../pipeline/.venv/bin/python serve.py`
  → POST localhost:8000/predict {"genome_id": "562.100000"}
- Dashboards: `./scoreboard.py`, `./biostat.py`, `./status.sh` (repo root)

## How it works (one line each)

1. FASTA → AMRFinderPlus (NCBI tool, Docker) → resistance genes/mutations per genome
2. Genome → 600 yes/no features (gene present? mutation present?)
3. Per drug: elastic-net logistic regression (5 small models, ~5KB of weights each)
4. Platt calibration → honest probabilities
5. No-call layer: abstains when evidence is weak or genome is genetically far from training
6. Evidence: every verdict cites the actual resistance genes (spectrum-confirmed mapping)
7. Evaluation is honest-by-construction: train/test split by genetic clusters (skani
   ANI ≥99.5%), so "unseen" really means unseen lineages. Leakage audit passes.

## Data

- 3,000 public E. coli genomes (BV-BRC), 1,434 feature-extracted
- 99,292 cleaned labels; MIC rows re-derived against EUCAST v16.1 breakpoints
- Training uses only ~339 genomes/drug — the rest is held out for honest testing

## Key decisions (don't re-litigate)

- Logistic regression, not deep learning: linear models match SOTA at this scale
  (Hu et al. 2024 benchmark); small data → small model is correct, not a failure
- No-call is a feature, not a bug: EUCAST itself has "area of technical uncertainty"
- Cefotaxime weakness = unseen resistance alleles in test clone; documented, abstained

## Still open (today, deadline 15:00)

- Static HTML demo → free HF Space (Gradio needs PRO; static is free; browser-side
  inference via demo/data/model_weights.json — verified vs sklearn)
- Video + project page (the actual submission)
- PREBUILT.md exists — disclosure of pre-event work, keep it accurate

## For the merge with Trista's backend (The-Genome-Reader main)

Their service architecture is good; our data/eval/models are real. Proposal:
our ML core + their API/service layer + their specs/prediction_api.schema.json
as the shared output contract. Zero file overlap between the repos.
