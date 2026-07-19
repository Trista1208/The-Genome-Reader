# 04 — Evaluation Rigor & No-Call Design

**Scope:** homology de-dup tooling & thresholds, cluster-aware splitting, calibration under small
calibration sets, conformal no-call layers, risk–coverage curves, exact metric definitions +
a <1-day sklearn harness plan, and how grouped hidden-test generalization is typically scored.
Verified 2026-07-18 against primary sources; versions pinned where relevant.

**Environment pins (verified via PyPI/bioconda APIs, 2026-07-18):**
`scikit-learn 1.9.0`, `mapie 1.4.1` (v1 API!), `crepes 0.9.1`;
bioconda `skani 0.3.2`, `fastani 1.34`, `mash 2.3` — all with `osx-arm64` builds (Apple Silicon OK).

---

## TL;DR — build this / skip this

| Decision | Recommendation | Why |
|---|---|---|
| De-dup/clustering tool | **skani** (`skani triangle`), Mash as fallback | fast, gives ANI **and aligned fraction**, trivial install |
| "Never cross splits" threshold | **ANI ≥ 99.5% AND AF ≥ 80%** (single-linkage); strict tier 99.9% for exact dupes | matches literature's "sequence type/genomovar" band; 95% is *species*, far too loose |
| Splitting | Cluster IDs as `groups` in `StratifiedGroupKFold`; audit: **zero cross-split pairs ≥ 99.5% ANI**, report max cross-split ANI | mirrors challenge's "genetically grouped splits" |
| Calibration | **Platt/sigmoid** (cal sets will be ~hundreds of genomes); isotonic only if ≥ ~1000 cal points per drug | sklearn user guide's own rule of thumb |
| No-call layer | **Split-conformal, class-conditional (Mondrian-by-class), α=0.10**, via `crepes` (5 lines) | per-class error control = the safety story judges want |
| Risk–coverage | Sort by confidence, plot **accuracy-at-coverage AND balanced-accuracy-at-coverage**, per drug | directly the brief's "no-call rate vs accuracy-at-coverage" |
| Harness | One `metrics.py`, ~300 lines, built **before** modeling; bootstrap CIs over **groups**, not genomes | everything else is tuning |
| Skip | temperature scaling (binary tasks), MAPIE deep-dive, APS/RAPS, AURC normalization schemes | time sinks with ~zero payoff here |

---

## 1. Homology de-duplication: Mash vs fastANI vs skani

### 1.1 The tools

| | Mash | fastANI | skani |
|---|---|---|---|
| Method | MinHash k-mer sketches, distance ≈ mutation rate | alignment-free approximate mapping (Mashmap) | sparse chaining of seeds |
| Output | distance only, **no aligned fraction (AF)** | ANI + AF | ANI + AF |
| Relative speed | sketching slowest of the three (skani sketches ~3× faster); pairwise dist very fast | baseline | querying ~25× faster than fastANI |
| Reference scale | — | 8.01 **billion** pairwise comparisons over 90K genomes in the paper | query vs >65,000 genomes in **seconds, ~6 GB RAM** |
| Install | `conda install -c bioconda mash` (2.3) | `conda install -c bioconda fastani` (1.34) | `conda install -c bioconda skani` (0.3.2); static Linux binary also on GitHub releases |
| Paper | Ondov et al. 2016, Genome Biol 17:132 | Jain et al. 2018, Nat Commun 9:5114 | Shaw & Yu 2023, Nat Methods 20:1661 |

