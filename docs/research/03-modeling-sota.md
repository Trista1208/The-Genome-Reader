# 03 — Modeling SOTA: whole-genome → AST prediction

Research memo for the **Genome Firewall** challenge (Hack-Nation × OpenAI × MIT Clubs, ~48 h).
Scope: published ML approaches, realistic performance per species/drug, simple-vs-deep, failure
modes, the 48 h stack, and whether k-mers can beat an AMRFinderPlus-feature baseline.
All claims sourced inline; every number annotated with the evaluation split type, because that
is the single biggest confounder in this literature.

---

## Executive verdict

**Build this (in priority order):**

1. **AMRFinderPlus gene/point-mutation features → per-drug L2-regularized logistic regression**,
   calibrated on the provided calibration split. This is the published-state floor and matches or
   beats deep models on tabular genomic features at our scale (1–3k genomes).
2. **Kover (Set Covering Machine) per drug** for ultra-sparse, interpretable k-mer rules — the
   top-ranked ML method in the largest neutral benchmark (78 species–antibiotic datasets), trains
   in minutes–hours with <8 GB RAM, and doubles as an evidence-citation engine for category (i)/(ii).
3. **LightGBM challenger on hashed 31-mer presence/absence** for the 1–2 drugs where the baseline
   is weakest — plus pyseer (LMM) on unitigs to convert "statistically associated k-mers" into
   defensible category-(ii) evidence.
4. **Grouped CV (Mash/MLST clusters) + a genomic nearest-neighbour baseline** to detect and
   quantify clonal leakage before it fools you.

**Ignore this:**

- Genomic language models (DNABERT-2, Nucleotide Transformer, HyenaDNA, Evo): no published
  WGS→AST advantage, wrong context scale (whole bacterial genome ≈5 Mb), and a 48 h budget
  with precomputed features. Fine-tuning a transformer here is how you lose the hackathon.
- Custom deep nets (CNN/MLP/autoencoder) on raw sequence — repeatedly shown to add ~nothing
  over LR/GBDT on this task at this n.
- MIC regression unless the organizer labels are actually MICs (binary S/I/R with a no-call
  layer is what is scored).

---

## 1. The method landscape (Q1)

### 1.1 k-mer rule-based learners — Kover (SCM / CART)

- **What:** Genomes → presence/absence of all 31-mers → Set Covering Machine learns a sparse
  conjunction/disjunction of k-mer presence/absence rules; CART variant learns small trees.
  `kover` (a.k.a. koverpy) is the Python implementation: https://github.com/aldro61/kover,
  docs https://aldro61.github.io/kover/.
- **Data needs:** Binary labels (it dropped "Intermediate" isolates), ≥~100 genomes/class
  preferred; works from FASTA (uses DSK counter) or a precomputed k-mer matrix. Original paper:
  17 datasets of 111–556 genomes, 10–123 M k-mers ([Drouin 2016, BMC Genomics 17:754](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-2889-6)).
