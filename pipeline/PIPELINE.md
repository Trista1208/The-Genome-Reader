# pipeline/ — splits, calibration, no-call, metrics

Evaluation/model harness per CONTRACT.md and the v2 synthesis (two-tier
splits, nested protocol, asymmetric no-call, ANI-distance override).

## Setup

```bash
python3 -m venv pipeline/.venv
pipeline/.venv/bin/pip install -r pipeline/requirements.txt
docker pull --platform linux/amd64 staphb/skani:0.3.2   # pinned; tag verified 2026-07-19
```

skani runs in Docker by default. Fallback without Docker: install a local
skani binary (e.g. `cargo install skani`) and pass `--skani-bin /path/to/skani`
or `export SKANI_BIN=/path/to/skani`.

## Modules

- `splits.py` — skani `triangle -E` wrapper (Docker), edge parser,
  single-linkage clusters (ANI >= 99.5% AND min-AF >= 80%), leave-top-N-clades-out
  coarse tier (default N=5, `--n-heldout`), train/calibration/test by cluster
  (StratifiedGroupKFold semantics; greedy fallback when too few groups/labels).
  Writes `splits/splits.json` in CONTRACT format and runs the leakage audit
  (fails nonzero if any cluster crosses splits or a >=threshold ANI edge
  connects train and heldout_group). `audit_cassette_sharing()` reports
  resistant-class AMR-feature overlap between splits from a feature matrix.
  `coarse_clade_id` currently equals `cluster_id` (no phylogeny available);
  the column exists so an MLST/phylo remap can drop in without schema changes.
- `nocall.py` — class-conditional split-conformal with ASYMMETRIC alpha
  (susceptible 0.02 / resistant 0.10) + ANI-distance-to-nearest-training-genome
  hard override (quantile-derived threshold). `apply_nocall(p, bands,
  distances)` is a pure function, so probabilities can be submitted for ALL
  genomes and calls re-derived later. crepes 0.9.1 was evaluated (installs
  cleanly) but supports only a single global eps, not per-class alphas, and
  exposes no pure (p, band) edges — hence the direct implementation.
- `calibrate.py` — Platt/sigmoid via `CalibratedClassifierCV(FrozenEstimator(...))`
  (sklearn >= 1.6). Isotonic deliberately NOT used at this calibration-set size.
- `metrics.py` — `evaluate_all(probabilities, labels, splits, nocall_mask)`
  writes `reports/metrics.json` + `reports/reliability_{drug}.png`: balanced
  accuracy, recall R/S, F1, AUROC, PR-AUC, Brier, no-call rate,
  accuracy-after-no-call, risk-coverage data, reliability data, per-group
  (seen vs heldout_group) breakdown, bootstrap-over-CLUSTERS 95% CIs.

## Full run (once the CPU batch frees up)

```bash
# from repo root; ~3k genomes, give it threads but nice it down if needed
pipeline/.venv/bin/python -m pipeline.splits \
  --genomes-dir data/genomes \
  --labels data/clean/labels_ampicillin.csv \  # optional, stratification (genome_id,label)
  --out splits/splits.json \
  --edges-out splits/skani_edges.tsv \
  --n-heldout 5 --threads 8
# exits nonzero + prints the audit if leakage is detected
```

## Evaluate a trained model

```python
from pipeline import metrics, nocall, calibrate

cal = calibrate.platt_calibrate(fitted_lr, X_cal, y_cal)          # calibration split only
bands = nocall.fit_conformal_bands(p_cal, y_cal)                  # asymmetric alphas
bands.dist_threshold = nocall.fit_distance_threshold(d_cal_to_train)
mask = {g: m for g, m in zip(genomes, nocall.apply_nocall(p_all, bands, d_all))}

res = metrics.evaluate_all(
    probabilities,        # {genome: p} or {drug: {genome: p}} or genome x drug DataFrame
    labels,               # same shape; NaN = unlabeled
    splits,               # splits/splits.json dict (or path)
    mask,                 # same shape, bool; None to score without abstention
    out_dir="reports",
)
```

## Tests

```bash
cd pipeline && ../pipeline/.venv/bin/python -m pytest -q   # 22 passed
```

All tests run on synthetic data; Docker/skani is exercised only by the manual
smoke validation (`run_skani_triangle` on 5 genomes), never by pytest.
