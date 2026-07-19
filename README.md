# The Genome Reader

**Module 01 of Genome Firewall** — Hack-Nation × OpenAI × MIT Club of Northern California × MIT Club of Germany

> Turn a reconstructed bacterial genome (FASTA) into features an AI model can use to predict antibiotic response — before standard lab results arrive.

## Sequence visualization

The repository includes a self-contained, dependency-free frontend concept in `index.html`. A continuous 15-second animation shows a shaded 3D DNA double helix spinning, moving left, dissolving into glowing fragments that enter the first model layer, and revealing a dense side-view compression neural network over a subtle grayscale WebGL line field.

Run it locally with:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173). It is illustrative only and includes no model prediction or clinical decision.

**Repo:** [Trista1208/The-Genome-Reader](https://github.com/Trista1208/The-Genome-Reader)

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

## Recommended modeling baseline (full system)

- One **regularized logistic regression per antibiotic**  
- Features from AMRFinderPlus (genes + mutations)  
- CPU-friendly, easy to calibrate and explain  

Optional stretch: genomic LMs (e.g. HyenaDNA, DNABERT-2) on selected regions/chunks — not required.

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
- [ ] Download cohort FASTA assemblies  
- [ ] Document FASTA → AMRFinderPlus → feature matrix pipeline  
- [ ] Specify feature output schema for Module 02  
- [ ] Homology de-duplication + per-drug logistic regression (Module 02)  
- [ ] Streamlit/Gradio decision report with no-call (Module 03)  

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
```

---

## References

- Challenge brief: *Genome Firewall: An AI Defense System Against Superbugs* (Hack-Nation 6th Global AI Hackathon)  
- [AMRFinderPlus](https://github.com/ncbi/amr)  
- [BV-BRC FTP](https://www.bv-brc.org/docs/quick_references/ftp.html)  
- [BV-BRC](https://www.bv-brc.org)
