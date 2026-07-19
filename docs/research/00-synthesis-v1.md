# Genome Firewall — Candidate Setup v1 (pre-roast)

Synthesized from research reports 01–08 in this directory. This is the draft the roast
agents attack. Nothing here is sacred.

## 0. Event reality (VERIFY IMMEDIATELY)

- Reported: ~24h event, ~21h hacking, Sat ~12:15pm ET → Sun 9:00am ET.
  Submission = project page + MP4/H.264 video, editable until deadline. Top-16
  pitch 3 min one week later. Source: hack-nation.ai / projects.hack-nation.ai.
- Consequence: ALL pipeline construction must happen pre-event. Event hours are
  for data adaptation, calibration, evaluation, demo, video.

## 1. System architecture

```
organizer FASTA + labels (+ precomputed AMRFinderPlus results)
        │
        ▼
[01 Genome Reader]  AMRFinderPlus 4.2.7 + pinned DB
        │  features: acquired-gene presence / point mutations / degraded-evidence
        │  tiers (partial, internal stop) / confirmed-susceptible loci (--mutation_all)
        ▼
[02 Predictor]  per-drug L1-logistic regression (primary)
        │         + optional k-mer logistic stream (evidence category ii) — own code, NOT Kover (GPL)
        │  deterministic target-presence gate (absent target → never "likely to work")
        │  Platt calibration (CalibratedClassifierCV, sigmoid)
        │  class-conditional split-conformal no-call (crepes, alpha=0.10)
        ▼
[03 Decision Report]  Streamlit, cached/precomputed results only
        │  per-drug cards: verdict / calibrated confidence / evidence category (i|ii|iii)
        │  LLM narrative: citation-by-ID, Structured Outputs strict mode, code renders
        │  all facts; BioFire-style disclaimer on every screen
        ▼
[Metrics harness]  skani ANI de-dup (>=99.5% ANI + >=80% AF, single linkage)
        │  StratifiedGroupKFold; balanced acc, per-drug F1/AUROC/PR-AUC, Brier,
        │  reliability, no-call rate, accuracy-at-coverage, per-group breakdown,
        │  cross-split ANI audit (zero pairs >= 99.5%)
```

## 2. Threat-model framing (the "firewall" story)

| Failure mode ("attack") | Countermeasure |
|---|---|
| Homolog leakage across splits | skani components, ANI audit artifact |
| False confidence | Platt + conformal no-call + reliability plot |
| Spurious correlation sold as biology | evidence categories (i)/(ii)/(iii); LLM may only cite evidence IDs |
| Absent-target false-susceptible | deterministic molecular-target gate |
| Autonomous decision-making | human-oversight copy, lab-confirmation banner |

## 3. Pre-event build list (in priority order)

1. **Download rehearsal data**: species-parameterized BV-BRC script; E. coli
   primary, K. pneumoniae + N. gonorrhoeae backups (labels CSV + ~3-5k genomes
   each, ~25 GB). Plus Hu et al. Mendeley benchmark (doi:10.17632/6vc2msmsxi.1).
   Filter BV-BRC labels: evidence == "Laboratory Method" ONLY (drop Computational
   Method = model-generated); normalize drug names; resolve duplicate
   genome×drug conflicts; S/I/R binarization with documented rule.
2. **AMRFinderPlus env**: conda ncbi-amrfinderplus=4.2.7 + `amrfinder -u` (DB
   2026-05-15.1), or StaPH-B docker tag baking both. Run over rehearsal genomes
   (GNU parallel, -j2 --threads 4, overnight). Feature-matrix builder with
   v4.0-renamed headers (Element symbol etc.) and version logging.
3. **Metrics harness** (~300 lines): skani triangle -E → connected components →
   group labels; StratifiedGroupKFold; full metric suite; ANI audit; reliability
   diagram; risk-coverage curve. Validate harness on Hu et al. folds.
4. **Baseline model**: per-drug L1-LR on AMRFinderPlus features + Platt + crepes
   conformal; reference numbers on 2-3 Hu et al. species-drug datasets.
5. **Streamlit shell**: 5 states (QC gate → verdict table → evidence drawer →
   calibration tab → coverage chart), 3 cached genomes (clean resistant / honest
   susceptible / engineered refusal).
6. **LLM report writer**: Structured Outputs strict schema, citation regex
   validation, iterate on gpt-5.4-nano/mini (~$8), final on gpt-5.4.

## 4. Event-day flow (21h)

- H0–1: species confirmed; `amrfinder -l` point-mutation check (decides mutation
  evidence tier); adapt loaders to organizer schema; cross-check rehearsal
  corpus vs organizer genome IDs for hidden-test leakage (de-dup!).
- H1–4: features → train + calibrate baseline → grouped-CV numbers on the
  organizer split. If precomputed AMRFinderPlus results provided: parse, verify
  version, else run own.
- H4–8: conformal tuning + target gate + per-drug thresholds; k-mer stream only
  if baseline is green.
- H8–12: Streamlit demo + LLM narrative + threat-model slide.
- H12–16: evaluation tables/plots for project page; record video; write page.
- H16–21: buffer, polish, submit early, sleep.

## 5. Demo script (4 min, video)

1. Hook (20s): 1-3 days for lab AST; the answer is in the genome.
2. Cached genome A: resistant — verdict + gene evidence + citation (30s).
3. Cached genome B: "likely to work" — target-gate panel shown explicitly (30s).
4. WOW: held-out-group genome → engineered refusal; naive baseline confidently
   guesses; accuracy-at-coverage curve proves the no-call wins (60s).
5. EUCAST ATU analogy ("uncertain" is laboratory orthodoxy) + disclaimer (20s).
6. Metrics tables: per-drug, per-group, calibration, coverage (40s).

## 6. Open contingencies

- Species not E. coli → swap download script parameter; backup species rehearsed.
- No curated point mutations for species (`amrfinder -l`) → mutation evidence
  tier degrades; consider RGI/CARD as second tool (adds install risk).
- Organizer labels dirty (mixed standards, duplicates) → documented binarization
  rule; report label-audit slide.
- Conformal no-call rate too high at alpha=0.10 → tune alpha per drug, report
  coverage trade-off honestly.
