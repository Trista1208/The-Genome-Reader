# 01 — Data Landscape: Genome Firewall

**Agent scope:** which public data to train on, label-quality traps, what the organizer dataset probably is, exact pull mechanics, fallbacks/licensing.
**Method note:** all per-species/per-drug counts below were measured live against the BV-BRC data API on 2026-07-18 (queries included so you can re-run them the morning of the event). Nothing here is from memory alone.

---

## TL;DR — build this / ignore this

**Build this (before the event):**
1. A **BV-BRC pull script** that grabs (a) all `evidence=Laboratory Method` AMR labels for *E. coli*, *K. pneumoniae*, *S. enterica*, *N. gonorrhoeae*, *S. aureus* as CSV, and (b) the matching `.fna` genomes for the top ~3–5k genomes of the two most likely species (E. coli + one backup). Everything is anonymous, no auth, verified working today.
2. A **label-cleaning module**: drop `Computational Method` rows, normalize antibiotic-name variants (misspellings like `tigecyklin` exist), resolve multiple rows per genome×drug, binarize S/I/R with an explicit I-policy, record `testing_standard` + year.
3. A **genome QC filter** using BV-BRC metadata fields (`genome_quality`, `checkm_completeness`, `checkm_contamination`, `contigs`, `genome_length`) — mirrors what published benchmarks did.
4. Optional insurance: download the **Hu et al. benchmark datasets** (78 species×drug datasets with homology/phylogeny splits already made, Mendeley Data) — closest existing thing to the organizer's format.

