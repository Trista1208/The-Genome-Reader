# AMRFinderPlus Practicalities — Genome Firewall (Hack-Nation) prep

Research date: 2026-07-18. Software facts verified against live sources on that date:
latest software **v4.2.7** (released 2026-01-26), latest database **2026-05-15.1**
(database format version 4.2.0). Primary sources: [ncbi/amr GitHub wiki](https://github.com/ncbi/amr/wiki),
[bioconda recipe](https://bioconda.github.io/recipes/ncbi-amrfinderplus/README.html),
[NCBI AMR FTP](https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/latest/).

**One-paragraph verdict:** AMRFinderPlus nucleotide-only mode on raw contigs is the right
primary feature extractor for this challenge. It is conda-installable on macOS (incl. Apple
Silicon) and Linux in ~2 minutes, runs at roughly 1–3 min/genome, covers both acquired genes
and (for 31 curated taxa) point mutations in one TSV, and its `Class`/`Subclass` columns map
hits to drug classes — which feeds both the evidence-category labels and the
molecular-target-presence gate. Do **not** add ResFinder/RGI/abricate in a 48h build unless
the challenge species turns out to be outside AMRFinderPlus's curated point-mutation set
*and* resistance in that species is known to be mutation-driven.

---

## 1. Installation (macOS/Linux, 2026)

### Recommended: bioconda

```bash
# ~2-5 min solve; pin the version for team reproducibility
conda create -n amrfinder -c conda-forge -c bioconda ncbi-amrfinderplus=4.2.7
conda activate amrfinder
amrfinder -u            # downloads the database (see below — REQUIRED)
bash test_amrfinder.sh -p   # optional sanity test, ends with "Success!"
```

Facts, verified:

- Package name is `ncbi-amrfinderplus` on the bioconda channel
  ([recipe page](https://bioconda.github.io/recipes/ncbi-amrfinderplus/README.html)).
  Current bioconda version: **4.2.7-0**. Older 3.x builds exist but avoid them — v4.0
  changed the DB format and output column names
  ([v4.0.3 release notes](https://github.com/ncbi/amr/releases/tag/amrfinder_v4.0.3)).
- **Platforms** (queried from anaconda.org 2026-07-18): `linux-64`, `osx-64` (all versions),
  `linux-aarch64` and **`osx-arm64`** (Apple Silicon: only 4.0.22, 4.0.23, 4.2.4, 4.2.5, 4.2.7).
  On Apple Silicon, explicitly install ≥4.2.7 or conda may fall back to an emulated/osx-64 env.
  On Intel macs everything works.
- **Dependencies** are pulled in automatically: `blast >=2.9`, `hmmer >=3.2`, `curl`
  ([recipe meta.yaml](https://github.com/bioconda/bioconda-recipes/blob/master/recipes/ncbi-amrfinderplus/meta.yaml)).
  No manual BLAST+ install needed. If you install from source/binaries instead, you must
  ensure `blastp`/`tblastn`/`hmmsearch` are on PATH
  ([Test your installation](https://github.com/ncbi/amr/wiki/Test-your-installation)).
- Verify with `amrfinder --database_version` (prints software + DB versions).

### The database is a SEPARATE download — and not bundled

The current bioconda recipe contains only `build.sh` + `meta.yaml` — **no post-link script**,
so a fresh conda install has *no database*. First run fails until you run:

```bash
amrfinder -u    # (or --update); needs internet access to ftp.ncbi.nlm.nih.gov
```

This downloads the latest DB into `$CONDA_PREFIX/share/amrfinderplus/data/YYYY-MM-DD.N/`
([Upgrading wiki](https://github.com/ncbi/amr/wiki/Upgrading); real-world path seen in
[this issue](https://github.com/ncbi/amr/issues/174)). Verified sizes in the current
`latest` dir (2026-05-15.1): `AMR.LIB` (HMM library) **107 MB**, `AMR_CDS.fa` 11 MB,
`AMRProt.fa` 4.7 MB, `ReferenceGeneCatalog.txt` 2.3 MB — total footprint ≈150 MB.
Plan for **hackathon Wi-Fi risk**: pre-download the DB on every team laptop the night
before (or carry it on a USB stick) and point at it with `amrfinder -d <dir>`.

### Database versioning and why it matters

- DB versions are date-stamped (`YYYY-MM-DD.N`), updated roughly every 1–3 months, and
  **results change between versions**: new genes/alleles, renamed hierarchy nodes, new
  point mutations, new blacklisted genes. Two teammates on different DB versions will
  produce *different feature matrices* from identical FASTAs. This is a silent-reproducibility
  bug, not an error message.
- Old DB versions are archived under per-format directories:
  `.../AMRFinderPlus/database/4.2/2026-05-15.1/` etc.
  ([FTP index](https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/)).
  Software–DB compatibility is gated by `database_format_version.txt` (currently `4.2.0`):
  software 4.2.x requires a format-4.2 DB; `amrfinder` refuses mismatches
  ([AMRFinderPlus database wiki](https://github.com/ncbi/amr/wiki/AMRFinderPlus-database)).
- **Team protocol:** pin one DB version for the whole event (e.g. `2026-05-15.1`),
  distribute that exact directory, always run with `-d /path/to/2026-05-15.1`, and record
  `amrfinder --database_version` output in every experiment log. Note the version string is
  printed to **STDERR**, never embedded in the output TSV (see §7).
- Docker fallback with sw+DB version baked into the tag:
  `staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1`
  ([Docker Hub tags](https://hub.docker.com/r/staphb/ncbi-amrfinderplus/tags)) — the
  [StaPH-B](https://staphb.org) images ship the DB inside, good for a fully offline,
  byte-identical setup.

## 2. Input modes: yes, raw nucleotide FASTA works

`amrfinder -n contigs.fasta` runs directly on assembled contigs with **no prior gene
annotation** — it does translated searches (blastx/tblastn) of the assembly against the AMR
protein database plus blastn for nucleotide point-mutation references
([Running AMRFinderPlus](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus),
[Methods](https://github.com/ncbi/amr/wiki/Methods)).

Trade-off to know: **nucleotide-only mode does not run the HMM library** ("HMM searches are
not performed" — [Methods](https://github.com/ncbi/amr/wiki/Methods)), so sensitivity for
distant homologs is slightly reduced; Method `HMM` hits only appear with protein input.
The "most sensitive and accurate" mode is combined `-p proteins.faa -g annot.gff -n contigs.fna`,
but that needs an annotation step (prokka/bakta) per genome — for 1–3k genomes in 48h,
**skip it**: nucleotide-only is the standard operating mode (used by Bactopia, Theiagen,
nf-core/funcscan) and the delta rarely matters for the curated core AMR genes, which also
have curated blast cutoffs.

Canonical command per genome:

```bash
amrfinder -n genome.fasta -O <Organism> --plus -o out.tsv --threads 4 \
          --mutation_all out.mutations.tsv --print_node
```

- `--plus`: adds stress/virulence/efflux genes. Cheap to include; filter downstream by
  `Scope`/`Type` if noisy. Include it so the option is there.
- `--mutation_all`: reports genotypes at *all* screened point-mutation loci, letting you
  distinguish "susceptible allele confirmed present" from "locus not found" — exactly the
  signal the challenge's no-call/target-gate logic needs. Only meaningful with `-O`.
- `--print_node`: adds the `Hierarchy node` column — a stable family-level ID, very useful
  for collapsing allele-level symbols (blaTEM-1, blaTEM-156 → node) into ML features.

### What `--organism` changes ([wiki table](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus#--organism-option))

1. **Enables point-mutation screening** (Subtype `POINT`) — without `-O` you get *zero*
   point-mutation rows, only acquired genes.
2. Suppresses genes that are near-universal/uninformative in that taxon ("blacklisted").
3. Special behaviors: divergent pbp reporting for `Streptococcus_pneumoniae` /
   `Neisseria_gonorrhoeae`; runs StxTyper for `-O Escherichia` (needs `-n` and `--plus`).
4. `amrfinder -l` lists valid values. As of DB 2026-05-15.1 there are **31 taxa** with
   curated point mutations (I counted `whitelisted_taxa` in ReferenceGeneCatalog.txt):
   Acinetobacter_baumannii, Bordetella_pertussis, Burkholderia_cepacia/pseudomallei,
   Campylobacter, Citrobacter_freundii, Clostridioides_difficile, Corynebacterium_diphtheriae,
   Enterobacter_asburiae/cloacae, Enterococcus_faecalis/faecium, Escherichia (=Shigella),
   Haemophilus_influenzae, **Helicobacter_pylori** (newer than the wiki table — `-l` is
   authoritative), Klebsiella_oxytoca/pneumoniae, Neisseria_gonorrhoeae/meningitidis,
   Pseudomonas_aeruginosa, Salmonella, Serratia_marcescens, Staphylococcus_aureus/
   epidermidis/pseudintermedius, Streptococcus_agalactiae/pneumoniae/pyogenes,
   Vibrio_cholerae/parahaemolyticus/vulnificus.

**First thing to check when the challenge dataset drops:** is the species in `amrfinder -l`?
If yes → always pass `-O`; your point-mutation features and mutation-driven drugs depend on it.
If no (e.g. Mycobacterium tuberculosis, where NCBI explicitly says mutation coverage is absent)
→ AMRFinderPlus gives you acquired-gene features only, and the "known resistance mutation"
evidence tier must come from elsewhere (see §6).

## 3. Runtime and throughput

Hard numbers from primary sources are scarce (no benchmark in the
[Feldgarden 2021 paper](https://www.nature.com/articles/s41598-021-91456-0)); treat these
as engineering estimates, and **benchmark on ~20 genomes before launching the full batch**:

- Nucleotide-only mode on a ~5 Mb genome, 4 threads: expect **~1–3 min/genome** on a modern
  laptop (dominated by tblastn/blastx of the assembly vs ~8.4k reference proteins; the
  Theiagen workflow provisions 8 CPUs for this task
  ([PHB docs](https://theiagen.github.io/public_health_bioinformatics/v2.2.1/workflows/standalone/ncbi_amrfinderplus/));
  a hosted pipeline runs assembly+MLST+AMRFinder+ResFinder in 5–10 min total
  ([Solu changelog](https://solu-changelog.feather.blog/assembly-amrfinder))).
- `--threads` defaults to 4; >4 helps nucleotide searches, ~nothing for protein-only
  ([wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)).
- **1k–3k genomes ≈ 30–150 core-hours worst case; more realistically 20–100 core-hours
  at 1–3 min each.** On an 8-core laptop running 2 parallel jobs × 4 threads:
  3,000 genomes ≈ 4–12 h. On 4 parallel jobs × 2 threads: ≈ 2–6 h. **This is fine overnight
  but not at noon on day 2 — start the batch in hour 1–2 of the event** (or immediately if
  precomputed results are provided).

Batch recipe (GNU parallel; `brew install parallel` / `apt install parallel`):

```bash
ls genomes/*.fasta | parallel -j 2 --bar \
  'amrfinder -n {} -O Escherichia --plus --threads 4 \
     -o results/{/.}.amr.tsv --mutation_all results/{/.}.mut.tsv 2> results/{/.}.log'
# xargs alternative (no GNU parallel on stock macOS):
ls genomes/*.fasta | xargs -P 2 -I{} sh -c \
  'b=$(basename {} .fasta); amrfinder -n {} -O Escherichia --plus --threads 4 \
     -o results/$b.amr.tsv --mutation_all results/$b.mut.tsv 2> results/$b.log'
```

Keep the per-genome STDERR logs — they contain the software+DB version strings you need for
the reproducibility section (§1) and for validating organizer precomputed results (§7).

## 4. Output format and the feature-matrix recipe

### Columns (v4.x, tab-separated; [full field docs](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus#output-format))

| # | Column (v4 name) | v3 name (pre-4.0!) | Meaning / use |
|---|---|---|---|
| 1 | `Protein id` | `Protein identifier` | Query protein ID; `NA` for nuc-only runs |
| 2 | `Contig id` | same | Contig of the hit (present for `-n`) |
| 3–5 | `Start`, `Stop`, `Strand` | same | 1-based coords; `Strand` is `+`/`-` (orientation of the *hit*, see §5) |
| 6 | `Element symbol` | `Gene symbol` | e.g. `blaTEM-156`, `gyrA_T86A`, `23S_A2075G` — **the primary feature key** |
| 7 | `Element name` | `Sequence name` | Full name, e.g. "class A beta-lactamase TEM-156" |
| 8 | `Scope` | same | `core` (curated AMR) vs `plus` (stress/virulence; only with `--plus`) |
| 9 | `Type` | `Element type` | `AMR` / `STRESS` / `VIRULENCE` |
| 10 | `Subtype` | `Element subtype` | **`AMR` = acquired gene; `POINT` = curated resistance point mutation; `POINT_DISRUPT` = putative gene-disrupting lesion** |
| 11 | `Class` | same | Drug class the element affects, e.g. `BETA-LACTAM`, `QUINOLONE` — **maps hit → drug** |
| 12 | `Subclass` | same | Finer drug mapping where known, e.g. `CEPHALOSPORIN`, `VANCOMYCIN` |
| 13 | `Method` | same | Detection method & completeness — see below |
| 14 | `Target length` | same | Query length (aa or nt) |
| 15 | `Reference sequence length` | same | DB reference length |
| 16 | `% Coverage of reference` | same | <90% ⇒ partial |
| 17 | `% Identity to reference` | same | ≥90% default cutoff (curated overrides exist) |
| 18 | `Alignment length` | same | |
| 19 | `Closest reference accession` | `Accession of closest sequence` | RefSeq accession; for POINT rows it's the *susceptible* WT allele |
| 20 | `Closest reference name` | `Name of closest sequence` | |
| 21 | `HMM accession` | `HMM id` | `NA` in nuc-only mode |
| 22 | `HMM description` | same | |
| 23 | `Hierarchy node` (opt.) | — | Family-level node ID (`--print_node`); **use as canonical feature ID** |

⚠️ **The v3→v4 column rename (Oct 2024,
[release notes](https://github.com/ncbi/amr/releases/tag/amrfinder_v4.0.3)) is the #1 parser
bug you'll hit**: `Gene symbol→Element symbol`, `Sequence name→Element name`,
`Element type→Type`, `Element subtype→Subtype`, `Accession of closest sequence→Closest
reference accession`, `HMM id→HMM accession`. Organizer precomputed results generated with
v3.x will have the old headers. Normalize on read (§7).

### Distinguishing hit classes: use `Subtype` + `Method`

`Method` values ([docs](https://github.com/ncbi/amr/wiki/Interpreting-results#the-method-column)):
`ALLELE` (100%/100% allele match) > `EXACT` (100%/100% non-allele) > `BLAST` (>90% cov,
>90% id) > `INTERNAL_STOP` (premature stop — likely non-functional!) > `PARTIAL_CONTIG_END`
(50–90% cov, break at contig edge) > `PARTIAL` (50–90% cov, internal) > `HMM` (protein-only).
Suffix `P`/`X`/`N` = found via protein / translated-nucleotide / nucleotide-blast search.
`POINTP/POINTX/POINTN` = point mutation calls.

Concrete classification rule for features:

```python
ACQUIRED_FULL    = (Subtype == "AMR")  & Method.str.contains("ALLELE|EXACT|BLAST", regex=True)
ACQUIRED_PARTIAL = (Subtype == "AMR")  & Method.str.contains("PARTIAL", regex=True)
POINT_MUT        = (Subtype == "POINT")           # Method POINTP/POINTX/POINTN
DISRUPT          = (Subtype == "POINT_DISRUPT")
DEAD_GENE        = (Method == "INTERNAL_STOP")    # do NOT count as functional resistance
```

### Feature-matrix recipe (per genome → per drug)

Build three tiers per genome; keep them separate so the model can weight evidence
(and so your evidence-category labels are free):

1. **Tier 1 — functional acquired genes** (`ACQUIRED_FULL`): feature = `Hierarchy node`
   (fallback `Element symbol`), value 1. Optionally split by `Class` →
   `has_AMINOGLYCOSIDE_gene` etc. — these double as drug-specific gate features.
2. **Tier 2 — curated point mutations** (`POINT_MUT`): feature = `Element symbol`
   verbatim (e.g. `gyrA_S83L`, `23S_A2075G`); optionally class-level rollups.
   Use the `--mutation_all` file to add *negative evidence* features:
   `gyrA_locus_present_wt` (locus found, susceptible allele) vs `gyrA_locus_missing`.
3. **Tier 3 — degraded evidence**: `ACQUIRED_PARTIAL` and `INTERNAL_STOP` as separate
   count/flag features, never merged into tier 1. A truncated bla at a contig edge is
   weak evidence; an internal-stop bla is evidence *against* function.

Dedup note: one element can produce multiple rows (fusion genes, `--report_all_equal`),
so collapse by (`genome`, `Hierarchy node`) before pivoting. `Class` values are
controlled vocabulary (uppercase); multiple classes appear as e.g. `BETA-LACTAM` with
subclass detail — join hits to your 3–5 challenge antibiotics via `Subclass` first,
then `Class`, with a small hand-curated mapping table (e.g. `AMINOGLYCOSIDE` →
gentamicin/tobramycin rows; expect ~10–30 mapping rules, an hour of work).

## 5. Pitfalls (ranked by hackathon damage potential)

1. **Column renames v3↔v4** — see §4. Normalize headers defensively.
2. **Partial genes at contig edges** — `PARTIAL_CONTIG_END*` rows are often full-length
   genes split by assembly
   ([docs](https://github.com/ncbi/amr/wiki/Interpreting-results)); treat as weaker
   evidence tier, not absence, not full presence. Circular-contig breaks produce the same
   artifact ([known issue](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus#known-issues)).
3. **Species without an `--organism` option** → silently zero point-mutation features.
   If the challenge species is mutation-driven (MTB is the canonical example), AMRFinderPlus
   alone structurally cannot produce tier-(i) evidence for it. Check `amrfinder -l` first.
4. **`INTERNAL_STOP` ≠ resistance gene** — a pseudogene hit. Counting it as "has blaX"
   creates false resistance signals.
5. **Version not in the output file** — software/DB versions go to STDERR only. If you don't
   capture stderr logs, you cannot later prove which DB produced a feature matrix.
6. **`--plus` scope confusion** — `Scope=plus` rows (efflux, stress, virulence) are *less*
   curated; some are intrinsic/universal in a species. Keep them out of tier-1 features or
   you'll inject near-constant columns.
7. **Intrinsic/inherent resistance is out of scope** — e.g. M. bovis pncA (PZA) resistance
   won't be reported; AMRFinderPlus detects *acquired* genes and *curated* mutations, not
   wild-type intrinsic phenotypes
   ([USDA training notes](https://github.com/USDA-VS/nvsl_bioinformatic_training/blob/main/docs/amrfinder-plus.md)).
   This is exactly why the challenge's molecular-target gate must not infer "likely to work"
   from "no marker found".
8. **Genotype ≠ phenotype** — NCBI's own caution: presence of a gene does not prove
   resistance (expression, porin loss, sub-breakpoint effects)
   ([Interpreting results](https://github.com/ncbi/amr/wiki/Interpreting-results)).
   Put this quote in the demo's disclaimer; judges love it.
9. **macOS-specific**: v4.2.4 had an `-O` crash on macOS
   ([issue #174](https://github.com/ncbi/amr/issues/174), closed) — use 4.2.7. Apple Silicon
   needs the osx-arm64 build (≥4.0.22; §1). `TMPDIR` is respected if /tmp is tight
   ([wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus#temporary-files)).
10. **FASTA defline gotchas** — contig IDs starting with `?`, containing `,,`, or ending in
    `;~,.` make amrfinder exit with an error (makeblastdb quirk,
    [wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus#input-file-formats));
    `.gz` inputs are auto-handled via `gunzip`. No unicode in files.
11. **Frame shifts** are not explicitly detected on acquired genes — they surface as
    `INTERNAL_STOP`/`PARTIAL`, another reason those tiers exist.

## 6. Complementary tools — 48h verdict

| Tool | What it adds over AMRFinderPlus | Cost | Verdict |
|---|---|---|---|
| **ResFinder 4.x** ([paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/), bioconda 4.7.2) | Second acquired-gene DB; PointFinder mutations for a few species; published genotype→phenotype panels (~97% concordance for major species/drugs) | Medium: KMA dependency, its own DB versioning, different output schema (JSON) | **Skip**, unless you want one *literature citation* to justify rules-based phenotype priors |
| **RGI 6.0.8 / CARD** ([card.mcmaster.ca](https://card.mcmaster.ca), bioconda rgi 6.0.8) | CARD protein-variant models catch more mutation-driven resistance across species; `Strict`/`Perfect`/`Loose` paradigm is a nice confidence ladder | Medium-high: Prodigal+DIAMOND pipeline, heavier, noisier output | **Skip** for a curated-taxon challenge; **reconsider** only if the species is outside AMRFinderPlus's 31 taxa |
| **abricate 1.4.0** ([github.com/tseemann/abricate](https://github.com/tseemann/abricate)) | Fast mass screening, bundled NCBI/ResFinder/CARD dbs, trivially parallel | Low | **Skip** — acquired genes only, no point mutations, adds nothing AMRFinderPlus doesn't already give; effectively unmaintained |
| **staramr 0.12.3** ([github.com/phac-nml/staramr](https://github.com/phac-nml/staramr)) | ResFinder/PointFinder wrapper with per-drug phenotype predictions + quality checks | Medium | Only if you adopt ResFinder; otherwise skip |
| **hAMRonization** ([pha4ge/hAMRonization](https://github.com/pha4ge/hAMRonization)) | Unified parser for 17 tools incl. amrfinderplus (validated vs v4.0.3 output) | Low (pip install) | **Optional**: use its `amrfinderplus` parser if you merge ≥2 tools; otherwise 20 lines of pandas is simpler |

Rationale: the marginal value of a second acquired-gene caller is small (these DBs
cross-pollinate; NCBI curates from ResFinder/CARD among others —
[database wiki](https://github.com/ncbi/amr/wiki/AMRFinderPlus-database)) while the cost —
install friction, output harmonization, versioning a second DB, explaining discrepancies to
judges — is high in 48h. Spend those hours on calibration and the grouped-split harness.

## 7. Consuming organizer "precomputed AMRFinderPlus results" robustly

Most likely shapes, in decreasing order of probability:

1. **One TSV per genome** named by sample ID (`<sample>.tsv` / `.txt` / `.amrfinder.tsv`),
   exactly the `amrfinder -o` format of §4 (header + 22–23 cols).
2. **One big concatenated TSV** for all genomes — either with a leading sample/`Name` column
   (what `--name <id>` prepends) or relying on `Contig id`/filename parsing. The `--name`
   option exists precisely for this ([wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)).
3. Possibly **v3-format headers** (pre-Oct-2024 software) or **MicroBIGG-E-style** exports
   from NCBI Pathogen Detection (v4 names, which is why NCBI renamed the columns —
   [release notes](https://github.com/ncbi/amr/releases/tag/amrfinder_v4.0.3)).

Robust ingestion checklist:

```python
import pandas as pd

V3_TO_V4 = {
    "Protein identifier": "Protein id",
    "Gene symbol": "Element symbol",
    "Sequence name": "Element name",
    "Element type": "Type",
    "Element subtype": "Subtype",
    "Accession of closest sequence": "Closest reference accession",
    "Name of closest sequence": "Closest reference name",
    "HMM id": "HMM accession",
}

def read_amrfinder(path_or_buffer, sample=None):
    df = pd.read_csv(path_or_buffer, sep="\t", dtype=str)
    df = df.rename(columns=V3_TO_V4)
    required = {"Element symbol", "Subtype", "Method", "Class", "Subclass"}
    missing = required - set(df.columns)
    assert not missing, f"{path_or_buffer}: missing {missing} — not AMRFinderPlus v3/v4 output?"
    if sample is not None:
        df["sample"] = sample
    elif "Name" in df.columns:            # from --name
        df = df.rename(columns={"Name": "sample"})
    for c in ["% Coverage of reference", "% Identity to reference"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
```

- **Version audit first**: `head -1` one file; check for `Element symbol` (v4) vs
  `Gene symbol` (v3). The TSV itself carries **no** software/DB version — look for an
  organizer README/log; if absent, note in your writeup that feature provenance is
  version-unknown (judges asked for reproducibility; naming this limitation is free points).
- If only v3 results are provided and you want hierarchy nodes, re-derive them by joining
  `Element symbol` → `ReferenceGeneCatalog.txt` / `ReferenceGeneHierarchy.txt`
  ([download](https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/latest/ReferenceGeneCatalog.txt))
  — symbol→node mapping is many-to-one, so aggregate ambiguous joins.
- **Sanity checks that catch silent breakage**: (a) every challenge sample has exactly one
  parsed file/row-group — join against the label manifest and assert 1:1; (b) zero-hit
  genomes produce an *empty or header-only* file, not an error — your parser must emit an
  all-zero feature row for them (this is the "no known signal" evidence tier!); (c) dedupe
  (`sample`, `Element symbol`, `Contig id`, `Start`) before pivoting; (d) verify `Subtype`
  contains `POINT` rows — if not, results were run without `-O` and you have no mutation
  features (re-run yourself if allowed).
- If organizers provide results **and** raw FASTAs: spend the CPU to re-run a random 50
  genomes with your pinned DB and diff. Systematic differences = different DB version;
  decide consciously which feature set to trust, don't mix.

## 8. Build-this vs ignore-this

**Build this (hours 0–4):**
- Pinned conda env (`ncbi-amrfinderplus=4.2.7`) + pinned DB directory, distributed to all laptops.
- `run_amrfinder.sh` batch wrapper (parallel, per-genome logs, `--mutation_all`, `--print_node`).
- `parse_amrfinder.py` implementing §7 ingestion + §4 three-tier feature matrix, unit-tested
  on 3 genomes and on an empty-result file.
- A `drug → Class/Subclass` mapping table for the 3–5 challenge drugs (hand-curated, ~1h).

**Ignore this (48h scope):**
- ResFinder/RGI/abricate/DeepARG/etc. as extra feature streams (§6).
- Combined protein+GFF mode (annotation step not worth it; nuc-only is standard).
- Custom AMRFinderPlus databases ("not a trivial exercise" per NCBI).
- Novel-variant mining via `--mutation_all` `[UNKNOWN]` rows — interesting, not hackathon-scope.

## Self-roast

1. **My runtime numbers are extrapolation, not measurement.** No primary-source benchmark
   exists; if real throughput is 5–10× worse (big multi-plasmid genomes, slow Wi-Fi-throttled
   VM, macOS thermal throttling), the 3k-genome batch won't finish overnight and the team
   needed the organizer's precomputed results all along. Mitigation is stated (benchmark 20
   genomes in hour 1, fall back to precomputed) — but the plan still hinges on an unverified
   constant.
2. **Nucleotide-only mode may be the wrong trade.** I recommend skipping protein+GFF mode
   for speed, but it costs HMM-based sensitivity — i.e., potentially missing exactly the
   divergent/remote homologs the hidden "unseen groups" test set is designed to contain.
   If the challenge species has highly variable AMR alleles, combined mode (or RGI's more
   permissive models) could beat my recommendation on the metric that matters most.
3. **The single-tool doctrine could backfire twice over.** (a) If the challenge species is
   outside the 31 curated taxa and mutation-driven, AMRFinderPlus structurally yields no
   tier-(i) evidence and my "add tools only then" caveat fires *after* hours have been sunk
   into the AMRFinderPlus pipeline; (b) judges may explicitly reward methodological triangulation
   (AMRFinderPlus + ResFinder/RGI agreement as a confidence feature) — it's a cheap,
   legible story, and I told the team to skip it. The 48h-scarcity argument is real, but
   "integrating a second caller" is closer to 2h than to the implied half-day if you use
   hAMRonization.
