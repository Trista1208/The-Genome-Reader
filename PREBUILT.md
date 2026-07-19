# PREBUILT.md — Pre-event work disclosure

In the interest of transparency, this document discloses what existed **before** the
official hacking window, per hackathon rules. Everything below was built from public
data and public tools; no organizer-provided dataset, credits, or privileged access
was used before kickoff.

## What existed before kickoff

| Item | What it is | Source |
|---|---|---|
| Research notes | Challenge analysis, method selection, evaluation design (`genome-firewall-research/`) | Public brief + public literature |
| Rehearsal dataset | 3,000 public E. coli genomes + 401k lab-only AST rows | BV-BRC (public archive) |
| Label-cleaning module | MIC-only re-derivation vs EUCAST v16.1, synonym map, conflict log | Our code, public standards |
| AMRFinderPlus environment | Docker image `staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1`, smoke test | NCBI public domain tool |
| Feature extraction (rehearsal) | AMRFinderPlus TSVs for the rehearsal genomes | Above |
| Evaluation harness | skani two-tier splits, metrics suite, calibration + conformal no-call | Our code |
| Drug→determinant map | Cited mapping (ResFinder/PointFinder/AMRFinderPlus sources) | Our curation, public sources |
| Baseline models (rehearsal) | Per-drug elastic-net LR, trained on rehearsal data only | Our code |

## What was built during the event

- Adaptation to the organizer's fixed dataset (schema, species, drugs)
- Final training/calibration on organizer splits
- Demo apps (Gradio + static), report writer, API server
- Videos + project page
- Any organizer-data-driven tuning

## Notes

- The rehearsal corpus comes from the same public archive (BV-BRC) the organizers
  may have sampled. Before any organizer-data training, we cross-check genome IDs
  and de-duplicate (ANI ≥ 99.5%) so no hidden-test genome can leak from rehearsal
  data into training.
- Rehearsal metrics are never reported as event results; all reported numbers are
  computed on the organizer's splits.