**Ignore this:** MGnify (metagenomes, no isolate AST), NDARO/CARD/ResFinder as *label* sources (they are gene catalogs — features, not phenotypes), the BV-BRC "Computational Method" phenotype rows (model-generated, roughly half the DB), raw SRA reads (assembly burns hours; use BV-BRC's assembled `.fna`).

---

## 1. Species with the best WGS + lab-AST coverage

### 1.1 Headline numbers (verified via BV-BRC API, 2026-07-18)

"Lab-AST rows" = records in the `genome_amr` collection with `evidence=Laboratory Method` (one row per genome×antibiotic measurement). "Unique genomes w/ AST" = distinct `genome_id`s among those rows (counted by full paging + `sort -u`, not estimated).

| Species (taxon_id) | Public genomes in BV-BRC | Lab-AST rows | Unique genomes w/ lab AST | Top antibiotics by lab-label count |
|---|---|---|---|---|
| *E. coli* (562) | 118,168 | 243,124 | **12,627** | ciprofloxacin 15.8k, ceftazidime 15.2k, pip/tazobactam 14.0k, cefotaxime 13.9k, gentamicin 13.3k, meropenem 13.0k, ampicillin 11.9k, cefuroxime 11.6k, SXT 10.7k |
| *M. tuberculosis* (1773) | 46,764 | 212,555 | **27,902** | isoniazid 25.8k, rifampin 25.3k, ethambutol 22.4k, amikacin 13.8k, kanamycin 13.1k, rifabutin 12.0k, ethionamide 11.6k, pyrazinamide 10.6k, moxifloxacin 10.5k, bedaquiline 10.1k |
| *N. gonorrhoeae* (485) | 15,004 | 72,933 | **10,260** | azithromycin 16.4k, ceftriaxone 13.8k, ciprofloxacin 12.4k, cefixime 10.4k, penicillin 7.1k, tetracycline 5.5k, spectinomycin 4.6k |
| *K. pneumoniae* (573) | 42,829 | 85,291 | **7,276** | meropenem 6.2k, gentamicin 4.9k, ciprofloxacin 4.9k, ceftazidime 4.4k, amikacin 3.9k, SXT 3.8k, ampicillin 3.4k |
| *S. aureus* (1280) | 29,360 | 45,876 | **4,859** | ciprofloxacin 3.7k, gentamicin 3.6k, erythromycin 3.6k, tetracycline 3.3k, vancomycin 2.9k, penicillin 2.5k, cefoxitin 2.3k, oxacillin 2.2k |
| *S. enterica* (28901) | 43,005 | 63,198 | **4,678** | ampicillin 4.7k, ciprofloxacin 4.7k, gentamicin 4.5k, tetracycline 4.5k, chloramphenicol 4.5k, azithromycin 4.4k, streptomycin 4.1k |
| *P. aeruginosa* (287) | 16,369 | 11,121 | **1,421** | meropenem 1.5k, ceftazidime 1.3k, ciprofloxacin 1.2k, tobramycin 1.1k, amikacin 0.7k |

Reproduce with:
```bash
# total genomes (public) per species — total is in the Content-Range response header
curl -s -D - -o /dev/null "https://www.bv-brc.org/api/genome/?eq(taxon_lineage_ids,562)&eq(public,true)&limit(1)" | grep -i content-range
# per-drug lab-AST counts — facet counts come back in the facet_counts RESPONSE HEADER
curl -s -D - -o /dev/null "https://www.bv-brc.org/api/genome_amr/?eq(taxon_id,562)&eq(evidence,Laboratory%20Method)&facet((field,antibiotic),(mincount,200),(limit,60))&limit(0)" | grep -i facet_counts
```
API base: `https://www.bv-brc.org/api/{collection}` — docs: [BV-BRC docs hub](https://www.bv-brc.org/docs/) (RQL query syntax, `eq/ne/gt/and/or`, `select()`, `sort()`, `limit(n,offset)`; page cap 25,000 rows; `Accept: text/csv` gives CSV).

Context figures from literature: BV-BRC held lab-derived AST for **67,000 genomes (~40 genera, >100 species) in 2022** ([Olson et al., NAR 2023, PMC9825582](https://pmc.ncbi.nlm.nih.gov/articles/PMC9825582/)) and **90,829 genomes by early 2025** ([preprints.org review 202504.2464](https://www.preprints.org/manuscript/202504.2464/v1/download)); the 7 species above alone account for ~63k unique genomes today, so coverage keeps growing. Curation methods: [Wattam et al. 2023 chapter](http://www.iq.usp.br/setubal/bmc/2023/cap2.pdf).

### 1.2 Ready-made benchmark datasets (use as dress rehearsal)

- **Hu et al. 2024 (McHardy lab)** — the single most relevant prior benchmark: **78 species×antibiotic PATRIC datasets, 11 species, 44 drugs, 31,195 genomes after QC** (per-dataset 200–13,500 genomes; ≥100 genomes per class), evaluated with **random / phylogeny-aware / homology-aware splits** — i.e. exactly the "genetically grouped splits" the organizers promise. E. coli multi-drug set: 2,493 genomes × up to 13 drugs. [bioRxiv 2024.01.31.578169](https://www.biorxiv.org/content/10.1101/2024.01.31.578169v1.full.pdf) · datasets: [Mendeley Data doi:10.17632/6vc2msmsxi.1](https://data.mendeley.com/datasets/6vc2msmsxi/1) · code: [github.com/hzi-bifo/AMR_benchmarking_khu](https://github.com/hzi-bifo/AMR_benchmarking_khu)
- **Arcadia Science 2025 E. coli set** — 6,983 E. coli strains × 50 antibiotics from BV-BRC + SRA; gentamicin deepest (6,043 strains); ships phenotype matrix + accessions on Zenodo. [pub](https://research.arcadiascience.com/pub/dataset-ecoli-amr-genotype-phenotype/release/3/) · [Zenodo 10.5281/zenodo.12692732](https://doi.org/10.5281/zenodo.12692732)
- **CRyPTIC (TB only)** — 12,289 MTB isolates with quantitative MICs for 13 drugs + reads in ENA. [PLOS Biol 2022 data compendium e3001721](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001721) · [GWAS paper e3001755, 10,228 genomes](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001755)

**Read on the table:** E. coli is the safest species to prep (deepest genome pool AND deepest label pool: ~19 lab rows/genome). N. gonorrhoeae has the best *per-genome panel completeness* (~7 drugs on 10.3k of its 15k genomes, uniform CDC panels). K. pneumoniae, S. aureus, S. enterica are workable. P. aeruginosa is thin (1,421 genomes — a 1–3k-genome challenge set could barely be built). MTB has the most genomes with labels (27.9k) but it's a different problem (no plasmid-borne acquired genes; resistance = chromosomal SNPs; AMRFinderPlus barely applies; MIC plates, not S/I/R panels).

---

## 2. Label-quality traps (all verified against live data)

1. **Model-generated phenotypes are mixed into the same table.** Every `genome_amr` row has an `evidence` field: `"Laboratory Method"` vs `"Computational Method"`. Computational rows are PATRIC's own ML classifiers — they literally carry fields like `"computational_method":"AdaBoost Classifier"` and `"computational_method_performance":"Accuracy:0.931, F1 score:0.935, AUC:0.950"` (observed live). Training on these = fitting a model to another model's output. **Filter `eq(evidence,Laboratory Method)` everywhere.** These classifiers are from [Davis et al., Sci Rep 2016](https://www.nature.com/articles/srep27930) / [PATRIC NAR 2020, doi:10.1093/nar/gkz943](https://doi.org/10.1093/nar/gkz943).
2. **Antibiotic names are not normalized.** Facet counts expose spelling variants as separate buckets: `tigecycline` 8,314 **and** `tigecyklin` 2,448 (E. coli); `amoxicillin/clavulanic acid` vs `amoxicillin_clavulanat`; `tetracycline` vs `tetracyklin`; `sulfisoxazole`/`sulfonamides`/`sulfa`. Worst: Klebsiella has a bucket literally named `extended spectrum beta lactamase` (451 rows) — that's a *phenotype*, not a drug. Build a synonym map keyed to the organizer's drug list; treat unknown buckets as untrusted.
3. **S/I/R and MIC coexist.** Rows carry `resistant_phenotype` (Susceptible/Intermediate/Resistant) **and** `measurement`/`measurement_sign`/`measurement_value`/`measurement_unit` (MIC in mg/L), plus `laboratory_typing_method` (observed: `MIC`, `Disk diffusion`, …) and `vendor` (e.g. Oxoid). Disk-diffusion zone diameters and MICs are not interchangeable; where only S/I/R is given, you cannot re-derive MIC.
4. **Breakpoints drift.** Rows carry `testing_standard` (CLSI / EUCAST) and `testing_standard_year` (observed: 2021). The same MIC flips S↔R across years and standards; EUCAST also redefined "I" in 2019 ([EUCAST clinical breakpoints](https://www.eucast.org/clinical_breakpoints)). Mixed-era labels are silent label noise; for calibration, consider restricting to one standard or flagging pre-2019 I's.
5. **Duplicate / conflicting rows per genome×drug.** Rows outnumber unique genomes ~7–19× per species because (a) genomes have panels of drugs and (b) the same genome×drug can appear multiple times from different PMID sources (e.g. NARMS + a paper), occasionally with conflicting calls. Decide a deterministic resolver pre-event (prefer MIC over disk, then newer standard, then majority vote; log conflicts).
6. **NCBI's AST browser is submitter-supplied and unvetted.** NCBI's own docs: *"The phenotype data displayed in this interface is supplied by submitters into the BioSample database… NCBI staff do not vet the methods used or values supplied"* ([NCBI AST HowTo PDF](https://www.ncbi.nlm.nih.gov/core/assets/pathogens/files/HowTo/FindIMIresisbasedonMICv2.pdf)). Same caution for NARMS Now downloads, which now include **WGS-predicted** resistance columns next to measured ones — don't merge them blindly ([CDC NARMS Now notes](https://stacks.cdc.gov/view/cdc/58082/cdc_58082_DS1.pdf)).
7. **Query by `taxon_id`, not by name.** The `genome_amr` collection has **no `species` field** (querying it errors out — verified). Use numeric taxon IDs (table in §1.1); name-based queries would silently mix in Shigella-as-E. coli etc.
8. **Genome-side traps:** duplicate submissions of the same isolate (GenBank + RefSeq copies), plasmid-only "genomes", contaminated assemblies. The `genome` collection gives you the filters for free: `genome_quality`, `genome_status` (Complete/WGS), `contigs`, `contig_n50`, `genome_length`, `checkm_completeness`, `checkm_contamination`, `fine_consistency`, `coarse_consistency`, plus `assembly_accession`, `biosample_accession`, `mlst`, `collection_year`, `isolation_country` (full field list verified live). Hu et al. excluded plasmid-only sequences and filtered on exactly these quality fields.
9. **Surveillance bias:** resistant isolates are over-sequenced in most collections; class balance in BV-BRC ≠ clinical prevalence. Fine for training, but your *calibration* prior should come from the organizer's calibration split, not from train.

---

## 3. What the organizer dataset most plausibly is

Constraints from the brief: one species, 1–3k genomes, 3–5 antibiotics, grouped train/calibration/hidden-test splits, "possibly precomputed AMRFinderPlus results".

Ranked guess:

1. **E. coli (~65% likely).** Default organism for every prior AMR-ML benchmark (Hu et al.'s largest sets; Arcadia's 6,983-strain set; PATRIC classifiers). A 1–3k-genome QC'd subset with 3–5 drugs is trivially assembled from the top-count drugs: **ciprofloxacin, gentamicin, ampicillin, trimethoprim/sulfamethoxazole, cefotaxime (or ceftazidime/meropenem)**. AMRFinderPlus has an E. coli/Shigella point-mutation panel, matching the "precomputed AMRFinderPlus" hint ([AMRFinderPlus wiki](https://github.com/ncbi/amr/wiki)).
2. **K. pneumoniae (~15%).** Second-deepest Enterobacterales label pool; drugs would be meropenem/ciprofloxacin/gentamicin/ceftazidime/SXT. Carbapenem-resistance prediction is a compelling "firewall" narrative.
3. **N. gonorrhoeae (~10%).** Uniform CDC panels give azithromycin/ceftriaxone/ciprofloxacin/cefixime/penicillin on nearly every genome — cleanest multi-drug label matrix of all candidates; WHO priority pathogen; AMRFinderPlus point-mutation panel exists.
4. **S. enterica (~7%).** NARMS-labeled (ampicillin/ciprofloxacin/gentamicin/tetracycline/azithromycin), AMRFinderPlus-ready, but serovar structure makes "one species" messy.
5. **M. tuberculosis or S. aureus (~3%).** MTB: biggest label pool but MIC-based, SNP-driven biology, AMRFinderPlus mostly irrelevant — contradicts the hints. S. aureus: workable, but cefoxitin/oxacillin≈mecA makes one drug almost trivially separable and vancomycin resistance is nearly absent (class-balance nightmare).
6. **P. aeruginosa — tail risk worth 30 minutes of prep.** Only 1,421 labeled genomes, which fits "1–3k genomes" suspiciously well, and thin data makes the no-call/calibration mechanics genuinely matter. If organizers want a *hard* challenge, this is it. (See Self-roast #1.)

**Prep consequence:** build the pipeline species-agnostic, but pre-download E. coli (full) + K. pneumoniae + N. gonorrhoeae (labels + 3–5k genomes each). That covers ~90% of the probability mass with ~25 GB of storage.

---

## 4. Exact pull mechanics — BV-BRC (all verified today)

### 4.1 Data API (metadata + labels) — no auth for public data
Base: `https://www.bv-brc.org/api/<collection>?<RQL query>`. Collections used: `genome`, `genome_amr`, `genome_sequence`, `sp_gene`.
```bash
# all E. coli LAB-measured AST labels as CSV (page with limit(count,offset), cap 25k/page)
curl -s "https://www.bv-brc.org/api/genome_amr/?eq(taxon_id,562)&eq(evidence,Laboratory%20Method)&limit(25000,0)" -H "Accept: text/csv" > ecoli_amr_p1.csv
# genome metadata for QC filtering (contigs, checkm, mlst, collection_year...)
curl -s "https://www.bv-brc.org/api/genome/?eq(taxon_lineage_ids,562)&eq(public,true)&select(genome_id,genome_name,genome_status,genome_quality,contigs,contig_n50,genome_length,checkm_completeness,checkm_contamination,mlst,collection_year,isolation_country,assembly_accession)&limit(25000,0)" -H "Accept: text/csv" > ecoli_meta.csv
# total rows = Content-Range response header; per-drug counts = facet_counts response header (see §1.1)
```
Verified: CSV accept-header works; `Content-Range: items 0-25/243124`-style totals; `facet((field,x),(mincount,n))` requires a preceding `eq(...)` filter or it 400s.

### 4.2 CLI (convenience; Perl)
Repo [github.com/BV-BRC/BV-BRC-CLI](https://github.com/BV-BRC/BV-BRC-CLI), Homebrew tap [BV-BRC/homebrew-BV-BRC-CLI](https://github.com/BV-BRC/homebrew-BV-BRC-CLI) (`brew install` on macOS). Key commands: `p3-all-genomes` (metadata TSV), `p3-genome-fasta`, `p3-dump-genomes` (fna/gto). Docs: [CLI getting started](https://www.bv-brc.org/docs/cli_tutorial/cli_getting_started.html), command refs e.g. [p3-dump-genomes](https://www.bv-brc.org/docs///cli_tutorial/command_list/p3-dump-genomes.html). Account needed only for private workspace ops; public queries are anonymous.

### 4.3 FTPS bulk download (the fast lane for genomes)
Plain `ftp://` is **dead** — BV-BRC migrated to explicit FTPS (verified: plain listing returns nothing; FTPS works). [Official FTP doc](https://www.bv-brc.org/docs/quick_references/ftp.html).
```bash
# one-shot: the entire lab-AST label table (142 MB, verified present 2026-07-18)
curl -s --ssl-reqd --user anonymous:guest ftp://ftp.bv-brc.org/RELEASE_NOTES/PATRIC_genomes_AMR.txt -o PATRIC_genomes_AMR.txt
# also in RELEASE_NOTES/: genome_summary (158 MB), genome_metadata (562 MB), genome_lineage (371 MB)
# per-genome files: genomes/<genome_id>/<genome_id>.fna (+ .faa .gff .features.tab .spgene.tab)
for i in `cat genome_list`; do wget -qN "ftps://ftp.bv-brc.org/genomes/$i/$i.fna"; done   # official one-liner
# faster + still polite:
cat genome_list | xargs -P 8 -I{} wget -qN "ftps://ftp.bv-brc.org/genomes/{}/{}.fna"
```
`.spgene.tab` per genome = specialty-gene (AMR gene) calls — a free precomputed feature stream if the organizers don't supply AMRFinderPlus output.

### 4.4 Sequence pull via API (FTP fallback)
`genome_sequence` serves raw contig sequence (verified: `select(genome_id,accession,length,sequence)` returns sequence strings) — workable for a few hundred genomes, but for thousands it's many MB of JSON per page; prefer FTPS or `p3-genome-fasta`.

### 4.5 Sizes & realistic times
- Bacterial `.fna` ≈ 4–5.5 MB (E. coli ~5.3 MB). **1k genomes ≈ 5 GB; 3k ≈ 15 GB** uncompressed (~4× smaller gzipped).
- Sequential `wget` loop: expect ~5–20 MB/s effective → **3k genomes ≈ 15–50 min**. With `xargs -P 8`: **~4–10 min**. Labels CSV: seconds. `PATRIC_genomes_AMR.txt`: 142 MB, <1 min.
- No rate limit hit during this research (~60 API calls), but add `sleep 0.2` and retry-on-500 to be safe; API paging beyond 25k/response requires `limit(n,offset)` loops.
- **Auth:** none needed for anything above. Account ([user.bv-brc.org/register](https://user.bv-brc.org/register)) only for workspace/analysis jobs (e.g. running their assembly or annotation services) — not needed at the hackathon.

---

## 5. Fallback sources & licensing

| Source | What you get | When to use | License/attribution |
|---|---|---|---|
| **BV-BRC FTP `RELEASE_NOTES/PATRIC_genomes_AMR.txt`** | All lab AST labels, one 142 MB TSV | API down/slow at event start | Free to use; cite [Olson et al. NAR 2023 (PMC9825582)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9825582/) |
| **NCBI Pathogen Detection / AST browser** | Submitter AST from BioSample attributes; isolates linked to SNP clusters ([AST browser](https://www.ncbi.nlm.nih.gov/pathogens/ast), [HowTo](https://www.ncbi.nlm.nih.gov/core/assets/pathogens/files/HowTo/FindIMIresisbasedonMICv2.pdf)) | Cross-check labels; hidden-test provenance guesses | NCBI data public; unvetted — see trap #6 |
| **NCBI Datasets CLI** | `datasets download genome taxon "escherichia coli" --assembly-level complete,chromosome --include genome` → dehydrated zip, `datasets rehydrate` ([docs](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/command-line-tools/)) | If you need RefSeq assemblies specifically | Public domain (US Gov); cite NCBI |
| **NDARO** ([ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance](https://www.ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance/)) | AMR gene/allele catalog, HMMs, reference isolates | Feature reference for evidence category (i), NOT a label source | Public domain |
| **NARMS Now (CDC)** ([wwwn.cdc.gov/narmsnow](https://wwwn.cdc.gov/narmsnow/)) | Downloadable AST tables: Salmonella, Shigella, E. coli O157, Campylobacter + WGS links ([update notes](https://stacks.cdc.gov/view/cdc/58082/cdc_58082_DS1.pdf)) | Salmonella/E. coli cross-validation | US Gov public domain; cite CDC NARMS |
| **CRyPTIC via ENA** | 12,289 MTB × 13-drug MICs + reads | Only if organizer species is MTB | PLOS CC BY; reads via INSDC |
| **Hu et al. Mendeley benchmark** ([doi:10.17632/6vc2msmsxi.1](https://data.mendeley.com/datasets/6vc2msmsxi/1)) | 78 ready species×drug datasets + splits | Dress rehearsal tonight; emergency backup data | Mendeley Data, typically CC BY 4.0 (check record) |
| **Arcadia E. coli set** ([Zenodo](https://doi.org/10.5281/zenodo.12692732)) | 6,983 strains × 50 drugs phenotype matrix + accessions | Same | CC BY 4.0 (Zenodo) |
| **ENA** ([ebi.ac.uk/ena](https://www.ebi.ac.uk/ena/browser/api/)) | Raw reads/assemblies by accession, REST API | If BV-BRC lacks a needed accession | INSDC open-access policy; cite ENA + submitters |
| **MGnify** | Metagenomes | **Don't** — not isolate AST | — |

General licensing position: genome sequences in BV-BRC/NCBI/ENA derive from INSDC public archives (no copyleft; etiquette = cite resource + original BioProjects); NARMS/CDC and NCBI-generated content are US-government public domain; papers' supplementary datasets are CC BY — attribute and move on. Nothing here restricts hackathon use.

---

## Self-roast

1. **The organizer-guess could be wrong in the expensive direction.** My 65% on E. coli is reasoned, not evidence — organizers may deliberately pick a *harder* species. P. aeruginosa's 1,421 labeled genomes fits "1–3k genomes" suspiciously well, and thin data makes the no-call/calibration mechanics actually matter. If they do, my pre-download advice (E. coli + Klebsiella + Ngon) misses, and the team loses the first 2–4 hours to a cold P. aeruginosa pull. Mitigation is cheap (the pull script is species-parameterized), but the *prep hours* are concentrated where they may not pay off.
2. **Row counts flatter to deceive.** I report 243k E. coli lab-AST rows, but that is only 12.6k unique genomes, and after dropping conflicting labels, QC-filtering genomes, and intersecting to a rectangular 3–5-drug matrix, the usable matrix shrinks further (Arcadia got 6,983 strains × ≥1 drug from the same pool, with only ~6k labels even for their best drug). Any plan sized on my top-line numbers (e.g. "we'll have 15k cipro labels") is oversized; the honest design target is 2–6k genomes × 3–5 drugs — coincidentally exactly the organizer's stated range.
3. **My "verified today" mechanics may rot by event day, and I optimized for BV-BRC monoculture.** FTPS endpoints, the 25k page cap, header-based facet counts, and the CLI's Perl dependency are all single-point-of-failure infrastructure I tested once, on one network. If BV-BRC is down/throttled during the event (or the organizer's dataset is actually built from NCBI BioSample AST instead), the team's muscle memory is pointed at the wrong API; the NARMS/NCBI fallbacks listed here are documented but not rehearsed, and a fallback you haven't run is not a fallback.
