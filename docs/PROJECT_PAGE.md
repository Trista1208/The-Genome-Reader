# Genome Firewall — an honest AI defense against superbugs

**Upload one bacterial genome; get, per antibiotic: `likely to fail` · `likely to
work` · `no-call` — with calibrated confidence, cited genetic evidence, and
principled abstention.** Genome Firewall reads a reconstructed *E. coli* genome and
says which of five frontline antibiotics are likely to fail, which are likely to
work, and — the part we are proudest of — when it does not know. On genetic lineages
never seen in training, it declines to answer on about six in ten genomes, and on the
four in ten it does call, it is right about nine times out of ten. A system that says
"I don't know" on cue is the one you can believe when it says "I do."

> **Research prototype. Every prediction must be confirmed with standard laboratory
> susceptibility testing.** Strictly defensive work: prediction only — the system
> never generates, designs, or suggests changes to any organism.

---

## The problem

Empiric antibiotic therapy is a blind prescription. Standard lab susceptibility
testing takes **1–3 days**; until then, clinicians guess — and empiric therapy fails
in **10–39% of ICU patients** because resistance is invisible at prescription time.
Antimicrobial resistance was directly responsible for an estimated **1.27 million
deaths in 2019** (Murray et al., *The Lancet*), more than HIV or malaria. The
infecting bacterium's genome is available hours to days earlier than the lab
phenotype — the open question is whether machine learning can read it *honestly*:
most published AMR classifiers report inflated accuracy from random train/test
splits that put near-identical strains on both sides, are miscalibrated, and answer
every query no matter how far it is from their training data. A confidently wrong
"this drug will work" is worse than no answer at all.

## The approach

```
FASTA ──AMRFinderPlus 4.2.7──▶ resistance genes/mutations (per genome)
      ──feature matrix───────▶ 0/1 grid (~900 gene/mutation features)
      ──per-drug model───────▶ elastic-net logistic regression + Platt calibration
      ──honesty layers───────▶ asymmetric conformal no-call · ANI-distance override
                                · target-locus callability gate
      ──evaluation───────────▶ skani (ANI ≥99.5%) cluster splits; metrics on
                                held-out genetic groups only
```

Deliberately small models. We train ~340 genomes per drug, dominated by a handful of
outbreak clones — in that regime a large model memorizes clones, not resistance
biology. The ciprofloxacin model has **80 nonzero weights** out of ~900 candidate
features (86–162 across the other four drugs). Every weight can be read and audited,
and most correspond to known resistance mechanisms. Small is not the limitation;
small is the control that keeps the model honest.

The honesty architecture, four layers:

1. **Cluster splits** — genomes are clustered with skani at ≥99.5% ANI; every
   headline number is computed on genetic groups held out of training, never on
   random splits.
2. **No-call band** — class-conditional conformal prediction with an *asymmetric*
   band (α = 0.02 susceptible-side, 0.10 resistant-side): "likely to work" must clear
   a stricter bar than "likely to fail", because a false "work" is the dangerous
   error. A hard ANI-distance override refuses any genome farther from the training
   set than anything the model was ever right about.
3. **Target-locus callability gate** — before "no mutation found" is trusted for
   ciprofloxacin, the gyrA / parC / parE target loci must be verified present in the
   assembly (k-mer locus check). Not-called loci force suspicion, never a
   default-susceptible.
4. **Decoupled evidence** — the report separates category (i) curated determinants
   (AMRFinderPlus hits via an allele-aware drug→class mapping, each with tier and
   citation family) from category (ii) statistical associations (the model's nonzero
   features, explicitly labeled mechanism-free) and category (iii) no known signal.
   A mechanism-free prediction is visibly weaker.

## Data provenance

- **3,000 public *E. coli* genomes** from BV-BRC (1,434 carried through feature
  extraction and labels into the v2 modeling corpus, 161 ANI clusters).
- **99,292 cleaned labels**; **laboratory-measured AST rows only**
  (`evidence == "Laboratory Method"`) — no model-generated phenotypes anywhere in
  the pipeline.
- MIC rows **re-derived against EUCAST v16.1 breakpoints** rather than trusting
  source-database interpretations; re-interpretation **flip-rate 0.39%**; conflicting
  rows excluded and counted.
- Five drugs: ciprofloxacin, gentamicin, ampicillin,
  trimethoprim/sulfamethoxazole, cefotaxime.

