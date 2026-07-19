# Genome Firewall — demo report app (Gradio)

Per-genome antibiotic-resistance report for Hack-Nation Challenge 06.
Renders **precomputed artifacts only** — the app never runs model inference.
Species: *Escherichia coli* (BV-BRC taxon 562). Drugs: ciprofloxacin,
gentamicin, ampicillin, trimethoprim–sulfamethoxazole, cefotaxime.

> **Research prototype — all results must be confirmed with standard
> laboratory susceptibility testing.** (Shown as a banner on every view.)

## Run

```bash
# from the repo root — the pipeline venv already has everything the app needs
# EXCEPT gradio, so use the demo venv:
python3.12 -m venv demo/.venv
demo/.venv/bin/pip install -r demo/requirements.txt

demo/.venv/bin/python demo/app.py
# -> http://127.0.0.1:7860   (PORT env var to change)
```

The app re-reads `reports/metrics.json` + reliability PNGs **on every render**,
so a retrain overwriting them takes effect without a restart (there is also a
"↻ Re-read metrics" button). Per-genome scores come from a committed cache —
the app itself never unpickles a model.

## What the app shows

- **Genome picker** — 3 curated story genomes (buttons) + any of the ~1434
  AMRFinderPlus-genome ids (dropdown, free text).
- **Verdict table** — per drug: `likely to fail` / `likely to work` / `no-call`
  (verbatim rubric words), calibrated score, and confidence as **frequency
  framing** pulled live from `metrics.json` reliability bins: *"among held-out
  genomes scoring 0.9–1.0, 93% were resistant (n=29)"*. NO-CALL is rendered
  neutral gray with its reason (abstention band vs ANI-distance override).
- **Evidence drawer per drug** — three clearly separated categories:
  (i) *known determinant* — spectrum-confirmed AMRFinderPlus hits via the
  allele-aware `drug_class_map.yaml` rules, each with tier (POINT mutation /
  full gene EXACT-ALLELE / degraded), confidence (confirmed / review), and its
  citation family (ResFinder 4.0, PointFinder, AMRFinderPlus catalog);
  (ii) *statistical association* — the model's strongest nonzero features
  present in this genome, explicitly labeled mechanism-free;
  (iii) *no-signal check* — declared when neither is present, plus the drug's
  declared blind spots.
- **Callability-gate panel** (ciprofloxacin) — gyrA / parC / parE loci:
  mutation found vs wild-type-intact (k-mer-verified sequenced) vs not-called.
  The honest sentence: *we verified the target locus was actually sequenced
  before trusting "no mutation found"*.
- **Trust tab** — reliability plot PNG, accuracy-vs-coverage curve (from
  `metrics.json` `risk_coverage`), no-call rate + accuracy-when-called per
  drug per group, and the threat-model table (4 failure modes →
  countermeasures, from research 00/08).

## Curated genomes (current picks — see `data/curated.json`)

Selection is programmatic (`build_cache.py: pick_curated`), re-derived on
every cache rebuild; criteria in order:

1. **Textbook resistant** — lab-confirmed ciprofloxacin-resistant, model
   verdict `likely to fail`, ≥2 QRDR loci (gyrA/parC/parE) with curated point
   mutations so category-(i) evidence is rich; never from the train split.
2. **Honest likely-to-work** — lab-susceptible on all scored drugs, never
   called `likely to fail`, ciprofloxacin called `likely to work`, gyrA+parC
   k-mer-verified wild-type-intact; fewest no-calls wins.
3. **The refusal** — held-out genetic group, firewall declined to call:
   ANI-distance override firing on a confident score if one exists, else the
   widest conformal-band refusal.

Current picks (cache built from the 04:00 retrain artifacts; callability
k-mer check k=31, ≥30% of 48 spaced locus k-mers, both strands):

| slot | genome | what it shows |
|---|---|---|
| resistant | `562.140931` | heldout_group; lab ciprofloxacin-R; QRDR mutations gyrA S83L+D87N, parC S80I+E84V, parE I529L; verdict **likely to fail** (ciprofloxacin, gentamicin, cefotaxime), no-call on ampicillin |
| susceptible | `562.100280` | test split (never trained on); lab-S on all 5 drugs; gyrA/parC/parE k-mer-verified wild-type-intact; **likely to work** on 5/5 |
| refusal | `562.100124` | heldout_group; **no-call on 5/5 drugs** — ciprofloxacin score 0.088 would have read *likely to work* under a naive 0.5 threshold, lab truth is Resistant; the abstention band catches exactly this error |

