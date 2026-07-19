# 07 — Competition Meta: Genome Firewall @ Hack-Nation 6th Global AI Hackathon

**Prepared:** 2026-07-18 (event day). **Scope:** what already exists to reuse, what wins/loses at this kind of event, how the AMRFinderPlus "dare" interacts with scoring, what's legal to pre-build, and how to budget the clock.

**⚠️ Headline correction first:** the brief assumes a "~48-hour event." Hack-Nation is a **24-hour hackathon** — official agenda: kickoff & challenge reveal Saturday 12:00–1:00 PM ET, hacking begins **~12:15–1:00 PM Sat July 18**, submission deadline **9:00 AM Sun July 19 ET** — i.e. **~20–21 hours of hacking**, not 48. Finalist pitches (3 min, top-16 teams) happen a week later (July 25). Sources: [hack-nation.ai](https://hack-nation.ai/), [projects.hack-nation.ai](https://projects.hack-nation.ai/) (the two pages differ by ~45 min on kickoff; both agree on the 9:00 AM Sunday deadline). **Halve every time budget in the team plan.**

---

## 1. Open-source genome → AMR prediction pipelines (GitHub census, 2026-07-18)

Stars/license/last-push pulled live from the GitHub API. "Reusable?" = legally + practically for a 21-hour build.

### 1a. End-to-end ML phenotype predictors (the direct competitors to your build)

| Repo | Stars | License | Last push | What it is | Reusable? |
|---|---|---|---|---|---|
| [aldro61/kover](https://github.com/aldro61/kover) | 53 | GPL-3.0 | 2022-08 | k-mer presence/absence → interpretable rule models (Set Covering Machines, CART). [Docs](https://aldro61.github.io/kover/). **Top-ranked ML method** in the big 2024 benchmark (see §2/§4). | Conceptually yes (interpretable rules = evidence categories). Practically risky: unmaintained 4 yrs, heavy jellyfish k-mer-counting step. GPL-3.0 is fine if invoked as an external CLI, but copying code into your GPL-incompatible submission is not. |
| [bioinfo-ut/PhenotypeSeeker](https://github.com/bioinfo-ut/PhenotypeSeeker) | 21 | GPL-3.0 | 2026-01 | k-mer GWAS (chi² filter) → logistic regression per phenotype. 2nd-best ML in benchmark. | Same caveats as Kover. Faster than Kover but memory-hungry on 1k+ genomes. |
| [hzi-bifo/AMR_benchmarking](https://github.com/hzi-bifo/AMR_benchmarking) | 7 | **MIT** | 2024-11 | The benchmark harness from ["Assessing computational predictions of AMR phenotypes"](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full-text): 78 curated PATRIC species×antibiotic datasets, **random / phylogeny-aware / homology-aware fold generators**, nested-CV evaluation, F1-macro metrics. | **Yes — the single best legal accelerator.** MIT-licensed, and it is literally a genetically-grouped-split evaluation harness with public training data. Clone the fold logic and metrics; optionally train on its 31,195-genome datasets pre-event. |
| [hzi-bifo/AMR_prediction_pipeline](https://github.com/hzi-bifo/AMR_prediction_pipeline) | 1 | **MIT** | 2024-09 | Pre-trained Kover/PhenotypeSeeker/ResFinder models for 78 species×drug combos + per-combo software-recommendation table. | If the organizer's species ∈ {E. coli, S. aureus, K. pneumoniae, S. pneumoniae, A. baumannii, P. aeruginosa, M. tuberculosis, E. faecium, S. enterica, C. jejuni, N. gonorrhoeae}, these are ready-made baselines to diff against. Otherwise skip. |
| [jodyphelan/tb-ml](https://github.com/jodyphelan/tb-ml) | 4 | GPL-3.0 | 2023-03 | "A simple tool for creating ML AMR prediction pipelines" — small, readable reference implementation (TB). | Read for structure in hour 0 if useful; not a dependency. |
| [hossainlab/DeepAMR](https://github.com/hossainlab/DeepAMR) | 1 | Apache-2.0 | 2026-02 (created 2026-01) | k-mer multi-label deep learning platform, BV-BRC data. | Immature (1 star, 1 month old at event time). Do not build on it. |
| [farhat-lab/gentb-snakemake](https://github.com/farhat-lab/gentb-snakemake) | 2 | **NO LICENSE** | 2023-06 | TB-only RandomForest pipeline. | No license = all rights reserved. Do not copy code. |
| **AresDB / ARESdb** | — | **Proprietary** | — | Ares Genetics/OpGen commercial AMR knowledge base (~40k genomes, 100+ drugs); exclusively licensed to QIAGEN in 2019 ([QIAGEN press release](https://corporate.qiagen.com/English/newsroom/press-releases/press-release-details/2019/QIAGEN-partners-with-Ares-Genetics-to-advance-global-fight-against-antibiotic-resistant-pathogens/default.aspx), [Mayo study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315026/)). | Not available. Mentioning it in the pitch as "the $ commercial comparator" is fair game. |

### 1b. Rule-based / evidence-extraction tools (your evidence stream (i), NOT your classifier)

| Repo | Stars | License | Last push | Notes |
|---|---|---|---|---|
| [ncbi/amr](https://github.com/ncbi/amr) (AMRFinderPlus) | 377 | Public domain-ish (US Gov work; GitHub flags NOASSERTION) | 2026-07 (active) | The safe-baseline tool itself. Curated Reference Gene Database + HMMs + curated cutoffs; `--organism` enables point-mutation calling ([NCBI docs](https://www.ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance/AMRFinder/), [Feldgarden 2021](https://www.nature.com/articles/s41598-021-91456-0)). **Pre-download the DB (`amrfinder -u`) before the event — don't do it on conference wifi.** |
| [arpcard/rgi](https://github.com/arpcard/rgi) (CARD) | 425 | NOASSERTION | 2026-05 | Alternative AMR-call evidence stream (broader, looser). Useful as a second opinion; disagreeing RGI/AMRFinderPlus calls are a natural "low-confidence / no-call" trigger. |
| [phac-nml/staramr](https://github.com/phac-nml/staramr) | 203 | **Apache-2.0** | 2026-06 | ResFinder/PointFinder/PlasmidFinder scanner with tidy report output. Best-licensed reference for "scan → table → ML features" plumbing. |
| [MDU-PHL/abritamr](https://github.com/MDU-PHL/abritamr) | 100 | GPL-3.0 | 2026-06 | Wraps AMRFinderPlus with species-aware logic and R/S/I classes. Read it for how a production lab turns raw gene calls into conservative phenotype classes. |
| [tseemann/abricate](https://github.com/tseemann/abricate) | 501 | GPL-2.0 | 2026-07 | Mass-screening classic. NCBI explicitly warns ABRicate-with-ncbi-db ≠ AMRFinderPlus results ([NCBI note](https://www.ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance/AMRFinder/)). Fine for a quick feature matrix, but don't present it as "AMRFinderPlus". |
| [jodyphelan/TBProfiler](https://github.com/jodyphelan/TBProfiler) | 136 | GPL-3.0 | 2026-04 | Curated TB mutation→resistance caller. Only if organizer species is TB. |
| [gaarangoa/deeparg](https://github.com/gaarangoa/deeparg) | 58 | MIT | 2026-04 | Deep-learning ARG *identification* (not phenotype prediction). Possible feature stream; heavy for the payoff. |

### 1c. GWAS / association machinery (your evidence stream (ii))

- [mgalardini/pyseer](https://github.com/mgalardini/pyseer) — 136★, **Apache-2.0**, active (2026-03). k-mer/unitig GWAS with population-structure correction. This is the principled engine for "statistical association only" evidence: an association that survives lineage correction is exactly what distinguishes stream (ii) from shortcut learning.
- [BorgwardtLab/maldi_amr](https://github.com/BorgwardtLab/maldi_amr) — 48★, BSD-3, 2022. MALDI-TOF spectra, **not genomes — wrong input type; ignore the code**, but its evaluation design (train/test scenario matrices by species) is the intellectual ancestor of the challenge's grouped-split judging.
- [BorgwardtLab/ConformalAMR](https://github.com/BorgwardtLab/ConformalAMR) — 5★, **no license (all rights reserved)**. Conformal prediction with guaranteed coverage for AMR, but MALDI-based. Read the [paper](https://github.com/BorgwardtLab/ConformalAMR) for the recipe; write your own 50-line split-conformal wrapper (it's `sort(calibration_scores); quantile at ⌈(n+1)(1-α)⌉/n`), don't copy theirs.

### 1d. Verdict for question 1

Nothing on GitHub gives you "FASTA → calibrated 3-way call + no-call + evidence categories" off the shelf. The legal accelerators that exist: **AMR_benchmarking (MIT)** for grouped-split evaluation + public training data; **AMRFinderPlus (public domain)** and **staramr (Apache-2.0)** for evidence extraction; **pyseer (Apache-2.0)** for association-with-lineage-correction. Everything end-to-end is either unmaintained (Kover), license-encumbered (GPL), license-absent (GenTB, ConformalAMR), or proprietary (ARESdb). Your team's own plan (AMRFinderPlus features + per-drug regularized LR + conformal) is *not* redundant with any of these — it is the right scope.

---

## 2. What genomics-hackathon teams build — and the mistakes judges call out

Direct "genomics hackathon post-mortem" writeups are scarce (I found none with technical judging feedback — candid gap). But AMR-specific hackathons exist and mirror this challenge's shape: e.g. the [SPREAD Hackathon 2026 at Statens Serum Institut](https://en.ssi.dk/surveillance-and-preparedness/international-coorporation/spread) (WGS-AST focus) and an [AMR bioinformatics conference+hackathon track](https://mcarthurbioinformatics.ca/?p=2915) (McArthur lab/CARD community). What judges with bioinformatics literacy punish is well documented in the literature:

1. **Random splits / homolog leakage — the #1 killer.** The hzi-bifo benchmark ([bioRxiv 2024.01.31.578169](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full-text)) trained Kover/PhenotypeSeeker/Seq2Geno2Pheno/Aytan-Aktug on 78 PATRIC datasets under three fold types. ML hit **F1-macro ≥ 0.9 in 64% of random-fold experiments but only 33% (phylogeny-aware) and 25% (homology-aware)**. A team reporting "97% accuracy" from a random split is advertising exactly the number the challenge's hidden-test design (unseen genetic groups) is built to destroy. The benchmark calls the mechanism **shortcut learning**: models pick up clade-background k-mers, not resistance mechanisms.
2. **Leaky preprocessing.** [Whalen, Schreiber, Noble & Pollard, *Navigating the pitfalls of applying machine learning in genomics*, Nat Rev Genet 23:169–181 (2022)](https://escholarship.org/content/qt6f5210xq/qt6f5210xq_noSplash_a2d4f168c601186bcfc04cbf01746184.pdf?t=rb04hp): feature selection/normalization/embedding fit on all data before splitting is pervasive in genomics and inflates everything. Fix inside CV folds only.
3. **Population-structure confounding sold as signal.** Same benchmark's misclassification analysis shows errors concentrate by clade; [Anahtar, Yang & Kanjilal, J Clin Microbiol 2021](https://pubmed.ncbi.nlm.nih.gov/39399439/) reviews the pattern across AMR ML. If your "statistical association" features disappear after lineage correction, they were stream-(iii) noise, not stream-(ii) signal.
4. **Headline-accuracy overselling on imbalanced labels.** Judges at data challenges read past accuracy; this challenge *bakes in* the antidotes (balanced accuracy, per-drug F1/PR-AUC, Brier, coverage curves). Showing only one number is a self-own.
5. **"No marker found ⇒ susceptible."** Rule-based determinants miss novel/mechanism-free resistance; inter-lab studies found bioinformatic AMR predictions discordant even between curated tools ([Doyle et al., Microb Genomics 2020](https://www.nature.com/articles/s41467-022-35713-4) ref 11; [Feldgarden 2019](https://pubmed.ncbi.nlm.nih.gov/31427293/): AMRFinder vs ResFinder differed on 8.8% of gene symbols). The challenge's molecular-target-presence gate is precisely the anti-pattern detector for this mistake — make a show of passing it.
6. **Demo overclaim.** Any implication of clinical validity without "research use only — confirm with standard lab testing" reads as naïveté to a bio-literate judge. The challenge makes the disclaimer mandatory; put it in the UI, the video, and the report footer.

---

## 3. Prior Hack-Nation events: what won and why

- **Scale/format:** 5th edition: 5,500+ applications → 2,000 selected hackers, 65+ countries ([NUST SEECS writeup](https://seecs.nust.edu.pk/in-the-spotlight/nust-seecs-students-shine-on-the-global-stage-3rd-place-at-hack-nations-global-ai-hackathon/)). Challenges are revealed at kickoff; submissions live on [projects.hack-nation.ai](https://projects.hack-nation.ai/) and are **editable until the deadline**; submission includes a **video (MP4/H.264 recommended)**; **top 16 teams** across challenges pitch live for 3 min a week later ([platform FAQ](https://projects.hack-nation.ai/)).
- **A documented winner:** *LabMind AI* (NUST team) — 3rd place, "Fulcrum Science Challenge," 5th edition: a **full-stack product** turning research hypotheses into costed experiment plans — i.e. a workflow product with a crisp narrative, not a bare model ([NUST SEECS](https://seecs.nust.edu.pk/in-the-spotlight/nust-seecs-students-shine-on-the-global-stage-3rd-place-at-hack-nations-global-ai-hackathon/), [project link](https://projects.hack-nation.ai/#/project/b6762400-943a-4ffb-ac93-95603267b040?returnTo=%2Fwinners)).
- **The venture filter:** Hack-Nation brands itself "hackathon → venture starting line"; its front page features an Anto (YC F25) founder who took the same project from hackathon to YC seed ([hack-nation.ai](https://hack-nation.ai/)). Judging language is "working AI product," "pitch to operators and investors."
- **Implication for Genome Firewall:** the leaderboard metrics get you to finalist; the 3-minute pitch to operators/investors wins it. The pitchable story here is *trustworthy abstention*: "everyone can bolt AMRFinderPlus onto sklearn; we built the system that knows when it doesn't know — genetically-grouped honest evaluation, calibrated confidence, a gate that never says 'susceptible' just because it found nothing." That maps directly onto the challenge's stated judging axes. Caveat: no official technical rubric is public; this is inference from organizer marketing + one winner profile.

---

## 4. The "replace or improve upon AMRFinderPlus" dare — what it implies about scoring

What AMRFinderPlus actually is: curated database (4,579 AMR proteins + 560+ HMMs as of the 2019 validation) + BLAST/HMM with curated per-family cutoffs + species-specific point-mutation panels. Validated at **98.4% genotype–phenotype consistency over 87,679 AST tests** on 6,242 NARMS isolates ([Feldgarden 2019, AAC 63:e00483-19](https://pubmed.ncbi.nlm.nih.gov/31427293/)); ResFinder 4.0 hit **98.8% concordance** on 7,489 Salmonella drug observations ([Bortolaia 2020, JAC dkaa345](https://backend.orbit.dtu.dk/ws/portalfiles/portal/264045068/dkaa345.pdf)). On well-cataloged species×drug combos, this is close to a performance ceiling.

The dare interacts with the hidden-test design, and the benchmark literature tells you which side wins where:

- **Random folds: ML > rules.** Kover best on 30% of combos vs ResFinder 25% ([hzi-bifo benchmark](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full-text)).
- **Divergent genomes (the challenge's actual test condition): rules > ML.** ResFinder best on **44% (phylogeny-aware) and 50% (homology-aware)** of datasets vs Kover's 28%/34%; ML's susceptible-class precision ≥0.95 collapsed from 47% of experiments (random) to **30% (homology-aware)**.
- **Rules have a coverage hole:** ResFinder had no catalog for 13/78 (17%) of species×drug combos and scored ~0 there. ML's advantage is filling catalog gaps and catching novel determinants.

**Scoring read:** the dare is bait. "Replacing" AMRFinderPlus means throwing away the single strongest generalizer to unseen groups — the exact condition of the hidden test. "Improving upon" means: keep it as evidence stream (i) and add value only where it's blind — (a) catalog gaps and novel/divergent resistance via a homology-safe association stream, (b) calibrated probabilities + no-call where it emits uncalibrated booleans, (c) the target-presence gate to kill false "susceptible" calls (the most dangerous error class: susceptible-class precision is what degrades most under divergence). Expect the organizers to run an AMRFinderPlus-only reference baseline; your margin over it comes from the coverage/accuracy tradeoff and calibration axes (Brier, reliability plot, accuracy-at-coverage), not raw accuracy on catalog-covered combos. A submission that just wraps AMRFinderPlus scores ~0 on evidence categories (ii)/(iii), calibration, and probably the gate.

---

## 5. What can legally/practically be pre-built before the dataset drops

**Rules status (verified 2026-07-18):** no code-freshness rule is published on [hack-nation.ai](https://hack-nation.ai/), the [submission platform FAQ](https://projects.hack-nation.ai/), or the [Luma event page](https://luma.com/90ndbjym). The industry-default rulebook ([MLH standard hackathon rules](https://github.com/MLH/mlh-policies/blob/master/standard-hackathon-rules.md)) says "all work on a project should be done during the period of the hackathon" but "teams can use an idea they had before the event" — and open-source libraries are universally permitted ([Devpost default rules template](https://hg-hackathon.devpost.com/rules) is similar). **Crucially, this challenge's own brief explicitly sanctions pre-event prep** ("pre-event prep must use public data (BV-BRC/PATRIC etc.)", dataset "only drops at event start") — the organizers are telling you the intended meta is: arrive with a working pipeline, spend event hours on their data.

**De-risk protocol:** (1) keep the pre-event repo public with honest timestamps; (2) write a PREBUILT.md listing what existed before kickoff; (3) confirm in the kickoff Q&A/Discord that pre-trained-on-public-data models and scaffolding are within challenge rules; (4) never pre-train on anything that could overlap organizer data — see the leakage trap below.

**Pre-build checklist (all defensible):**
- FASTA ingestion + QC + report (length, N50, contamination heuristics).
- AMRFinderPlus runner with **DB pre-downloaded** (`amrfinder -u`), plus a precomputed-results parser (the brief says organizers may hand you AMRFinderPlus output — handle both paths).
- Homology dedup + grouped-split harness: MMseqs2 `easy-cluster` → cluster IDs → `GroupKFold`; verify no cluster crosses folds. (Or lift the MIT-licensed fold logic from [hzi-bifo/AMR_benchmarking](https://github.com/hzi-bifo/AMR_benchmarking).)
- **Metrics harness first** (your plan is right): balanced accuracy, per-drug F1/AUROC/PR-AUC, Brier, reliability diagram, accuracy-at-coverage curve — all unit-tested on synthetic predictions before event day.
- Split-conformal no-call layer skeleton (calibration-set plumbing, per-drug α, monotone coverage reporting).
- Streamlit shell: upload FASTA → predictions table + evidence badges + reliability plot + hard-coded mandatory disclaimer banner. Demo shell should run end-to-end on a toy genome pre-event.
- Public-data training corpus: BV-BRC/PATRIC genomes+AST (the benchmark's 78 datasets are a shortcut — 31,195 genomes, quality-filtered). Pre-trained per-drug LR models transfer only if the organizer species is one of the 11 benchmark species.
- LLM report-writer template with evidence-citation-by-ID schema and a fixed "confirm with standard laboratory testing" footer. Budget: $50 credits ≈ 1M+ GPT-4o-mini-class tokens; use <$5 for dev loops, reserve the rest; template-fill fallback if the API flakes.

**Cannot be pre-built:** the antibiotic list, label semantics (their S/I/R thresholds, whether "intermediate" exists), the actual group structure, demo screenshots, and any submission video.

**⚠️ Leakage trap in pre-training:** if organizers assembled their ~1k–3k genomes from public archives, your public-data training set may *contain hidden-test genomes*. That both inflates your internal validation and may violate the spirit of the grouped-split test. De-dup your pre-trained corpus against the organizer's train/calibration IDs/sequences at event start, and state in the writeup that you did.

---

## 6. Time-budget template (corrected for the real ~21 hours)

The only quantitative study of phase allocation I could verify: an analysis of ESTIA's "24 Hours of innovation" (2008–2010 data) found **winning teams worked 16.25 h of 24 vs 16.10 h for non-winners — raw hours don't differentiate; allocation does** (winners spent more on task planning, less thrashing on specification) ([Dubois thesis, ETS Montréal](https://espace.etsmtl.ca/id/eprint/1511/14/DUBOIS_Mario-web.pdf)). Plan for ~16–17 h of effective work, 3–4 h sleep in shifts. All-nighters in bioinformatics plumbing produce strand/label bugs that cost more than they buy.

| Window (ET) | Hours | Deliverable gate |
|---|---|---|
| Sat 1 PM – 2 PM | 0–1 | Data unpacked; splits/labels verified; QC report. **No modeling until split structure is understood.** |
| Sat 2 PM – 4 PM | 1–3 | AMRFinderPlus features + trivial baselines (majority-class, gene-presence rules) through the **pre-built metrics harness** on organizer grouped splits. First end-to-end result by H3. |
| Sat 4 PM – 9 PM | 3–8 | Per-drug regularized LR + target-gate + conformal no-call; grouped CV; first reliability plots. **Checkpoint H8: if not beating trivial baselines, debug evaluation before adding features.** |
| Sat 9 PM – 2 AM | 8–13 | Optional k-mer/association stream — **kill criterion: drop it at H10–11 if CV shows no headroom over AMRFinder-features LR**. Otherwise: per-drug error analysis + calibration polish. Sleep shift A. |
| Sun 2 AM – 6 AM | 13–17 | Demo assembly (Streamlit + LLM report writer + disclaimers); README/writeup skeleton; sleep shift B. **LLM fallback: template text if API fails once.** |
| Sun 6 AM – 7:30 AM | 17–18.5 | Model freeze. Full metrics re-run from clean checkout. No new features. |
| Sun 7:30 AM – 9:00 AM | 18.5–21 | Video (MP4/H.264), submission page, buffer. **Hard freeze 30 min before deadline** — platform allows edits until 9:00 AM, don't rely on last-minute uploads. |

Post-event lever: finalists pitch July 25 (3 min) — the week between is for pitch polish, not model changes (submission is frozen at deadline).

---

## Self-roast

1. **"Pitch beats metrics" is inferred, not verified.** Hack-Nation publishes no technical judging rubric; my read leans on organizer marketing and one university PR story. If Genome Firewall is scored like a Kaggle task by an automated leaderboard, hours spent on demo polish (H13–17 in my budget) would be better spent on the coverage curve — the opposite of my advice. The honest hedge is that the brief's own judging list (grouped splits, Brier, reliability, coverage) is metrics-heavy, so maybe the demo matters less than §3 implies.
2. **The pre-build green light rests on a norms argument, not a rules document.** I found no published Hack-Nation code-freshness rule; MLH-style defaults (which Hack-Nation may well adopt at kickoff) say all work happens during the event. If organizers disallow pre-trained models or extensive scaffolding, following §5 wastes the prep and — worse — risks disqualification if the team doesn't disclose. The disclosure-first protocol mitigates but doesn't eliminate this. My recommendation to confirm in kickoff Q&A could also get a non-answer ("see brief"), leaving the ambiguity unresolved at hour 0.
3. **My repo picks could burn the clock instead of saving it.** Star counts and licenses are today-snapshot GitHub API data; I did not install anything. Kover is unmaintained since 2022 with a heavy jellyfish dependency chain — recommending it (even "as reference") in a 21-hour event invites dependency hell. Similarly, betting on the AMR_benchmarking datasets assumes the organizer's species/antibiotics overlap its 11-species/44-drug PATRIC-2020 snapshot; if not, pre-trained baselines transfer ~nothing (the same benchmark shows cross-species LOSO models collapse, p≈1e-13–1e-19), and the pre-event training time was a sunk cost. The safest reading of my own report is: pre-build *harness and plumbing*, treat pre-trained models as a lottery ticket.
