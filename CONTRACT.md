# Genome Firewall — Dry-Run Workspace Contract

Dry-run pipeline for Hack-Nation Challenge 06 "Genome Firewall".
Goal: FASTA (one reconstructed bacterial genome) -> per-antibiotic
likely-to-fail / likely-to-work / no-call + calibrated confidence + evidence category.
Practice species: Escherichia coli (taxon_id 562).

## Directory layout & ownership (one builder per area)

- `data/` — BV-BRC pull: `labels_{species}.csv`, `genomes/{genome_id}.fna`, `manifest.json`, pull script, `clean/` (cleaned labels + audit), DATA.md
- `features/` — AMRFinderPlus (Docker) wrapper + `feature_matrix.csv` + `metadata.json`, drug→Class/Subclass mapping table, FEATURES.md
- `pipeline/` — splits (skani clustering, two-tier), train, calibrate, no-call, callability gate, eval harness, PIPELINE.md
- `rapidata/` — crowd-annotation order definitions (dry-run only), RAPIDATA.md — OUT OF SCOPE for the 21h event

## Shared file formats

### data/labels.csv + data/clean/
Raw: `genome_id,genome_name,taxon_id,antibiotic,resistant_phenotype,measurement,measurement_unit,laboratory_typing_method,evidence`
- ONLY laboratory-measured records (evidence == "Laboratory Method"); never computational predictions.
- Cleaned labels are RE-DERIVED: MIC rows only, re-interpreted against one current
  breakpoint standard per drug (`data/breakpoints.yaml`); submitted S/I/R calls used
  only when no MIC exists; flip-rate vs submitted calls logged in the audit.
- I-handling is standard-aware: EUCAST pre-2019 I → excluded/flagged; post-2019 I →
  excluded from binary training, reported separately.
- Conflicting lab records per genome-antibiotic pair → excluded and counted in manifest.

### data/genomes/{genome_id}.fna
Nucleotide FASTA per genome, public BV-BRC genomes only.

### features/feature_matrix.csv
First column `genome_id`; remaining columns binary (0/1) presence of AMRFinderPlus
"Element symbol" entries (AMRFinderPlus v4 header name — v3 "Gene symbol" is deprecated).
Feature tiers: acquired genes / curated point mutations / degraded evidence (partial,
internal stop); `--mutation_all` confirmed-WT vs locus-not-called feeds the callability gate.
`features/metadata.json`: tool version, database version, organism option used, date.
`features/drug_class_map.yaml`: allele-aware drug→Class/Subclass mapping (e.g. blaTEM →
ampicillin only; CTX-M → 3rd-gen cephalosporins; KPC/NDM/OXA-48 → carbapenems) — required
for evidence category (i) "spectrum-confirmed" labels.

### splits/splits.json
`{genome_id: {"cluster_id": int, "coarse_clade_id": int, "split": "train"|"calibration"|"test"|"heldout_group"}}`
Two tiers: fine clusters = skani >=99.5% ANI + >=80% aligned-fraction single-linkage
(de-dup: never cross splits); coarse clades = leave-top-N-clades-out tier used for
tuning and all reported numbers. Splits are BY CLUSTER, never by row.
`heldout_group` = whole clusters never seen in train/calibration (simulates organizer hidden set).

### models/{antibiotic}/ + reports/
Per-drug model artifacts; `reports/metrics.json` + `reports/reliability_{antibiotic}.png`.
Metrics per drug per split: balanced accuracy, recall per class (Resistant / Susceptible),
F1, AUROC, PR-AUC, Brier score, no-call rate, accuracy-after-no-call, reliability plot;
reported separately for seen clusters vs heldout_group.

## Conventions
- Labels: Resistant = "likely to fail" (1), Susceptible = "likely to work" (0),
  Intermediate/uncertain excluded from binary training but counted in reports.
- Python: each area has its own `.venv` (no conda on this machine).
- Bioinformatics CLIs run in Docker (`--platform linux/amd64` if needed); nothing installs system-wide.
- No git commits, no network writes beyond public BV-BRC / NCBI downloads. No API keys in files.