## Static build (HF Spaces — free static tier)

`demo/static/` is a self-contained no-framework HTML/JS version of the same
report (Gradio needs a PRO Space; static is free). Generate the data payloads
after any cache rebuild and serve the directory:

```bash
demo/.venv/bin/python demo/build_static.py
cd demo/static && python3 -m http.server 8791    # http://127.0.0.1:8791
node demo/static_smoke.js                        # DOM-stubbed render checks
```

Everything is precomputed JSON (`data/*.json` ≤ 6.2 MB total); the browser
runs zero inference. `data/gate_status.json` drives the callability panel —
if it is absent the panel degrades to a note instead of breaking.

## Rebuilding the cache (after a retrain)

```bash
pipeline/.venv/bin/python demo/build_cache.py                    # full rescore (~30 min)
pipeline/.venv/bin/python demo/build_cache.py --callability-only # k-mer gate only (~35 min)
pipeline/.venv/bin/python demo/build_cache.py --curate-only      # re-pick stories only (seconds)
```

`build_cache.py` must run with the **pipeline venv** (it unpickles
`models/*/baseline.pkl` — same scikit-learn that trained them). It writes:

- `demo/data/genome_cache.json` — per-genome calibrated score, verdict
  (re-derived as a pure function of score/band/distance per
  `pipeline/nocall.py`), no-call reason, lab label, top model features, split,
  ANI distance to nearest training genome, and the gyrA/parC/parE callability
  status (k-mer locus check: ≥30% of 48 spaced 31-mers of the donor locus,
  either strand = "locus sequenced"; the donor is `562.100000`, whose TSV
  confirms the exact locus coordinates. Intraspecies divergence breaks most
  31-mers; an absent locus matches ~zero — 0.30 separates the two widely).
- `demo/data/curated.json`, `demo/data/amrfinder/*.tsv` (curated genomes),
- `demo/reports/` — snapshot of metrics + reliability PNGs (fallback for
  standalone hosting; the live `../reports` is preferred when present).
  NOTE: gitignored (root `reports/` pattern catches `demo/reports/`) —
  regenerate with build_cache.py.

## Layout / portability (HF Spaces)

```
demo/
  app.py                 # Gradio entry point (local demo / video)
  requirements.txt       # gradio==5.38.2, PyYAML, pandas
  map_evidence.py        # vendored from features/ (stdlib + PyYAML)
  drug_class_map.yaml    # vendored evidence rules + citations
  build_cache.py         # cache builder (repo-side only; not needed on Spaces)
  build_static.py        # emits static/data + static/assets from the cache
  smoke_test.py          # Gradio --local / --url smoke checks
  static_smoke.js        # static-app render checks (node, DOM-stubbed)
  data/genome_cache.json # committed; all the app needs for verdicts
  data/curated.json      # the 3 story genomes + pick rationale
  data/amrfinder/*.tsv   # evidence drawer for curated genomes offline
  static/                # self-contained static build (free HF static Space)
    index.html app.js styles.css
    data/*.json          # genomes / evidence / gate_status / metrics / curated
    assets/reliability_*.png
  reports/               # metrics snapshot fallback (gitignored, regenerable)
```

For a static Space, copy `demo/static/` alone. For a Gradio Space (PRO),
copy `demo/`; the app resolves data in the order `$GF_REPORTS_DIR` →
`../reports` → `demo/reports` (and `$GF_AMRFINDER_DIR` →
`../features/amrfinder` → `demo/data/amrfinder`), so the standalone copy
works as-is, while in-repo it follows the live retrain.
Do **not** commit real lab data beyond what is already here; no API keys,
no network calls at runtime.

## Smoke test

```bash
demo/.venv/bin/python demo/smoke_test.py --local                      # no server
demo/.venv/bin/python demo/smoke_test.py --url http://127.0.0.1:7860  # live API
node demo/static_smoke.js                                             # static app
```
