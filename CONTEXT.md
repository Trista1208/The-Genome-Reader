# GENOME FIREWALL — team context (updated 19 Jul, ~09:00)

**What it is:** Hack-Nation challenge 06 — predict from a bacterial genome (FASTA)
which antibiotics will fail / work / can't-tell, with calibrated confidence, evidence,
and honest abstention. Strictly defensive; lab-confirmation required on all outputs.

**Status: COMPLETE PIPELINE, v3 retrain running.** All brief requirements covered.

## Where everything lives

- Models (open, skops): https://huggingface.co/Darkroom4364/genome-firewall-ecoli
- Demo Space (static): https://huggingface.co/spaces/Darkroom4364/genome-firewall
- Code: branch `sprint/baseline` on github.com/Trista1208/The-Genome-Reader AND
  github.com/Darkroom4364/genome-firewall (kept in sync; `main` intentionally untouched)
- Colab: `notebooks/GenomeFirewall_Demo.ipynb` (models + data load from HF, runs anywhere)

## Numbers v2 — held-out genetic groups (1,434 genomes, 161 clusters)

cipro 0.956 · SXT 0.906 · gentamicin 0.877 · ampicillin 0.838 · cefotaxime 0.694
(cefotaxime abstains 58% — unseen ESBL alleles in test clone; documented, not hidden)
v3 on all 3,000 genomes in progress; ships only where it doesn't regress.

## Architecture (stable)

FASTA → AMRFinderPlus 4.2.7 (pinned DB) → ~900 features → per-drug elastic-net LR
→ Platt calibration → asymmetric conformal no-call + ANI-distance override +
target-locus callability gate. Evaluation: skani ANI ≥99.5% cluster splits,
leakage-audited; all reported numbers are on held-out genetic groups.

## Data provenance

3,000 public E. coli genomes (BV-BRC), 99,292 cleaned labels; lab-measured rows only;
MIC re-derived vs EUCAST v16.1 (flip-rate 0.39%). ~340 train genomes/drug by design.

## For the merge with Trista's backend (their `main`)

Our ML/eval core + their service/API layer + their `specs/prediction_api.schema.json`
as shared contract. Zero file overlap; unrelated histories (merge with
--allow-unrelated-histories or cherry-pick directories).

## Run it

- API: `cd api && ../pipeline/.venv/bin/python serve.py`
- Dashboards: `pipeline/.venv/bin/python learnwatch.py`, `python3 scoreboard.py`
- Tests: `pipeline/.venv/bin/python -m pytest pipeline/tests -q` (34 pass)

## Open items (deadline 15:00 today)

1. v3 retrain (running) → honest compare vs v2
2. Demo cache rebuild + Space redeploy (hotswap to v3)
3. Video + project page

Disclosure: PREBUILT.md (pre-event work) · README.md front door · this file = context.
