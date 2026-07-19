# Genome Firewall — FINAL SETUP v2 (post-roast)

Synthesis of research reports 01–08, hardened by three roast passes (ML-rigor,
hackathon-strategy, domain/clinical). Supersedes 00-synthesis-v1.md.
Changes forced by the roasts are marked [ROAST].

## 0. Event reality

- ~24h event (~21h hacking), submission = project page + MP4/H.264 video.
  Verify schedule + rules at kickoff.
- **State of prep (verified 2026-07-18 ~23:00 local): `genome-firewall/` is empty
  scaffolding — CONTRACT.md only. No data, no env, no code. The pre-event build
  list below is therefore mandatory, not optional.** [ROAST]

## 1. Architecture (final)

```
organizer FASTA + labels (+ precomputed AMRFinderPlus results if usable)
        │
        ▼
[01 Reader]  AMRFinderPlus 4.2.7 + pinned DB (StaPH-B docker)
        │  tiers: full genes / curated point mutations / degraded (partial, internal stop)
        │  + --mutation_all confirmed-WT vs locus-not-called  (the REAL gate signal)
        ▼
[02 Predictor]  per-drug elastic-net LR, class_weight='balanced'   [ROAST: no bare L1]
        │  evidence DECOUPLED from model: category (i) = AMRFinderPlus rows via
        │  allele-aware drug→Class/Subclass mapping table ("spectrum-confirmed"),
        │  never model coefficients                                        [ROAST]
        │  target-locus CALLABILITY gate (WT-intact at curated loci; BLAST vs
        │  ~10 target sequences) — folded into predictor PRE-calibration   [ROAST]
        │  Platt/sigmoid calibration (FrozenEstimator); isotonic skipped at this n
        │  abstention = class-conditional split-conformal (crepes) with
        │  ASYMMETRIC alpha: susceptible-side 0.01–0.02, resistant-side 0.10 [ROAST]
        │  + ANI-distance-to-nearest-training-genome hard OOD no-call override [ROAST]
        ▼
[03 Report]  Streamlit, cached JSON only; TEMPLATE-rendered report first,
        │  LLM narrative as capped drop-in upgrade (3 person-hours max)      [ROAST]
        │  frequency-framed confidence ("among held-out genomes in this bin,
        │  X% were resistant") — never per-isolate "93% chance"              [ROAST]
        ▼
[Metrics]  skani (>=99.5% ANI + >=80% AF single-linkage) de-dup tier
        │  + coarser leave-top-N-clades-out tier for tuning/reporting        [ROAST]
        │  cassette-sharing audit (resistant-class AMR-node overlap across splits) [ROAST]
        │  nested protocol: outer leave-clades-out = reported numbers,
        │  inner folds = the few allowed choices; tuned-vs-untouched gap shown [ROAST]
        │  insurance: store/submit probabilities for ALL genomes; calls are a
        │  pure function of (p, threshold, band)                             [ROAST]
```

## 2. The six roast-forced design changes (the headline)