- **Compute:** 33 s – 2 h training per dataset, **<8 GB RAM** (out-of-core HDF5 + popcount);
  bound-selection avoids 10-fold CV cost ([Drouin 2019, Sci Rep 9:4071](https://www.nature.com/articles/s41598-019-40561-2)).
- **Performance:** 107 datasets, 12 pathogens, 56 antibiotics from PATRIC — **95% of models >80%
  accuracy, 75% >90%, 45% >95%** (random 80/20 splits — leaky, see §4). Beat χ²-filtered
  CART/L1-SVM/L2-SVM and kernel SVMs on accuracy *and* sparsity; recovered katG-S315, rpoB-RRDR,
  rrs-A1401G, blaKPC, blaNDM-1 de novo ([Drouin 2016](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-2889-6), [Drouin 2019](https://www.nature.com/articles/s41598-019-40561-2)).
- **Benchmark position:** Top ML method in the largest neutral benchmark (78 datasets, 11
  species, 44 drugs, 31,195 genomes): best F1-macro in 30% of random-split cases and still best
  ML under phylogeny-aware (28%) and homology-aware (34%) splits ([Hu et al. 2024, Brief
  Bioinform 25:bbae206](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full); code:
  https://github.com/hzi-bifo/AMR_benchmarking).

### 1.2 k-mer + gradient boosting (XGBoost/LightGBM/AdaBoost)

- **What:** Davis et al. built AdaBoost classifiers on DNA k-mers at PATRIC (S. aureus
  methicillin AUC 0.991 / acc 99.5%, random CV) ([Davis 2016, Sci Rep 6:27930](https://www.nature.com/articles/srep27930); numbers as summarized in [this review](https://link.springer.com/article/10.1186/s42836-023-00195-2)).
  Nguyen/Davis then scaled XGBoost to MIC regression: K. pneumoniae 1,668 genomes, 20 drugs,
  10-mers, **92% accuracy within ±1 twofold dilution**; ciprofloxacin bACC 98.5%, VME 0.5%, ME
  2.5% ([Nguyen 2018, Sci Rep 8:421](https://www.nature.com/articles/s41598-017-18972-w), bACC as
  quoted by [Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349));
  Salmonella 5,278 genomes, 15 drugs, **95–96% within ±1 dilution** ([Nguyen 2019, JCM 57:e01260-18](https://www.biorxiv.org/content/10.1101/380782v2.full)).
- **Data needs:** 10³–10⁴ genomes with consistent AST; both studies used random 10-fold CV
  (leaky). Salmonella shows accuracy plateaus: 88.5% @250 genomes → 91.4% @1,000 → 95.2% @4,500
  diverse genomes — **~500 well-chosen diverse genomes already >90%**.
- **Compute warning:** the naïve "all 10-mer counts × all drugs" matrix needed **1.5 TB RAM**;
  they subsampled genomes to fit. For 1–3k genomes use *presence/absence of k=31* with
  singleton filtering + a univariate prefilter — fits in a laptop (see §5).

### 1.3 Pan-genome gene presence/absence + LR/SVM/GBDT

- Moradigaravand 2018 (1,936 E. coli, 11 drugs): **GBDT avg accuracy 0.91 (range 0.81–0.97),
  precision 0.92/recall 0.83 on random 20% holdout**; gene content was the dominant feature;
  population-structure-only model still 0.79 — proof that lineage itself is predictive (and a
  leakage vector) ([PLoS Comput Biol 14:e1006258](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258)).
- Hyun 2020 (288 S. aureus, 456 P. aeruginosa, 1,588 E. coli; 16 species–drug cases): SVM
  random-subspace ensembles on core-gene alleles + accessory genes; acc 79.3–99.5%, AUC
  0.79–1.0; detected 45 known AMR genes — and warned that "raw performance of an AMR-prediction
  model may have little to do with its capacity to learn real AMR mechanisms" ([PLoS Comput Biol
  16:e1007608](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007608)).
- Her & Wu 2018, E. coli pan-genome LR ([Bioinformatics 34:i89–95](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010018)).
- Pan-genome construction (Roary/panaroo) costs hours; AMRFinderPlus features give you the same
  "gene presence" signal for free in this challenge — skip de novo pan-genomes.

### 1.4 GWAS-style: pyseer / unitigs / DBGWAS

- **pyseer** ([Lees 2018, Bioinformatics 34:4310](https://pmc.ncbi.nlm.nih.gov/articles/PMC6289128/);
  docs https://pyseer.readthedocs.io/): fixed-effect or FaST-LMM association on k-mers/unitigs/
  SNPs/gene PAV with explicit population-structure correction (Mash distance MDS or kinship).
  Runtime ~2× the optimized C++ SEER; minutes–hours on 10³ genomes. Also ships whole-genome
  **elastic-net predictive models**. Canonical command:
  `pyseer --phenotypes pheno.tsv --kmers kmers.gz --distances structure.tsv --min-af 0.01 --max-af 0.99 --cpu 15 --filter-pvalue 1E-8`.
- **unitigs** ([Jaillard 2018, PLoS Genet 14:e1007758](https://pyseer.readthedocs.io/)) compress
  redundant k-mers into variable-length units — fewer correlated features, cleaner stats;
  `unitig-caller` (Bifrost) does this in minutes.
- DBGWAS ([Jaillard 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6289128/)) packages the same
  idea end-to-end. In a 48 h build, GWAS is your **category-(ii) evidence generator** (p-value +
  effect size per unitig), not the primary predictor.

### 1.5 Deep learning

- **DeepAMR** (13,403 MTB isolates, 16 countries; multi-task denoising autoencoder): mean AUROC
  **94.4–98.7%** across INH/EMB/RIF/PZA/MDR/PANS; best sensitivities INH 94.3%, EMB 91.5%, PZA
  87.3%, MDR 96.3% — **but for RIF and PANS the simple mutation-catalog baseline was better**
  (94.2% vs 94.9%; 92.2% vs 94.1%) ([Yang 2019, Bioinformatics 35:3240](https://pubmed.ncbi.nlm.nih.gov/30689732/)).
- CNNgwp/WDNN ([Green 2022, Nat Commun 13:3817](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10456961/));
  TB-DROP ([BMC Genomics 25:167](https://arxiv.org/html/2606.26179v1)); Kuang 2022 — traditional
  ML ≈ CNN for TB ([Sci Rep 12:2427](https://dpe.gospub.com/dpe/article/view/14));
  Aytan-Aktug 2021 — NN on partial genome alignments, no significant gain over ResFinder
  ([mSystems 6:e00185-21](https://www.dovepress.com/artificial-intelligence-for-antimicrobial-resistance-detection-and-pre-peer-reviewed-fulltext-article-IDR), as benchmarked by
  [Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).
- Verdict: DL wins only at 10⁴+ genomes with multi-task structure, and even then by ~1 AUROC point.

### 1.6 Genomic language models — compute/data reality check

| Model | Params | Context | Pretraining | Evidence for WGS→AST |
|---|---|---|---|---|
| DNABERT-2 | ~117 M | flexible (ALiBi), GUE inputs ≤10 kb | multi-species; ~92× less GPU time than NT | none published; GUE tasks are short regulatory elements ([arXiv:2306.15006](https://arxiv.org/abs/2306.15006)) |
| Nucleotide Transformer | 0.5–2.5 B | 6–12 kb | 3,202 human + 850 species genomes | none for AST; nearest is LoRA fine-tune to *classify AMR genes* (≤1 kb), not WGS→AST ([bioRxiv 2023.01.11.523679](https://www.biorxiv.org/content/10.1101/2023.01.11.523679v1), [ACL BioNLP 2025](https://preview.aclanthology.org/landing_page/2025.bionlp-1.pdf)) |
| HyenaDNA | ≤~40 M | up to 1 M nt | human reference only | none; even 1 M context is 5× too short for a 5 Mb genome ([arXiv:2306.15794](https://arxiv.org/abs/2306.15794)) |

Whole-genome AST would need chunking + pooling across ~5 Mb, which destroys the signal locality
that AMR prediction depends on and has zero published validation. **Do not build on these in 48 h.**

### 1.7 Method summary table

| Family | Exemplar | Min data | Compute (1–3k genomes) | Published perf (split!) | 48 h verdict |
|---|---|---|---|---|---|
| k-mer rules | Kover SCM | ~200 genomes | <8 GB RAM, min–h | 90–99% acc (random); top ML in 78-dataset benchmark | **Core** |
| k-mer GBM | Nguyen XGBoost | ~500 diverse | GBs RAM if hashed/prefiltered; 1.5 TB if naïve | 92–96% ±1 dilution (random) | **Core (challenger)** |
| Gene PAV + LR/GBDT | Moradigaravand | ~500 | minutes | 0.91 acc (random); 0.79 lineage-only | **Core (baseline)** |
| GWAS | pyseer LMM | ~500 | minutes–hours | evidence, not SOTA predictor | **Core (evidence)** |
| Catalog NN | Aytan-Aktug | ~1,000 | GPU helpful | ≈ ResFinder | Optional |
| Deep nets | DeepAMR et al. | ≥10⁴ | GPU hours | +≤1 AUROC vs rules | Skip |
| gLMs | DNABERT-2/NT/HyenaDNA | n/a | GPU days; wrong context scale | none for AST | **Skip** |

---

## 2. Realistic performance per species/drug (Q2) — mind the split

Random-split results in this field cluster at 0.90–0.99; **grouped/homology-aware evaluation cuts
the fraction of ≥0.9-F1 experiments by half to two-thirds** (64% → 33% phylogeny-aware → 25%
homology-aware; susceptible-class precision ≥0.95 in 47% → 39% → 30% of experiments)
([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)). Budget your
expected hidden-test scores accordingly.

| Species | Drug(s) | n | Model | Result | Split | Source |
|---|---|---|---|---|---|---|
| E. coli | 11 drugs | 1,936 | GBDT, pan-genome | acc 0.91 (0.81–0.97); P 0.92/R 0.83 | random 80/20 | [Moradigaravand 2018](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258) |
| E. coli | same | — | GBDT, population structure only | acc 0.79 | random | same |
| E. coli | same | — | GBDT, hold out ST131 | −0.28 acc vs random control | leave-lineage-out | same |
| E. coli | CIP/AMP/CTX | 1,509 (England) | SVM/LGB/RF on SNPs | CIP 0.87 acc → **0.50–0.57 on Africa data**; CTX 0.92 → 0.45; AMP held (0.94) | geographic external | [Nsubuga 2024, BMC Genomics 25:287](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-024-10214-4) |
| E. coli | CIP MIC | — | ML on curated+WG features | example of single-drug MIC regression | random | [Pataki 2020, Sci Rep 10:15026](https://www.medrxiv.org/content/10.1101/2024.05.15.24307162v1.full-text) |
| K. pneumoniae | 20 drugs | 1,668 | XGBoost 10-mer MIC | 92% within ±1 dilution; CIP bACC 98.5%, VME 0.5%, ME 2.5% | random 10-fold CV | [Nguyen 2018](https://www.nature.com/articles/s41598-017-18972-w) |
| K. pneumoniae | CIP | 331–378 | SCM/RF 31-mers | bACC significantly below gonococci; open pangenome hurts | random 2:1 | [Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349) |
| S. aureus | 12 drugs | 470 (val) | Mykrobe (rule-based de Bruijn) | **sens 99.1% / spec 99.6%** | independent validation | [Bradley 2015, Nat Commun 6:10063](https://pubmed.ncbi.nlm.nih.gov/26686880/) |
| S. aureus | methicillin | 606 | AdaBoost k-mers | AUC 0.991, acc 99.5% | random CV | [Davis 2016](https://www.nature.com/articles/srep27930) |
| S. aureus | 6 drugs | 288 | SVM-RSE pan-genome | acc up to 99.5%, AUC up to 1.0 | random 5-fold | [Hyun 2020](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007608) |
| N. gonorrhoeae | CIP | ~4,000 (7 datasets) | SCM/RF 31-mers | **bACC ≥93%** (gyrA-S91F alone: ≥98% sens, ≥99% spec) | random 2:1 | [Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349) |
| N. gonorrhoeae | AZM | same | same | **bACC 57–94%, wildly dataset-dependent** | random | same |
| N. gonorrhoeae | CFX/CIP/AZM MIC | 8,290 unitigs | RF/CatBoost regression | R² 0.75–0.79; recovered 23S rRNA/gyrA/penA | random 80/20 | [Yasir 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9280306/) |
| N. gonorrhoeae | 6 drugs MIC | 1,280 train | multivariate regression, curated determinants | validated on 1,095 Canadian + 431 international | external | [Demczuk 2020, AAC 64:e02005-19](https://pmc.ncbi.nlm.nih.gov/articles/PMC7038236/) |
| Salmonella | 15 drugs | 5,278 (≤4,500 used) | XGBoost 10-mer MIC | **95–96% within ±1 dilution**; ME ≤3% all drugs; VME within FDA limits for 7/15 | random 10-fold | [Nguyen 2019](https://www.biorxiv.org/content/10.1101/380782v2.full) |
| Salmonella | same | — | train ≤2014 → test 2015–16 | 86–92% (temporal decay ~5–9 pts) | time-split | same |
| M. tuberculosis | INH/RIF/EMB/PZA | 10,209 | rule-based catalog (9 genes) | **sens 97.1/97.5/94.6/91.3%; spec 99.0/98.8/93.6/96.8%**; full profile 89.5%; pansusceptible 97.9% | multicountry cohort | [CRyPTIC, NEJM 379:1403](https://pubmed.ncbi.nlm.nih.gov/30280646/) |
| M. tuberculosis | 4 first-line + MDR/PANS | 13,403 | DeepAMR | AUROC 94.4–98.7%; RIF/PANS sensitivity < catalog baseline | random CV | [Yang 2019](https://pubmed.ncbi.nlm.nih.gov/30689732/) |
| M. tuberculosis | multi-drug | 1,609 (val) | Mykrobe | sens 82.6% / spec 98.5% | independent | [Bradley 2015](https://pubmed.ncbi.nlm.nih.gov/26686880/) |
| M. tuberculosis | multi-drug | CRyPTIC VCF | XGBC/LGBC/GBC vs ANN | traditional ML competitive with ANN | random | [Kuang 2022](https://dpe.gospub.com/dpe/article/view/14) |
| 11 species | 44 drugs, 78 datasets | 31,195 | Kover / PhenotypeSeeker / Seq2Geno2Pheno / Aytan-Aktug / ResFinder | Kover top ML; **ResFinder best on divergent genomes (44–50%)**; β-lactams most variable (cefoxitin-S. aureus F1≥0.99 vs aztreonam-Kp 0.59) | random vs phylogeny vs homology | [Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full) |

**Reading the table for the challenge:** the organizer's hidden test includes *unseen groups* —
expect performance between the "phylogeny-aware" and "random" columns, i.e., **~0.8–0.95 balanced
accuracy for well-behaved species/drugs, and 0.6–0.8 for the hard ones** (macrolides with
breakpoint-hugging MICs, β-lactams with porin/efflux components, open-pangenome species).

---

## 3. Where simple models match deep ones (Q3)

Consistent finding across a decade of papers:

- **Fully-connected DNN ≈ logistic regression ≈ random forest** on pan-genome features
  (E. coli, 11 drugs): "deep learning models… did not provide substantial improvement over the
  simpler logistic regression models, or random forests"; GBDT won 11/11
  ([Moradigaravand 2018](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258)).
- **Rule-based Kover ≥ everything else** incl. logistic, SVM, NN-based Aytan-Aktug across 78
  datasets ([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).
- **DeepAMR ≈ mutation catalog**, and worse for 2/6 TB tasks ([Yang 2019](https://pubmed.ncbi.nlm.nih.gov/30689732/));
  traditional ML ≈ CNN on TB VCF data ([Kuang 2022](https://dpe.gospub.com/dpe/article/view/14)).
- RF/CNN only marginally > LR/SVM on SNP encodings (AUC ≤0.96, E. coli) ([Ren 2022, Bioinformatics 38:325](https://pubmed.ncbi.nlm.nih.gov/34613360/)).

**Why:** the signal is sparse, high-SNR, and mostly additive (one gene/mutation → phenotype);
n ≤ a few thousand ⇒ deep nets' capacity buys nothing and costs variance. Deep nets pull ahead
only with ≥10⁴ samples and multi-task/co-resistance structure (DeepAMR) — and even then by ~1
AUROC point. **There is no published evidence of a gLM beating a k-mer GBM for WGS→AST.**

---

## 4. Known failure modes (Q4) — the threat model, with receipts

1. **Population-structure confounding / lineage-as-predictor.** Models happily learn clade
   markers instead of resistance: structure-only features reached 0.79 accuracy
   ([Moradigaravand 2018](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258));
   across 24k genomes × 5 species, LightGBM trained on clade-confounded data collapsed and
   **more data did not rescue it**; predictive features barely overlapped between clades
   ([Yu, Wheeler & Barquist 2025, PLoS Biol 23:e3003539](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539);
   code https://github.com/BarquistLab/AMR_prediction). GWAS literature: lineage effects are the
   canonical confounder ([Earle 2016, Nat Microbiol 1:16041](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539);
   [Power & Parkhill 2017, Nat Rev Genet 18:41](https://pmc.ncbi.nlm.nih.gov/articles/PMC7002396/));
   feature-weighted models to remove lineage dependency ([Billows 2023, Bioinformatics 39:btad428](https://www.nature.com/articles/s41598-024-77947-w)).
2. **Clonal leakage in random splits.** Random CV puts near-identical genomes in train and test,
   inflating scores: F1≥0.9 in 64% (random) vs 33% (phylogeny-aware) vs 25% (homology-aware) of
   experiments ([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full));
   ST131 holdout −0.28 accuracy ([Moradigaravand](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258));
   England→Africa collapse to ~0.5 ([Nsubuga 2024](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-024-10214-4)).
   Nearly all the shiny 0.95+ numbers in §2 are random-split. Treat them as upper bounds.
3. **Label noise.** MICs are reproducible to ~±1 twofold dilution; isolates near the breakpoint
   are effectively unclassifiable — gonococcal AZM (MICs hugging the breakpoint) scored 57–94%
   bACC across datasets vs ≥93% for the bimodal CIP; removing near-breakpoint strains helped but
   didn't close the gap ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349)).
   MIC testing method varies between labs/datasets — an unfixable confounder; genotypic
   "errors" are often phenotyping errors ([Moradigaravand](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258);
   review [Kim 2022, Clin Microbiol Rev 35:e00179-21](https://www.mdpi.com/2813-9054/70/2/14)).
4. **Class imbalance.** Model sensitivity:specificity ratio tracks the NS:S ratio in training
   data (Pearson r>0.98) ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349));
   VME rates blow past FDA limits when resistant genomes are scarce ([Nguyen 2019](https://www.biorxiv.org/content/10.1101/380782v2.full)).
   Use balanced accuracy / macro-F1 as the tuning objective, and consider per-drug
   class-weighting — exactly what the challenge's metrics reward.
5. **S/I/R binarization choices.** "Intermediate" is partly label noise: Kover 2.0's 3-class
   models predicted S and R well but I was systematically mispredicted — the I breakpoint sits
   within ±1 dilution of both neighbors, i.e., inside assay noise
   ([Drouin 2019](https://www.nature.com/articles/s41598-019-40561-2)). Hu 2024 dropped I
   entirely; Moradigaravand folded I into R. **Recommendation: fold I into the no-call class if
   the organizer labels allow; otherwise into R (conservative for the molecular gate).**
6. **Breakpoint choice / metric choice.** AZM classifiers scored significantly better under CLSI
   than EUCAST breakpoints (two dilutions apart); binary S/NS classifiers beat MIC regressors on
   categorical accuracy ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349)).
7. **Mechanism diversity / open pangenomes.** Performance decays with genomic diversity
   (gonococci > K. pneumoniae > A. baumannii for the same drug) ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349));
   β-lactams most variable across species (porin/efflux/PBP multiplicity) ([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).
8. **Co-resistance spurious correlation.** Kover's streptomycin model initially learned katG/
   rpoB (INH/RIF determinants) because 95.6% of streptomycin-tested isolates shared INH labels
   ([Drouin 2016](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-2889-6)).
   Multi-drug panels share resistance cassettes — per-drug evidence must be annotated back to
   mechanism or it will cite the wrong gene.
9. **Shortcut learning via correlated metadata.** Year-of-isolation was selected by best models
   for 10/11 drugs — pure sampling artifact ([Moradigaravand](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258)).
   Never feed metadata (year, source, ST) as features.

---

## 5. The ambitious-but-feasible 48 h stack (Q5)

Assumes the organizer ships FASTA + precomputed AMRFinderPlus results + grouped
train/calibration splits, 1–3k genomes, 3–5 drugs.

**Tier 0 — hour 0–6 (the floor; must exist before anything clever):**
- Parse AMRFinderPlus output → binary matrix: AMR gene presence + called point mutations
  (~50–500 features). Also derive the molecular-target-presence flags for the gate.
- Grouping: `mash sketch -s 10000 *.fasta` → pairwise ANI → cluster at ~99.9% (near-duplicate
  de-dup, as required) and at ~95–99% (GroupKFold groups). Mash: O(minutes).
- Per drug: `LogisticRegression(class_weight='balanced', C=small)` with probability output;
  isotonic/Platt calibration on the calibration split. Tune C by **grouped** CV only.
- Metrics harness first (per plan): balanced acc, macro-F1, AUROC, PR-AUC, Brier, reliability,
  coverage-vs-accuracy.
- **Nearest-neighbour sanity baseline:** predict each genome by its closest training neighbour's
  label (Mash distance). If LR ≈ NN, your model is reading phylogeny, not mechanism
  (neighbour-typing idea: [Břinda 2020, Nat Microbiol 5:455](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539);
  recommended as a standard baseline by [Yu 2025](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003539)).

**Tier 1 — hour 6–18 (interpretable + evidence):**
- **Kover SCM per drug** on the training genomes (k=31). Sparse rules → annotate rule k-mers by
  BLAST against the AMRFinderPlus DB → category-(i) confirmation or category-(ii) candidate.
  Runtime: minutes–2 h/drug, <8 GB RAM ([Drouin 2016](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-016-2889-6)).
- **pyseer LMM on unitigs** (unitig-caller → pyseer with Mash-distance MDS correction) per drug
  → statistically-associated variants with p-values/effect sizes = your category-(ii) evidence
  table. Minutes–hours ([pyseer docs](https://pyseer.readthedocs.io/en/latest/usage.html)).

**Tier 2 — hour 18–36 (only if Tier 0/1 are green):**
- **Hashed 31-mer presence matrix** (KMC3 per genome, drop singletons, univariate χ² or pyseer
  prefilter to ~10⁵–10⁶ features; 3k×1M×1 B ≈ 3 GB) → **LightGBM** with `scale_pos_weight`,
  tuned by grouped CV. Compare to LR per drug; keep it **only for drugs where it wins under
  grouped CV** (expect gains mainly where catalogs are thin: macrolides, some β-lactams).
- Conformal no-call layer + evidence-citation report writer (other workstreams).

**Explicitly not:** de novo pan-genome building (Roary), MIC regression, deep nets, gLMs,
multi-species models ([LOSO cross-species transfer fails catastrophically](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).

**Why this is feasible:** every component is CPU-only, pip-installable, and has published
runtimes ≤ hours at 10³-genome scale; the heaviest step (k-mer counting 3k genomes with KMC3)
is ~minutes–tens of minutes on a modern laptop.

---

## 6. Can k-mers beat an AMRFinderPlus-feature baseline? (Q6)

**Short answer: matching it is easy; beating it is drug-specific and smaller than random-split
literature suggests. The honest expected value of the k-mer stream is evidence discovery
(category ii) and a few AUROC points on under-cataloged drugs — not a uniform win.**

Evidence *for* k-mer models winning:
- ML (Kover et al.) beat the catalog method ResFinder in 64% vs 17% of 78 datasets **under
  random splits** ([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).
- k-mer models recover known determinants *and* exploit correlated loci, reducing false
  negatives where the catalog is incomplete (E. coli: ML beat ResFinder/CARD rules on 10/11
  drugs, [Moradigaravand](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006258);
  Salmonella top k-mers = known AMR genes + novel regions, [Nguyen 2019](https://www.biorxiv.org/content/10.1101/380782v2.full)).

Evidence *against / caveats*:
- **On divergent genomes the catalog wins:** ResFinder best in 44% (phylogeny-aware) and 50%
  (homology-aware) of datasets vs Kover's 28%/34% ([Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).
  The hidden test has *unseen groups* — i.e., exactly the regime where the k-mer advantage
  shrinks and the curated-catalog generalization advantage appears.
- For mechanism-saturated drugs the ceiling is already hit: S. aureus 12-drug sens/spec
  99.1/99.6% rule-based ([Bradley 2015](https://pubmed.ncbi.nlm.nih.gov/26686880/));
  gonococcal CIP via one SNP ≥98%/≥99% ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349));
  TB first-line sens 91–97.5% ([CRyPTIC](https://pubmed.ncbi.nlm.nih.gov/30280646/));
  AMRFinderPlus itself validated at high genotype–phenotype concordance
  ([Feldgarden 2019, AAC 63:e00483-19](https://research.usc.edu.au/view/pdfCoverPage?instCode=61USC_INST&filePid=13172272360002621&download=true)).
  No k-mer model will add more than noise there.
- k-mer gains concentrate where catalogs are thin (AZM, β-lactams with regulatory/porin
  components) — which is also where labels are noisiest and grouped generalization is weakest
  ([Hicks 2019](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007349), [Hu 2024](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full)).

**What it would take to actually beat the baseline:**
1. Prove it per drug under **grouped CV** (not random) — if it doesn't win there, it won't win
   on the hidden groups.
2. Homology-aware feature handling: equivalent k-mers (same locus) must be grouped/weighted so
   the model can't split credit across thousands of collinear features (Kover's equivalent-rule
   grouping does this natively; unitigs help).
3. Annotate surviving k-mers back to genes/loci (BLAST vs AMR DB + whole reference) — turns
   "novel signal" into defensible category-(ii) evidence and catches co-resistance artifacts.
4. Restrict the k-mer challenger to drugs where baseline grouped-CV AUROC < ~0.95.

**Predicted outcome:** +0–3 AUROC points over the LR baseline for catalog-saturated drugs,
potentially +5–15 for thin-catalog drugs, *if* grouped evaluation confirms it; the k-mer
stream's guaranteed deliverable is the evidence table, not the score bump.

---

## Self-roast

1. **My evidence base is biased toward PATRIC/BV-BRC and may not transfer to the organizer's
   dataset.** The headline benchmarks (Hu 2024, Kover papers, Davis, Nguyen) all trained on
   PATRIC-scale, surveillance-biased collections. The challenge dataset is 1–3k genomes of one
   species with curated splits — smaller n pushes even harder toward the trivial baseline
   (Kover/pyseer may add ~nothing over LR on 500 genomes), and if the organizers pre-cleaned
   population structure, the leakage-driven panic in §4 is partly moot. My "expect 0.8–0.95"
   numbers could be off in either direction by 5–10 points.
2. **"Skip genomic LMs and deep learning" could leave points on the table.** The judging rewards
   per-drug F1/AUROC, and some resistance signal lives in regulatory/non-coding context that
   gene-presence features miss entirely; a LoRA fine-tune of DNABERT-2 over a handful of loci is
   a half-day job for a competent teammate and 2025-era tooling makes it cheap. If one drug in
   the panel has thin catalogs and regulatory-driven resistance (the classic AZM case), a
   sequence model might be the only thing that beats no-call. I recommended against it on
   time-risk grounds, not on evidence that it fails.
3. **The recommended stack is itself over-scoped for 48 h.** Tier 2 (KMC3 → hashed matrix →
   LightGBM → k-mer annotation) is a pipeline with ~5 failure points, each capable of eating
   half a day (RAM blowups, k-mer counting edge cases on draft assemblies, annotation
   ambiguity). The realistic outcome of attempting it is a distracted team and an
   under-validated Tier 0/1. A defensible counter-strategy to my own plan: ship only Tier 0+1,
   and spend the saved time on calibration, the no-call layer, and the demo — the things judges
   actually score.