Sources: [skani GitHub README](https://github.com/bluenote-1577/skani),
[skani paper (PubMed)](https://pubmed.ncbi.nlm.nih.gov/37735570/) (">20× faster [than FastANI] for fragmented, incomplete MAGs... query against >65,000 prokaryotic genomes in seconds and 6 GB memory"),
[fastANI paper (PubMed)](https://pubmed.ncbi.nlm.nih.gov/30504855/) ("up to three orders of magnitude faster compared to alignment-based approaches"; 8.01B pairs; 99.8% of pairs conform to ">95% intra-species and <83% inter-species ANI"),
[VEBA 2.0 paper](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10979853/) ("~25× faster than FastANI", loads index once, computes (N²−N)/2 pairs).

**At the challenge scale (1k–3k genomes, one species) all three finish in minutes on a laptop; pick
on output quality, not speed.** Mash's missing aligned fraction is a real weakness: two genomes can
share high ANI over a small aligned region (or an incomplete assembly can depress sketch overlap —
[Mash may underestimate ANI for incomplete genomes](https://github.com/bluenote-1577/skani)).
**Use skani.** Keep Mash as a one-command fallback if conda acts up at 2 a.m.

### 1.2 Commands (verify flags against `--help` on event day)

```bash
# skani all-vs-all: full matrix OR edge list (edge list is what you want for clustering)
skani triangle genomes/* -E -t 8 > skani_edges.tsv     # cols: ref, query, ANI, AF_ref, AF_query
# Mash fallback
mash sketch -o all genomes/*.fasta && mash dist -t all.msh all.msh > mash.tsv
# fastANI alternative (needs query/reference lists)
fastANI --ql genomes.txt --rl genomes.txt -o fastani.tsv -t 8
```

Then in Python: edges with `ANI ≥ τ` and `min(AF_ref, AF_query) ≥ 0.8` → graph →
**connected components = group IDs**. (skani only outputs pairs with AF ≥ 15%, i.e. reliably
> ~82% ANI — fine for de-dup thresholds ≥ 95%:
[skani output docs](https://github.com/bluenote-1577/skani).)

### 1.3 Defensible thresholds — what bacterial genomics actually uses

| Level | Threshold | Source |
|---|---|---|
| Same **species** | ANI ≥ 95% (≈ 70% DDH; Mash D ≤ 0.05) | [Goris et al. 2007](https://pubs.acs.org/doi/10.1021/acs.est.2c02081) (citing IJSEM 57:81); empirically confirmed as the discontinuity in [Jain 2018](https://pubmed.ncbi.nlm.nih.gov/30504855/); GTDB dereplication used "Mash ≤ 0.05 (~ANI 95%)" ([Parks et al. 2018, GTDB](https://www.biorxiv.org/content/10.1101/256800v2.full-text)) |
| "Same genome" dereplication default | ANI ≥ 99% | dRep default secondary threshold ("how similar genomes need to be to be considered the *same*") — [dRep docs/training material](https://trainings.migale.inrae.fr/posts/2022-05-10-module9bis/content/slides.html); primary pre-cluster is Mash 90% |
| **"Sequence type / genomovar"** | **ANI ≥ 99.5%** | [Rodriguez-R et al., mLife 2023](https://www.sciopen.com/local/article_pdf/10.1002/mlf2.12088.pdf): recommended table — strain >99.99%, genomovar/sequence type >99.5%, species >95% |
| Same **strain** (strict) | ANI > 99.99% | same mLife paper; no further ANI gap found within 99.5% clusters across 300 species ([NSF archive copy](https://par.nsf.gov/servlets/purl/10476572)) |
| Hierarchical practice | 96 / 98 / 99 / 99.5 / 99.9 / 99.99% | [BacTaxID, 2025](https://www.biorxiv.org/content/10.64898/2025.12.09.693184v2.full-text) — hierarchical ANI typing over 2.3M genomes |

Mash distance ≈ 1 − ANI (so 0.05 ≈ 95% ANI, 0.005 ≈ 99.5%):
[MicroScope docs](https://microscope.readthedocs.io/en/3.16.4/content/compgenomics/genoclust.html).

**Recommendation (defensible in 2 sentences to a judge):**
- *De-dup/split guarantee tier:* **ANI ≥ 99.5% + AF ≥ 80% ⇒ same group, never crosses train/test.**
  Rationale: 99.5% is the literature's "sequence type/genomovar" boundary — clones, outbreak
  transmissions, and technical replicates all sit far above it (re-sequencing noise ≈ 99.99%+),
  while genuinely distinct strains of the same species sit below it.
- *Strict tier:* also compute 99.9% clusters; these are near-duplicates — optionally keep only one
  representative in training (see §2 caveat on class balance), and use them for the leakage audit.
- *Sanity gate:* confirm the whole dataset clusters as one species at 95% (it should, per the brief).

**Caveats to state out loud (they make you look smarter, not weaker):**
- **Single-linkage chaining:** in a clonal species (extreme case: *M. tuberculosis*, where nearly all
  genomes are >99.9% ANI to each other), 99.5% single-linkage can collapse most of the dataset into
  one component → too few groups for CV. If the species turns out hyper-clonal, fall back to 99.9%
  clusters or core-genome-SNP phylogeny clades (as in the [PLoS Biol 2025 study](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539)).
  **Decision rule: if the largest 99.5% component holds >50% of genomes, tighten to 99.9%.**
- The organizer hands you *fixed* splits. Your de-dup is for (a) de-duplicating **training**
  (the brief explicitly asks), (b) **auditing their splits** (report max cross-split ANI — a killer
  slide), and (c) your internal validation. You cannot re-split their official train/cal/test.

---

## 2. Cluster-aware splitting: what the AMR genotype→phenotype literature does

The evidence that random splits inflate AMR prediction is direct and recent:

1. **Luo et al. 2024, Briefings in Bioinformatics** ([PMC11070729](https://pmc.ncbi.nlm.nih.gov/articles/PMC11070729/),
   code: `github.com/hzi-bifo/AMR_benchmarking`): 78 PATRIC species–antibiotic datasets, 4 ML methods
   + ResFinder, each evaluated under **random folds, phylogeny-aware folds, and homology-aware folds**.
   Headline (their Table 2): fraction of experiments with F1-macro ≥ 0.9 was **64% random → 33%
   phylogeny-aware → 25% homology-aware**; F1 ≥ 0.8: 81% → 60% → 50%. Clinically critical
   susceptible-class precision ≥ 0.95: **47% → 39% → 30%**. And the rule-based ResFinder was the best
   method in only 25% of combos under random splits but **44%/50% under phylogeny/homology splits** —
   i.e., *ML's edge over known-marker rules largely evaporates on divergent genomes.* This is the
   single most on-point citation for your "threat model" slide, and it directly justifies the
   molecular-target gate: absence of a marker is exactly where ML-without-gate fails silently.
2. **PLoS Biology 2025** ([link](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539)):
   defines clades from core-genome phylogeny, trains with resistant (or susceptible) samples of a
   clade *excluded*, tests on the held-out clade → demonstrates clade-structured sampling confounds
   predictions. This is the design pattern closest to the challenge's "hidden test includes unseen
   groups": **leave-one-clade-out**.
3. **Kim et al. 2022, Clinical Microbiology Reviews** ([PMC9491192](https://pmc.ncbi.nlm.nih.gov/articles/PMC9491192/)):
   the field's standard practice is still mostly random k-fold CV — i.e., most published numbers are
   the optimistic 64%-style numbers, not the 25%-style ones. Cite this to justify distrusting
   literature accuracy claims when setting your own expectations.
4. Ren et al. 2022 (Bioinformatics 38:325–334, [doi:10.1093/bioinformatics/btab681](https://doi.org/10.1093/bioinformatics/btab681))
   is the canonical PATRIC ML baseline paper; the 2024 benchmark above is effectively its stress-test.

**Practical recipe (build this):**
- Groups = skani connected components (§1). Split with
  [`StratifiedGroupKFold`](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html)
  (keeps class balance while respecting groups; plain `GroupKFold` does not stratify).
- Nest it: outer grouped folds for honest estimates, inner grouped folds for any threshold/C tuning.
  Never tune on the same grouped fold you report.
- **Leakage audit metric (one number + one plot):** maximum cross-split ANI between train and
  validation/test partitions (target: no pair ≥ 99.5%), plus a histogram of cross-split ANI values.
  Cheap to compute from the §1 edge list, devastatingly persuasive in the demo.
- Keep a **random-split number alongside the grouped number** in your report. The gap *is* the
  honest-generalization story; judges have read the brief, they'll recognize it.

---

## 3. Calibration with small calibration sets: Platt vs isotonic vs temperature

The challenge gives you a grouped **calibration split** — at 1k–3k total genomes, expect a few
hundred calibration points per drug, possibly ~100–300. That decides the question:

- **Platt (sigmoid):** 2-parameter logistic on the model score. "Most effective for **small sample
  sizes**" — [sklearn probability-calibration user guide](https://scikit-learn.org/stable/modules/calibration.html).
  Strictly monotonic ⇒ preserves ranking ⇒ **AUROC unchanged** (explicit note in the same guide).
- **Isotonic:** non-parametric, can fix any monotonic distortion, but "more prone to overfitting,
  especially on small datasets"; the guide's rule of thumb: isotonic performs as well or better
  only with **> ~1000 samples**. Also introduces **ties** in predicted probabilities, which can
  perturb AUROC. ⇒ Skip at this data scale.
- **Temperature scaling** ([Guo et al. 2017](https://arxiv.org/abs/1706.04599)): a *multiclass*
  method (softmax over logits with one scalar T). Your task is 3–5 **independent binary** problems
  (one per drug), where temperature = a 1-parameter restriction of Platt. Strictly dominated here.
  Note: sklearn 1.9's `CalibratedClassifierCV` now even has `method="temperature"` — still skip.

Also note the same user guide's observation that **well-specified `LogisticRegression` is often
already close to calibrated** (canonical link / balance property) — so measure ECE/Brier pre- and
post-calibration on the grouped validation; if the LR is already calibrated, say so and keep the
calibrator anyway as insurance (it costs nothing).

**Implementation (sklearn 1.9.0):** `cv="prefit"` was deprecated in 1.6; the current pattern is:

```python
from sklearn.frozen import FrozenEstimator
from sklearn.calibration import CalibratedClassifierCV
cal = CalibratedClassifierCV(FrozenEstimator(fitted_lr), method="sigmoid")
cal.fit(X_cal, y_cal)          # grouped calibration split ONLY
p_fail = cal.predict_proba(X_test)[:, 1]
```

([user guide](https://scikit-learn.org/stable/modules/calibration.html)). Do **not** use
`CalibratedClassifierCV` with internal k-fold CV on grouped data unless you pass grouped folds;
simplest is the FrozenEstimator pattern on the provided cal split. Per drug, you can try both
sigmoid and isotonic and pick by **Brier on a held-out grouped fold** — but default to sigmoid.

---

## 4. Conformal prediction for the no-call layer

### 4.1 What split-conformal gives you

With conformity scores s₁..sₙ on an exchangeable calibration set and
q̂ = the ⌈(n+1)(1−α)⌉/n empirical quantile, the set C(x) = {y : s(x,y) ≤ q̂} satisfies
**P(Y ∈ C(X)) ≥ 1−α marginally**, no distributional assumptions
([Angelopoulos & Bates 2023, *Conformal Prediction: A Gentle Introduction*](https://arxiv.org/abs/2107.07511)).
For classification the standard score is **LAC**: s = 1 − p̂(true class)
([Sadinle, Lei & Wasserman 2019, JASA](https://www.tandfonline.com/doi/full/10.1080/01621459.2018.1507496);
also [MAPIE theoretical docs](https://mapie.readthedocs.io/en/latest/theoretical_description_classification.html)).

**The binary case (your case) has a beautifully simple decision rule.** With calibrated p = p̂(fail):
a test genome gets *both* classes in its set (⇒ no-call) iff `min(p, 1−p) ≥ 1 − q̂`, i.e.
`p ∈ [1−q̂, q̂]`. So conformal in binary = a principled, data-driven way to set the no-call band
edges — you get the same object a hand-tuned margin would give, but with a coverage guarantee and a
one-line theoretical justification for the judges.

**Class-conditional / Mondrian variant:** run the quantile per true class on calibration data ⇒
per-class thresholds q̂_y, giving **P(Y ∈ C(X) | Y=y) ≥ 1−α for each class y** (Sadinle et al. 2019;
Mondrian CP, Vovk et al.). In this challenge that is *the* guarantee to put on a slide:
> "Among truly resistant genomes, at most ~α receive a pure 'likely to work' call; among truly
> susceptible, at most ~α receive a pure 'likely to fail' call — distribution-free."

Cost: the minority class has fewer calibration points ⇒ larger q̂ ⇒ more no-calls there. Worth it.

**The honest caveat (also a slide):** the guarantee is *marginal over exchangeable draws*. The
hidden test contains **unseen genetic groups**, which violates exchangeability ⇒ the 1−α coverage
holds only approximately on the hidden set. Nothing distribution-free can fix that; your defense is
(a) calibrate on the *provided grouped* calibration split (best available proxy for the shift), and
(b) verify empirical coverage on your own grouped validation folds. This is exactly the kind of
candid limitation the "threat model" framing wants.

### 4.2 Libraries (verified versions and APIs, 2026-07-18)

**`crepes 0.9.1` — recommended** ([PyPI](https://pypi.org/project/crepes/),
[docs](https://crepes.readthedocs.io/en/latest/crepes_nb_wrap.html),
[GitHub](https://github.com/ConformalPrediction/crepes)). Wraps any sklearn classifier; 5 lines per drug:

```python
from crepes import WrapClassifier
cc = WrapClassifier(fitted_calibrated_lr)          # has .predict_proba
cc.calibrate(X_cal, y_cal, class_cond=True)        # class_cond=True ⇒ Mondrian-by-class
sets = cc.predict_set(X_test, confidence=0.90)     # bool matrix n×2: which classes are in the set
cc.evaluate(X_val, y_val, confidence=0.90)         # -> error, avg_c, one_c, empty, ...
```

Map sets to the 3-way decision: `[1,0]`→"likely to fail", `[0,1]`→"likely to work", `[1,1]`→"no-call"
(`[0,0]` shouldn't occur for binary with sensible scores; assert it). `evaluate` returns `one_c`
(singleton rate = 1 − no-call rate), `avg_c`, and empirical `error` — your coverage check for free.
Concrete expectation-setting from crepes' own quickstart example: at 99% confidence their demo RF
produces `one_c ≈ 0.37` — i.e. **~63% non-singleton (no-call) predictions**. Lesson: **α=0.10
(90% confidence) is the sane operating point; 95–99% confidence explodes the no-call rate** in a
binary problem. Sweep confidence ∈ {0.80, 0.85, 0.90, 0.95} on grouped validation and pick per drug.

**`mapie 1.4.1` — fine, but note the v1 API rewrite.** `MapieClassifier` is gone; it's now
`SplitConformalClassifier(estimator=..., confidence_level=0.9, conformity_score="lac", prefit=True)`
with an explicit `.fit()` → `.conformalize(X_cal, y_cal)` → `.predict_set(X)` workflow
([v1 release notes](https://mapie.readthedocs.io/en/stable/v1_release_notes.html),
[module docs](https://mapie.readthedocs.io/en/latest/_modules/mapie/classification.html)).
Richer (APS/RAPS, risk control), but crepes' `class_cond=True` flag is the shortest path to the
per-class guarantee, and half the MAPIE tutorials on the internet still show the dead v0 API —
avoid that confusion mid-hackathon.

**Ignore for this task:** APS/RAPS (multiclass set-size optimizers — pointless in binary),
cross-conformal/jackknife+ (you have a dedicated cal split; split-conformal is cheaper and the
guarantee is cleaner).

### 4.3 Expected no-call rates — set expectations honestly

There is no universal number; the no-call rate at confidence 1−α equals the mass of calibrated
probabilities inside `[1−q̂, q̂]`, which depends on model sharpness. Rules of thumb to plan around:
- well-separated problem (AUROC ~0.95+, peaked probabilities): α=0.10 ⇒ often **10–25% no-calls**;
- mediocre drug (AUROC ~0.8): α=0.10 ⇒ **30–50%**;
- α=0.05 (95%): roughly double the band width ⇒ no-call rates can double.
Measure per drug; report no-call rate alongside accuracy-at-coverage — which is exactly the brief's
metric pairing (§5).

---

## 5. Risk–coverage curves: compute and present

Standard selective-classification machinery
([El-Yaniv & Wiener 2010, JMLR](https://www.jmlr.org/papers/v11/elyaniv10a.html);
[Geifman & El-Yaniv 2017, arXiv:1705.08500](https://arxiv.org/abs/1705.08500);
pitfalls: [Pugnana et al., "Overcoming Common Flaws in the Evaluation of Selective Classification
Systems", 2024](https://arxiv.org/html/2407.01032v2)):

1. Confidence per call: `c = max(p, 1−p)` restricted to *called* genomes (or, for the conformal
   variant, order called points by distance from the no-call band edge).
2. Sort descending by c. For k = 1..n_called: **coverage(k) = k/n_total** (denominator = *all*
   genomes, including no-calls!), **risk(k) = errors among top-k / k**.
3. Plot **accuracy-at-coverage = 1 − risk(k)** vs coverage. The no-call mechanism sets the right
   endpoint (max coverage achievable); the curve shows what buying back accuracy costs in coverage.

Presentation decisions:
- The brief says "**no-call rate vs accuracy-at-coverage**" ⇒ the x-axis *is* (1 − no-call rate).
  Plot both plain accuracy and **balanced accuracy at coverage** (classes are imbalanced; the brief
  leads with balanced accuracy, so this is likely closer to how they think).
- Report the **full curve per drug** (small multiples, one figure) + a table at fixed coverages
  {100%, 90%, 80%, 70%}. AURC as a scalar summary is optional
  ([Geifman & El-Yaniv 2017](https://arxiv.org/abs/1705.08500)); normalized variants exist
  ([arXiv:2603.07330](https://arxiv.org/pdf/2603.07330)) — skip, not worth the complexity.
- **Sanity requirement:** accuracy must be non-decreasing as coverage drops. If not, your
  confidence ranking is broken (or no-calls are mislabeled) — great automated test for the harness.
- Tune thresholds/α on grouped validation only; touching the test split for operating-point
  selection is the canonical flaw called out in
  [Pugnana et al. 2024](https://arxiv.org/html/2407.01032v2).

---

## 6. Metrics: exact definitions and the <1-day harness

### 6.1 Definitions mapped to sklearn 1.9.0 (positive class = "resistant / likely to fail", per drug)

| Brief metric | Definition | sklearn call |
|---|---|---|
| Balanced accuracy | mean of per-class recall = (TPR + TNR)/2, on **called** genomes | [`balanced_accuracy_score(y, ŷ)`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html) |
| F1 | harmonic mean of precision/recall; report per-class and macro | `f1_score(y, ŷ, average=None)` / `average='macro'`; set `zero_division=0` |
| AUROC | ranking quality, threshold-free, on all genomes w/ probabilities | `roc_auc_score(y, p)` |
| PR-AUC | area under precision–recall; more informative under imbalance | `average_precision_score(y, p)` (that's what "PR-AUC" means in practice) |
| Brier score | mean (p − y)² over all genomes (probabilities always exist) | `brier_score_loss(y, p)` |
| Reliability diagram | 10 equal-width bins: bin mean of p vs observed frequency, + counts histogram | `calibration_curve(y, p, n_bins=10)` + matplotlib (or `CalibrationDisplay.from_predictions`) |
| ECE (for the slide) | Σ_bins (n_b/n)·|acc_b − conf_b| | ~6 lines of numpy over `calibration_curve` output ([Guo et al. 2017](https://arxiv.org/abs/1706.04599)) |
| No-call rate | n_nocall / n | trivial |
| Accuracy-at-coverage | accuracy on called subset vs coverage (curve + points at fixed coverages) | §5 recipe |

Decide on day one and hard-code: the F1 threshold is **0.5 on calibrated p**, or a per-drug
threshold tuned on grouped validation — but *state which*. AUROC/PR-AUC/Brier are threshold-free;
balanced accuracy/F1 are not. If the organizer's scorer uses a different convention, you want to
discover that from the brief, not from the leaderboard.

### 6.2 Harness plan (<1 day, ~300 lines, built BEFORE model tuning)

```
eval/
  groups.py      # edge list -> connected components -> group ids; leakage audit (max cross-split ANI)
  metrics.py     # compute_all(y, p, calls) -> dict(row per drug); ECE; reliability plot; RC curve
  conformal.py   # crepes wrapper: calibrate -> sets -> 3-way calls
  report.py      # per-drug table (markdown + csv) + figures/ (reliability, RC, cross-split ANI hist)
```

Hour-by-hour:
1. **(2h)** `groups.py` + audit. Input: skani edge list; output: `genome → group99.5, group99.9`,
   plus assertion "zero cross-split pairs ≥ τ" for any proposed split.
2. **(2h)** `metrics.py` on *called* vs *all* genomes; reliability figure; ECE. Unit-test with a
   perfect predictor and a coin-flip predictor (expect BA=1.0/ECE≈0 and BA≈0.5 respectively).
3. **(2h)** `conformal.py`: crepes class-conditional wrapper + sweep over confidence levels,
   emitting the no-call-rate/accuracy table per drug.
4. **(2h)** `report.py`: one command regenerates the whole results page from saved `p` arrays.
   Save raw probability arrays (`np.save`) for every model run — replotting must never require
   retraining.
- **Confidence intervals:** bootstrap over **groups** (resample group IDs, not genomes), 200
  iterations, report 95% CI on balanced accuracy and Brier. Point metrics on clustered data without
  group-aware CIs are overconfident — same leakage logic as the splitting itself.

**Skip:** dashboard-grade experiment tracking, multi-seed ensembling infrastructure, hyperparameter
frameworks. `np.save` + one CSV is the tracking system.

---

## 7. How grouped hidden-test generalization is typically scored

No public organizer script exists for this challenge (dataset drops at event start), so infer from
the closest precedents:

- **AMR benchmarks score per species–antibiotic combination, then aggregate.** The hzi-bifo
  benchmark ([PMC11070729](https://pmc.ncbi.nlm.nih.gov/articles/PMC11070729/)) computes metrics per
  dataset per fold, prioritizes **F1-macro**, and adds susceptible-class precision/F1 as the
  "clinically oriented" view. Expect the same shape here: per-drug metrics → macro-average over the
  3–5 drugs; susceptible-class errors (false "likely to work") likely weighted in narrative judging
  even if not in the numeric score.
- **The splits are precomputed and fixed** (their Table-2-style comparisons all used "the same three
  predefined partitions for every method"). So hidden-test generalization = a single frozen
  evaluation, not a resampling exercise. Your job is to match their metric definitions exactly and
  to not peek: any threshold/α selection must come from train/calibration only.
- **Clade-holdout is the canonical "unseen groups" design** in this literature
  ([PLoS Biol 2025](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539)),
  consistent with the brief's "hidden test set includes unseen groups". Assume worst-case shift:
  calibration behavior on the hidden set will be somewhat worse than on your grouped validation —
  leave margin in your α choice.
- **No-call scoring:** the brief pairs "no-call rate vs accuracy-at-coverage", i.e. they most
  plausibly compute accuracy on called genomes and report/curve it against the no-call rate (§5).
  Two failure modes to avoid: (a) no-calling everything hard → tiny called set → high accuracy,
  embarrassing no-call rate; (b) the degenerate opposite. A mid-range operating point with a clean
  RC curve beats both.
- **Practical hedges:** (i) submit probabilities for *every* genome (Brier/AUROC/PR-AUC computable
  no matter how they handle no-calls); (ii) make the 3-way call rule a pure function of
  `(p, threshold, band)` so you can regenerate calls under any scoring convention in minutes;
  (iii) re-read the metric section of the brief at event start and diff it against `metrics.py`
  before any modeling.

---

## Self-roast

1. **The de-dup machinery may be solving the organizer's problem, not yours.** Train/calibration/
   hidden-test splits are *given* and fixed. If their splits are already clean, my entire §1–2
   apparatus reduces to one audit plot plus within-train de-dup — and if their splits are leaky,
   you can't change them anyway; you'd just be documenting their leak. Worse, if the species is
   clonal (e.g. *M. tuberculosis*), the 99.5% ANI grouping degenerates into one mega-cluster and the
   whole scheme needs the SNP-phylogeny fallback I hand-waved. Risk: burning 4+ hackathon hours on
   clustering infrastructure whose only deliverable is a histogram.
2. **The conformal layer could be ceremony over a margin threshold.** In binary, class-conditional
   split-conformal literally *is* two band edges per class — a tuned margin on calibrated
   probabilities produces the same object, is easier to debug at 3 a.m., and avoids the
   exchangeability caveat being thrown back at us by a sharp judge ("your 90% guarantee doesn't hold
   on unseen lineages, does it?"). The conformal framing earns its keep only if we actually present
   the per-class guarantee and empirically validate it on grouped folds; as a silent implementation
   detail it adds a dependency and an API (crepes, or MAPIE's just-rewritten v1) for nothing.
3. **Every quantitative recommendation here is a prior, and the data may violate all of them.**
   α=0.10, the sigmoid-over-isotonic default, the 99.5% threshold, the 10–25% no-call expectation —
   all extrapolate from datasets and class balances we haven't seen. A tiny calibration split
   (~100–300 genomes, grouped, so maybe ~30 effective independent clusters) makes the conformal
   quantile itself noisy: with ~30 clusters the coverage guarantee has cluster-level granularity,
   and per-class Mondrian quantiles could rest on a handful of resistant genomes. The honest
   deliverable is the harness that *measures* all of this on grouped validation — if the team
   treats any number in this report as ground truth instead of as a hypothesis to re-measure on
   event day, this document has failed at its only job.