1. **Conformal is not the firewall; distance is.** Class-conditional conformal is
   silent exactly on confident-wrong unseen-lineage errors. Fix: ANI-to-nearest-
   training-genome hard no-call override ("further than anything I was right
   about"), conformal demoted to "principled margin," and the demo shows
   MEASURED per-group coverage on leave-one-clade-out — not a staged refusal. [ML]
2. **Split granularity matches the organizer's difficulty.** Two-tier validation:
   99.5% ANI for de-dup, coarse leave-top-N-clades-out for all tuning/reporting.
   Plus cassette-level audit (plasmid cassettes cross ANI boundaries). [ML]
3. **Frozen protocol, nested evaluation.** Global alpha, threshold 0.5, no
   per-drug knob-fest on ~30 effective clusters; reported numbers come from
   untouched outer folds only; the tuned-vs-untouched gap is itself a slide. [ML]
4. **The gate is renamed and rebuilt honestly.** Within one species the target
   is never absent — the gate is a *locus callability / WT-intactness* check
   (APHL wording), built on --mutation_all + a 10-sequence BLAST. The demo says
   this sentence out loud. Susceptible-side safety comes from asymmetric
   abstention + a declared per-drug "unexplained resistance rate" (% of R
   isolates with no tier-1/2 marker — catches porin/efflux blind spots). [domain+ML]
5. **Labels are re-derived, not trusted.** MIC rows only, re-interpreted against
   ONE current breakpoint standard per drug; standard-aware I handling
   (pre/post-2019 EUCAST); flip-rate logged (slide); per-drug label-noise
   ceiling stated. The allele-aware drug→class mapping table (TEM→amp only,
   CTX-M→3GC, KPC/NDM/OXA-48→carbapenems, aminoglycoside variant-aware) is a
   named pre-event deliverable — v1 silently dropped it. [domain]
6. **LLM inverted, video inverted.** Template-rendered report first (2h, zero
   API, zero hallucination surface); LLM prose upgrade only after metrics are
   frozen, hard-capped, template fallback. Video cold-opens on the refusal,
   metrics = two numbers + one curve in 10s; codec/upload test at H2. [strategy]

Killed outright: k-mer stream (own research said +0–3 AUROC in the wrong
regime), Kover (GPL), genomic LMs, LLM adversarial-eval harness, Q&A feature. [all]

## 3. Pre-event build list (tonight, ordered)

1. **Data pull (start first, runs unattended):** species-parameterized BV-BRC
   script; E. coli primary + K. pneumoniae, N. gonorrhoeae backups; ADD cheap
   tail coverage: P. aeruginosa + S. aureus labels + ~500 genomes each [ROAST].
   Labels: evidence=="Laboratory Method" only; MIC-only re-interpretation with
   one breakpoint table per drug; conflicts excluded+counted; flip-rate logged.
2. **AMRFinderPlus env:** StaPH-B docker (4.2.7 + DB baked) or conda pin;
   smoke-test on 10 genomes; feature-matrix builder using **v4 headers
   ("Element symbol")** — CONTRACT.md says "Gene symbol" (v3), fix it [ROAST].
3. **drug→Class/Subclass mapping table** for the 5–8 likeliest drugs
   (allele-aware β-lactamases, variant-aware aminoglycosides; ResFinder
   genotype→phenotype tables as citation backbone). ~1h hand-curation. [ROAST]
4. **Metrics harness** (~300 lines): skani components (NOT Mash — CONTRACT.md
   amendment) [ROAST], two-tier splits, full metric suite, ANI + cassette
   audits, reliability + risk-coverage, bootstrap-over-groups CIs. Validate on
   Hu et al. folds (hzi-bifo/AMR_benchmarking, MIT).
5. **Baseline:** per-drug elastic-net LR + Platt + crepes asymmetric conformal +
   ANI-distance override; reference numbers on 2–3 Hu et al. datasets,
   INCLUDING per-group leave-one-clade-out coverage.
6. **Streamlit shell** rendering ANY results JSON (final model = data swap);
   3 cached rehearsal genomes; disclaimer every screen; template report writer.
7. **Parser for organizer precomputed results**: unit-test on synthetic files in
   all 3 plausible formats + v3/v4 header split, BEFORE the event. [ROAST]

## 4. Event day (21h) — the real critical path [ROAST]

- **H0–1:** Verify species/drugs; `amrfinder -l` mutation check; schema
  archaeology; **subsample 100 genomes through the ENTIRE pipeline** to shake
  out parser/schema bugs. Codec/upload test (10s MP4) — deletes a failure class.
- **H1–2:** Decision rule: precomputed results parseable by H2 → use + spot-
  verify 50 genomes; else launch own full batch NOW (4–12h wall — it owns the
  CPU; modeling waits). Leakage cross-check rehearsal pool vs organizer IDs.
- **H2–8:** Batch runs. Meanwhile: mapping table adaptation, demo content on
  rehearsal outputs, label audit, project-page skeleton. Machines by role.
- **H8 — CHECKPOINT:** first grouped-CV numbers. If not beating trivial
  baselines → debug EVALUATION first, not the model. **Nominate the refusal
  genome from CV output (owned deliverable).** If numbers land 0.6–0.8 on hard
  drugs: that's biology, not bugs — do not burn 3h debugging a correct pipeline.
- **H8–12:** Calibration + conformal + gate on organizer splits; per-drug
  unexplained-resistance audit; record backup video run as PRIMARY take.
- **H12 — MODEL FREEZE.** Demo = data swap. LLM prose upgrade attempt starts
  only now, capped 3 person-hours.
- **H12–16:** Video final, project page (metrics tables live HERE, not video),
  tuned-vs-untouched gap slide, threat-model slide.
- **H16–21:** Buffer → submit early → sleep shifts (scheduled, not aspirational).

**Kill list, in order:** k-mer (already dead) → LLM narrative (templates win) →
skani/cassette audit (demote to background) → calibration tab → conformal
(margin-threshold fallback). **Cannot be cut:** demo app, disclaimer, three
evidence categories in video, grouped metrics table, coverage curve.

**Minimum viable submission (from wreckage at H14):** per-drug LR on
AMRFinderPlus features + callability gate + margin no-call; grouped-CV metrics
table + reliability + coverage on organizer splits; Streamlit from cached JSON;
90–120s video cold-opening on the refusal. Scores on every judging axis.

## 5. Demo / video (4 min, inverted) [ROAST]

1. **Cold-open refusal (0:00–0:15):** "This genome made standard tools
   confidently wrong. Ours refused to answer. Here's why that's the win."
2. Problem (20s) — NEW HOOK: "the genome doesn't replace the lab — it tells you
   tonight which cases to rush and which antibiotic not to start with." [ROAST]
3. Genomes A (resistant, spectrum-confirmed evidence) + B (susceptible,
   callability gate panel) compressed to 40s total.
4. The refusal genome + per-group coverage number + one coverage curve (60s).
5. Two numbers + one curve (10s); ATU one-liner; disclaimer.

## 6. CONTRACT.md amendments for genome-firewall/

- Mash → **skani** (ANI + aligned fraction; Mash has no AF).
- "Gene symbol" → **"Element symbol"** (AMRFinderPlus v4 headers).
- splits.json: add the coarse leave-clades-out tier + `heldout_group` semantics
  mapped to it.
- data/: add MIC-only single-standard re-interpretation + flip-rate log.
- features/: add drug→Class/Subclass mapping table + --mutation_all WT tiers.
- rapidata/: crowd-annotation is out of scope for the 21h event; ignore.

## 7. Honest residual risks (say these before judges ask)

- Conformal coverage on unseen groups is approximate — we show empirical
  per-group numbers instead of claiming guarantees.
- The callability gate rarely fires; when it does it's usually assembly QC —
  we present it as such, not as a biological shield.
- Per-isolate confidence is a bin-level frequency, not an individual risk.
- Mechanism-incomplete drugs (porin/efflux) carry a declared unexplained-
  resistance rate and a wider no-call band.
