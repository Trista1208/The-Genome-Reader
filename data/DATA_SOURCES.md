# Data sources (Genome Firewall)

Defensive research use only. Predictions must be confirmed by standard lab testing.

## Organizer fixed dataset (preferred when available)

Hack-Nation may provide a pinned cohort: 1 species, 3–5 antibiotics, lab labels, group splits, checksums.
**If/when that package is released, it replaces the self-built BV-BRC cohort below.**

## What we download now (challenge-suggested)

| Source | What | Local path | Role |
|--------|------|------------|------|
| [BV-BRC FTPS](https://www.bv-brc.org/docs/quick_references/ftp.html) | `PATRIC_genomes_AMR.txt` | `raw/bvbrc/RELEASE_NOTES/` | Lab AMR phenotypes (labels) |
| BV-BRC FTPS | `genome_summary`, `genome_metadata`, `genome_lineage` | `raw/bvbrc/RELEASE_NOTES/` | Species, quality, taxonomy |
| BV-BRC FTPS | `{genome_id}.fna` | `raw/bvbrc/genomes/` | Assembled FASTA inputs for Module 01 |
| [AMRFinderPlus DB](https://github.com/ncbi/amr) | latest NCBI AMR gene/mutation DB | `raw/amrfinderplus/latest/` | Default annotation for Module 01 |

### Mentioned but not bulk-downloaded as primary data

| Source | Why deferred |
|--------|----------------|
| ResFinder | Alternative annotator; optional later |
| cAMRah | Multi-tool workflow paper, not a single dataset |
| XTree | Alignment tool, not phenotype data |
| Kaggle mirrors | Tutorials only; not a verified benchmark |

## Download commands

```bash
# 1) BV-BRC metadata + lab AMR table (~1.2 GB; lftp recommended)
bash scripts/download_bvbrc_release_notes_lftp.sh

# 2) AMRFinderPlus reference DB (~136 MB)
python3 scripts/download_amrfinder_db.py

# 3) Auto-select 1 species + 3–5 antibiotics, write genome list
python3 scripts/select_cohort.py --species "Escherichia coli" --n-antibiotics 5 --max-genomes 3000

# 4) Download FASTA assemblies for the cohort (~15 GB; resume-safe)
bash scripts/download_bvbrc_genomes.sh data/processed/cohort/genome_list.txt data/raw/bvbrc/genomes 6
```

## Interim cohort (self-built until organizer dataset arrives)

| Field | Value |
|-------|--------|
| Species | *Escherichia coli* |
| Genomes | 3,000 (capped from larger lab-labeled pool) |
| Antibiotics | gentamicin, ciprofloxacin, ceftazidime, cefotaxime, piperacillin/tazobactam |
| Labels | `data/processed/cohort/genome_antibiotic_labels.tsv` |
| Genome IDs | `data/processed/cohort/genome_list.txt` |

Phenotype filter: rows with laboratory measurement and/or typing method; computational predictions excluded when flagged.

## Label convention

- `resistant` → `likely_to_fail`
- `susceptible` → `likely_to_work`
- Exclude computational / model-generated phenotype fields when flagged
