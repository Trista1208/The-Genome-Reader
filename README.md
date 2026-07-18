# Genome Firewall — Backend

**Modules 01 + 02** — Hack-Nation × OpenAI × MIT Club of Northern California × MIT Club of Germany

> Backend pipeline: FASTA → AMRFinderPlus features → **calibrated Random Forest** → per-drug JSON scores (`likely_to_fail` / `likely_to_work` / `no_call`).

**Scope:** this repo is **backend only**. Module 03 UI lives in [`frontend/`](frontend/README.md) and consumes [`specs/prediction_api.schema.json`](specs/prediction_api.schema.json).

**Repo:** [Trista1208/The-Genome-Reader](https://github.com/Trista1208/The-Genome-Reader)

---

## Backend layers

```text
FASTA + lab labels
        │
        ▼
┌──────────────────────────────────────────┐
│ Layer 1 — Ingestion                      │
│ cohort labels, splits, drug targets      │  backend/genome_firewall/layer1_ingestion/
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Layer 2 — Features (Module 01)           │
│ AMRFinderPlus → sparse binary matrix       │  backend/genome_firewall/layer2_features/
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Layer 3 — Model (Module 02)              │
│ Random Forest + isotonic calibration       │  backend/genome_firewall/layer3_model/
│ homology-aware train/cal/test splits       │
│ deterministic drug-target gate             │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Layer 4 — Scoring                          │
│ calibrated P(fail), confidence, no-call    │  backend/genome_firewall/layer4_scoring/
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ Layer 5 — Evaluation                       │
│ Brier, AUROC, balanced accuracy, no-call   │  backend/genome_firewall/layer5_evaluation/
└──────────────────┬───────────────────────┘
                   ▼
           JSON report (API contract)
           frontend/ consumes this
```

| Layer | Responsibility |
|-------|----------------|
| **1 Ingestion** | BV-BRC labels, genome lists, homology splits |
| **2 Features** | AMRFinderPlus annotation → feature matrix ([`specs/feature_schema.json`](specs/feature_schema.json)) |
| **3 Model** | **Random Forest** per antibiotic; isotonic calibration on cal split |
| **4 Scoring** | Target gate, no-call band (0.40–0.60), `confidence_score` = calibrated P(predicted class) |
| **5 Evaluation** | Held-out cluster metrics written to `data/processed/models/metrics.json` |

### Score contract (credible confidence)

Each drug in the JSON report includes:

- `probability_fail` / `probability_work` — **isotonic-calibrated** after RF training  
- `confidence_score` — probability of the reported class (not raw vote fraction)  
- `no_call` when probability is in the uncertain band or target gate fails  
- `evidence_category` — separates known AMR markers from model-only associations  

See [`specs/prediction_api.schema.json`](specs/prediction_api.schema.json).

---

## The problem in one paragraph

Antibiotic-resistant infections are linked to **4.7M+ deaths/year** (1M+ directly because drugs no longer work). Lab susceptibility testing takes **1–3 days**. Doctors often guess in that window. Much of the answer is already in the bacterium’s DNA: once a genome is sequenced and reconstructed, AI can flag which antibiotics are likely to fail or work — **days earlier**. This challenge builds that defensive prediction layer. It must **never** design, modify, or suggest changes to an organism.

---

## Full system: Genome Firewall (3 modules)

| Module | Name | Job |
|--------|------|-----|
| **01** | **The Genome Reader** *(this repo)* | FASTA → model-ready features (AMR genes / mutations) |
| **02** | The Predictor | Features → per-drug: likely to fail / likely to work / no-call |
| **03** | The Decision Report | Demo UI with confidence, evidence type, and lab-confirm warning |

```text
Quality-checked FASTA (one species)
        │
        ▼
┌─────────────────────┐
│ 01 Genome Reader    │  ← THIS REPO
│ AMRFinderPlus (etc.)│
│ → feature matrix    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 02 Predictor        │
│ per antibiotic      │
│ + target gate       │
│ + homology de-dupe  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 03 Decision Report  │
│ Streamlit / Gradio  │
│ fail / work / no-call│
│ + confidence + evidence│
└─────────────────────┘
```

### In scope vs out of scope

| In scope | Out of scope |
|----------|----------------|
| One reconstructed, quality-checked bacterial genome (FASTA) | Collecting samples / reading DNA from blood |
| Per antibiotic: likely to fail / likely to work / no-call | Identifying the bacterial species |
| Confidence score + supporting genes or DNA changes | Genome reconstruction / assembly |
| Account for presence of the drug’s molecular target | Separating mixed bacteria in one sample |

**Your pipeline starts only after** isolation, sequencing, and genome reconstruction are already done.

---

## Module 01 — What this repo must deliver

### Goal

Build a **documented, repeatable path**:

```text
assembled FASTA  →  annotation (default: AMRFinderPlus)  →  model features
```

on the **organizer-provided fixed dataset**, plus a **clear specification of the output feature format**.

### Default tool

- **[AMRFinderPlus](https://github.com/ncbi/amr)** (NCBI) — public-domain; finds antimicrobial-resistance (AMR) genes and resistance-associated mutations from protein annotations and/or assembled nucleotide sequence.
- Optional stretch: improve on or replace AMRFinderPlus with another AI/annotation approach.
- Next step for the full system: a model that consumes **presence/absence** (and related) features of known AMR genes/mutations.

### Required deliverables for Module 01

1. **Repeatable pipeline** from FASTA → features on the fixed dataset  
2. **AMRFinderPlus as the default** annotation path (unless you document a justified alternative)  
3. **Output format specification** (what columns/features each genome produces for Module 02)

---

## Modules 02 & 03 (context for the full challenge)

### 02 — The Predictor

- Drug database + properties for the supported antibiotics  
- For each genome’s features: **likely to fail / likely to work / no-call** per drug  
- **Deterministic target gate:** do not say “likely to work” only because resistance markers are absent — check that the drug’s molecular target is present  
- **De-duplication by sequence homology** so near-identical genomes are not in both train and test (threshold chosen and justified by the team)

### 03 — The Decision Report

- Streamlit or Gradio demo  
- Per drug: prediction + **calibrated confidence** + **evidence category**:
  1. Known resistance gene / DNA change detected  
  2. Statistical association only  
  3. No known resistance signal  
- Mandatory message: **confirm with standard laboratory testing**  
- Prefer **no-call** over false confidence when evidence is weak or conflicting

---

## Responsibility requirements (must show in demo / docs)

| Principle | Meaning |
|-----------|---------|
| **Defensive by construction** | Predict/explain resistance that already exists. Never generate or design organisms. |
| **Honest generalization** | Report performance on genetically related group splits; state species & antibiotics covered vs not. |
| **Calibrated confidence + no-call** | Confidence should match real accuracy; return no-call when uncertain. |
| **Honest explanations** | Separate known resistance markers from mere statistical associations (SHAP ≠ proof of biology). |
| **Human oversight** | Decision support only — never autonomous treatment decisions. |

---

## Data sources (hints)

| Source | Role |
|--------|------|
| **[BV-BRC](https://www.bv-brc.org)** (ex-PATRIC) | Primary: genomes + lab-measured antibiotic outcomes (use organizer-pinned lab results, not model-generated phenotype fields) |
| **[AMRFinderPlus](https://github.com/ncbi/amr)** | Default AMR gene/mutation annotation |
| [ResFinder](https://cge.food.dtu.dk/services/ResFinder/) | Acquired genes / chromosomal mutations |
| [cAMRah](https://pmc.ncbi.nlm.nih.gov/articles/PMC12910510/) | Multi-tool AMR workflow (includes AMRFinderPlus, ResFinder, RGI/CARD, Abricate, BV-BRC) |
| Organizer fixed dataset | Expected: ~1k–3k genomes, **one species**, 3–5 antibiotics, lab labels, group-based train / calibration / **hidden** test splits |

---

## Recommended model (this backend)

- **Random Forest** (`sklearn.ensemble.RandomForestClassifier`) — one model per antibiotic  
- **Isotonic calibration** on the homology-held-out calibration split  
- Class-weighted training for imbalanced R/S labels  
- No-call band on calibrated probabilities (default 0.40–0.60)

Logistic regression / Streamlit UI are **not** used in this repo.

---

## How submissions are judged

Not a single headline accuracy on an unbalanced set. Report:

- **Balanced accuracy**; recall for resistant (fail) and susceptible (work) separately  
- **F1, AUROC, PR-AUC** per drug (PR-AUC matters under imbalance)  
- **Confidence quality:** Brier score, reliability plot; no-call rate and accuracy of remaining calls  
- **Generalization:** metrics by genetically related groups on held-out / unseen groups  

### Strong vs weak

| Strong | Weak |
|--------|------|
| Grouped genetic split; show real resistance signals | Random split with near-duplicates in train & test |
| One species + few drugs, done well, with no-call | Claim every pathogen and every antibiotic |
| Honest evidence categories | Treat SHAP as biological proof |
| Strictly defensive framing | Drift into organism design / enhancement |

---

## Safety note

This is a **research prototype**. Predictions from historical genomes are **not** approved clinical tools. Every antibiotic-response report must be confirmed by **standard laboratory testing**.

---

## Status / next steps for this repo

- [x] Download BV-BRC RELEASE_NOTES (AMR phenotypes + genome metadata)  
- [x] Download AMRFinderPlus latest database  
- [x] Select interim cohort (E. coli, 5 antibiotics, 3,000 genomes) — replace when organizer dataset ships  
- [x] Layered backend package under `backend/genome_firewall/`  
- [x] Random Forest + isotonic calibration (`scripts/train_models.py`)  
- [x] JSON scoring API (`scripts/score_genome.py`, `specs/prediction_api.schema.json`)  
- [ ] Full cohort AMRFinderPlus annotation (resume download + batch)  
- [ ] Frontend demo in `frontend/` (separate team)  

## Data download (repeatable)

See [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md).

```bash
# Metadata + lab AMR labels (BV-BRC FTPS)
bash scripts/download_bvbrc_release_notes_lftp.sh

# AMRFinderPlus reference DB (NCBI HTTPS)
python3 scripts/download_amrfinder_db.py

# Pick 1 species + 3–5 antibiotics (lab-measured only)
python3 scripts/select_cohort.py --species "Escherichia coli" --n-antibiotics 5 --max-genomes 3000

# FASTA assemblies for the cohort (lftp; resume-safe)
bash scripts/download_bvbrc_genomes.sh data/processed/cohort/genome_list.txt data/raw/bvbrc/genomes 6

# Module 01–02 backend pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e backend/

python3 scripts/run_amrfinder_batch.py --workers 4 --threads 2
python3 scripts/build_feature_matrix.py
python3 scripts/homology_split.py
python3 scripts/train_models.py

# Score one genome → JSON for frontend
python3 scripts/score_genome.py 562.144150 --out /tmp/report.json

# Benchmark (test split metrics + failure reasons)
python3 scripts/benchmark_models.py
python3 scripts/benchmark_models.py --min-genomes 40 --strict

# Automated tests
pytest tests/ -q
```

---

## References

- Challenge brief: *Genome Firewall: An AI Defense System Against Superbugs* (Hack-Nation 6th Global AI Hackathon)  
- [AMRFinderPlus](https://github.com/ncbi/amr)  
- [BV-BRC FTP](https://www.bv-brc.org/docs/quick_references/ftp.html)  
- [BV-BRC](https://www.bv-brc.org)