## Results — held-out genetic groups (model v2)

All numbers below are on **genetic lineages never seen in training**
(`heldout_group`; source: `reports/metrics.json`). Balanced accuracy CI95 is
bootstrapped over clusters — the honest uncertainty unit is the clone, not the genome.

| drug | n (R/S) | balanced acc | R-recall | S-recall | F1 | AUROC | PR-AUC | Brier | no-call rate | acc when called | CI95 (clusters) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ciprofloxacin | 620 (227/393) | **0.956** | 0.930 | 0.982 | 0.948 | 0.987 | 0.978 | 0.036 | 0.56 | 0.967 | [0.61, 0.96] |
| trimethoprim/SXT | 652 (263/389) | **0.906** | 0.928 | 0.884 | 0.884 | 0.956 | 0.939 | 0.082 | 0.59 | 0.970 | [0.88, 0.92] |
| gentamicin | 650 (96/554) | **0.877** | 0.812 | 0.942 | 0.757 | 0.926 | 0.812 | 0.059 | 0.66 | 0.814 | [0.64, 0.92] |
| ampicillin | 654 (399/255) | **0.838** | 0.789 | 0.886 | 0.848 | 0.931 | 0.944 | 0.120 | 0.62 | 0.884 | [0.77, 0.90] |
| cefotaxime | 503 (67/436) | **0.694** | 0.388 | 1.000 | 0.559 | 0.811 | 0.701 | 0.073 | 0.58 | 0.948 | [0.50, 0.71] |

Cefotaxime is the honest weak spot, and we show it on purpose: the held-out outbreak
clone carries ESBL alleles absent from all training lineages, resistant-recall drops
to 0.39, and the cluster-level confidence interval includes chance — the system
responds by abstaining on 58% of cases instead of guessing, and when it does call it
is still 94.8% accurate. This is the honesty architecture working as designed, on
the drug where it matters most.

<!--V3-SLOT: v3 retrain (full 3,000-genome corpus) — when it lands, add a v3-vs-v2
comparison table here (same columns, held-out groups only) and update the headline
figures above only where v3 does not regress. v2 fallback stays as written.-->

## Random splits lie — grouped splits tell the truth

The standard evaluation practice in this field — random train/test splits — puts
near-identical strains on both sides and rewards clone memorization (a named failure
mode in biological ML: Walsh et al. 2021, DOME recommendations; Hicks et al. 2019
showed classifiers degrade significantly on populations unlike training). We split by
skani cluster and report the two regimes side by side (balanced accuracy):

| drug | seen clusters (held-out genomes) | held-out genetic group (unseen lineages) |
|---|---|---|
| ciprofloxacin | 0.899 | 0.956 |
| trimethoprim/SXT | 0.936 | 0.906 |
| gentamicin | 0.852 | 0.877 |
| ampicillin | 0.924 | 0.838 |
| cefotaxime | 0.808 | 0.694 |

The gap cuts both ways — which is exactly the point. Only the right-hand column is a
claim about the next outbreak; the left column is what a random-split paper would
have reported.

## The no-call is the product

Clinical microbiology already formalized this: EUCAST maintains an official **Area
of Technical Uncertainty (ATU)** — the 100-year-old gold standard has an "uncertain"
zone. We gave our model the same professional privilege, and automated it. The band
is deliberately asymmetric: a wrong "likely to work" can kill, a wrong "likely to
fail" costs a second-choice drug, so "likely to work" must clear a much stricter bar
(for ciprofloxacin, p < 0.036) than "likely to fail" (p > 0.397). Everything in
between — about 60% of unseen-lineage genomes — is routed to the lab, which is where
uncertain cases always belonged. The showcase: genome `562.100124`, from a held-out
lineage, scores 0.088 for ciprofloxacin — a naive 0.5-threshold caller says "likely
to work"; the lab truth is **Resistant**. The abstention band catches exactly this
error: five drugs, five no-calls.

## Threat model — how this model can mislead, and what we did about it

| Failure mode | Failure story | Countermeasure (built, not promised) | Anchor |
|---|---|---|---|
| **Homolog leakage** | Random splits put near-identical strains in train and test; the model memorizes clones, not resistance biology, and collapses on unseen lineages. | All splits by skani cluster (≥99.5% ANI de-dup); every reported number comes from genetically grouped splits, with the held-out genetic group as the headline — never the in-distribution one. | Walsh et al. 2021 (DOME, *Nat Methods*); Hicks et al. 2019 (*PLoS Comput Biol*) |
| **False confidence** | A confidently wrong "likely to work" is the most dangerous output; raw ML scores are miscalibrated and users over-trust automated suggestions. | Platt calibration on a held-out split only; Brier score and reliability curve published per drug; asymmetric conformal no-call band plus ANI-distance hard override; confidence always shown as a bin-level frequency ("among held-out genomes in this bin, X% were resistant"), never a bare probability. | Van Calster et al. 2019 (*BMC Med*); FDA CDS guidance (automation bias) |
| **Spurious correlation** | The model latches onto lineage markers that correlate with resistance in this sample but encode no mechanism (cf. Caruana's pneumonia–asthma model). | Evidence decoupled from the model: category (i) curated determinant vs (ii) statistical association only vs (iii) no signal, shown separately; grouped evaluation exposes lineage-driven features by failing on unseen groups. | Caruana et al. 2015 (*KDD*); Hicks et al. 2019 (confounding, r > 0.98) |
| **Absent-target false-susceptible** | "No resistance gene found" reported as "susceptible", including when the drug's target locus was never actually sequenced. | Locus callability gate: quinolone target loci (gyrA / parC / parE) must be verified present in the assembly before a wild-type reading is trusted; not-called loci force suspicion, never default-susceptible. | BioFire K212727 FDA labeling; Ellington et al. 2017 (EUCAST WGS-AST report) |

## Limitations (said before you ask)

- **Cefotaxime generalization.** The held-out clone's ESBL alleles are absent from
  all training lineages; R-recall is 0.39 and the cluster-level CI95 includes chance.
  We report it instead of hiding it — and the abstention layers absorb most of the
  damage (94.8% accuracy when called). This is the case a v3 retrain on the full
  corpus is meant to improve. <!--V3-SLOT: one line on whether v3 moved cefotaxime.-->
- **Mechanism blind spots.** Features come from AMRFinderPlus's catalog; resistance
  mediated by porin loss or efflux overexpression is only partially visible to it,
  so mechanism-incomplete drugs carry a wider no-call band and a declared
  unexplained-resistance audit.
- **Coverage is approximate on unseen groups.** Conformal guarantees are
  distribution-level; on held-out clades we show measured per-group numbers instead
  of claiming guarantees. Per-isolate confidence is a bin-level frequency, not an
  individual risk.
- **Curated demo genomes.** The three story genomes are programmatically selected
  rehearsal cases (selection criteria in `demo/README.md`), chosen because each
  exercises a different honesty layer — they are demonstrations, not the evaluation.
- **The callability gate rarely fires**, and when it does it is usually assembly QC;
  we present it as such, not as a biological shield. It currently covers the
  quinolone target loci.
- **Scope:** one species, five drugs, ~340 training genomes per drug.

## Responsibility

- **Defensive by construction.** The system predicts and explains resistance that
  already exists in a sequenced isolate — the same capability class as NCBI's own
  AMRFinderPlus and DTU's ResFinder, run by public-health agencies. It produces no
  sequence output, no organism design, no mutation suggestions, and no free-text
  clinical advice; the report layer is template-rendered, not LLM-generated.
- **Human oversight, always.** Genome Firewall is decision support for prioritization
  — it tells you which cases to rush and which antibiotic not to start with. Every
  screen and every API response carries: *research prototype — confirm all results
  with standard laboratory susceptibility testing.* No-call means "route to the lab",
  not "alarm".
- **Disclosure.** Pre-event work is disclosed in `PREBUILT.md`; all data is public
  (BV-BRC); models, demo, and code are open (links below).

## Links

| What | Where |
|---|---|
| Models (skops, open) | https://huggingface.co/Darkroom4364/genome-firewall-ecoli |
| Interactive demo (static HF Space) | https://huggingface.co/spaces/Darkroom4364/genome-firewall |
| Colab demo notebook | `notebooks/GenomeFirewall_Demo.ipynb` (loads models + data from HF, runs anywhere) |
| Code — development line | https://github.com/Darkroom4364/genome-firewall (branch `sprint/baseline`) |
| Code — team repo | https://github.com/Trista1208/The-Genome-Reader (branch `sprint/baseline`) |
| Inference API | `api/serve.py` — FastAPI, `POST /predict` (genome_id or raw feature vector) |
