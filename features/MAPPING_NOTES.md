# MAPPING_NOTES — drug → resistance-determinant mapping (evidence category i)

Companion to `drug_class_map.yaml` (the machine-readable table) and
`map_evidence.py` (the CLI that applies it). Curated 2026-07-19 for
E. coli (taxon 562), AMRFinderPlus v4 output vocabulary
("Element symbol" / "Class" / "Subclass" / "Subtype" / "Method").

Rule: **no invented mappings** — every drug↔determinant link below traces to
one of the cited sources. Where sources disagree or evidence is indirect, the
rule is `confidence: review`, never silently counted as confirmed.

## 1. Sources

| Key | What | URL | Version / accessed | Citation |
|---|---|---|---|---|
| resfinder_phenotypes | ResFinder genotype→phenotype panel (`phenotypes.txt`, 3213 rows) | https://bitbucket.org/genomicepidemiology/resfinder_db/raw/master/phenotypes.txt | master, 2026-07-19 | Bortolaia et al. 2020 (ResFinder 4.0), JAC doi:10.1093/jac/dkaa389; Florensa et al. 2022, JAC (PMC8914360) |
| pointfinder_ecoli | PointFinder E. coli point-mutation panel (`escherichia_coli/resistens-overview.txt`, 72 rows) | https://bitbucket.org/genomicepidemiology/pointfinder_db/raw/master/escherichia_coli/resistens-overview.txt | master, 2026-07-19 | Zankari et al. 2017 (PointFinder), JAC doi:10.1093/jac/dkx217 |
| amrfp_catalog | AMRFinderPlus `ReferenceGeneCatalog.txt` (per-allele class/subclass + curated POINT set, 11358 rows) | https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/latest/ReferenceGeneCatalog.txt | DB **2026-05-15.1**, 2026-07-19 | Feldgarden et al. 2021, Sci Rep 11:12728, PMID 34135355 |
| amrfp_interpreting | AMRFinderPlus wiki "Interpreting results" (Method tiers; Subclass semantics) | https://github.com/ncbi/amr/wiki/Interpreting-results | 2026-07-19 | — |
| amrfp_methods | AMRFinderPlus wiki "Methods" (hit-quality ordering; point detection) | https://github.com/ncbi/amr/wiki/Methods | 2026-07-19 | — |

CARD ARO was **not needed** for any confirmed rule (ResFinder + AMRFinderPlus
curation cover everything); it is named as the follow-up cross-check for the
one OXA conflict (§3). Local working copies of the fetched panels were kept
outside the repo (/tmp) — the URLs above are the citations.

Key AMRFinderPlus semantics the design rests on (amrfp_interpreting, quoted in
the YAML header): Subclass "CEPHALOSPORIN" = Lahey **2be** extended-spectrum
definition; "CARBAPENEM" = the protein *has carbapenemase activity* but may or
may not confer other β-lactam resistance; when phenotype is unclear, Subclass
falls back to the Class value. Method quality order (amrfp_methods):
ALLELE > EXACT > BLAST > INTERNAL_STOP > PARTIAL_CONTIG_END > PARTIAL > HMM.

## 2. Rule families per drug (all `confirmed` unless stated)

**ciprofloxacin**
- QRDR POINT mutations `gyrA|gyrB|parC|parE` (Subtype POINT, Class QUINOLONE) —
  PointFinder panel maps gyrA G81/D82/S83/A84/Q106/A196, gyrB D426/K447, parC
  A56/S57/F60/G78/S80/E84, parE 11 positions (incl. I529L) to ciprofloxacin;
  AMRFinderPlus curates the same loci (verified: gyrA_S83L, gyrA_D87N,
  parC_S80I, parC_E84V, parE_I529L all exist in the catalog as QUINOLONE).
- `qnr*`, `qepA*` — every qnr family and qepA1–4 → Ciprofloxacin in the
  ResFinder panel. PMQR = low-level resistance (noted for the report layer).
- `aac(6')-Ib-cr` — ResFinder (PMID 17938184) → Ciprofloxacin; panel caveat
  (PMID 16369542): MIC does not always cross ECOFF.
- `oqxA|oqxB` — **review**: AMRFinderPlus tags PHENICOL/QUINOLONE; absent from
  the ResFinder panel.
- `marR|soxR|soxS|acrR` POINT — **review**: NCBI-curated, MULTIDRUG subclass
  incl. QUINOLONE/FLUOROQUINOLONE; pleiotropic efflux upregulation.

**gentamicin** (substrate-aware, per-allele)
- AMR genes with Subclass containing GENTAMICIN — AMRFinderPlus per-allele
  curation, cross-validated against ResFinder: aac(3)-I/II/III/IV/VI,
  ant(2'')-Ia (=aadB), aac(6')-II family, gentamicin-active aac(6')-Ib
  alleles (e.g. Ib11), aph(2'') family, aac(6')-Ie/aph(2''), armA.
  Canonical **aac(6')-Ib is NOT gentamicin-tagged** (tobramycin/amikacin
  only, ResFinder PMID 2841303) — verified in both sources.
- `rmt[A-Z]|npmA` symbol rule — 16S methyltransferases; ResFinder maps all to
  Gentamicin (rmtB PMID 14742200, npmA PMID 17875999); AMRFinderPlus gives
  them only the generic Subclass AMINOGLYCOSIDE, hence the explicit rule.
- **review**: `aph(3')-IIa/IIb/VIa/VIb` (ResFinder lists gentamicin, PMIDs
  1664906/8723476/2846986/16048938; AMRFinderPlus does not) and
  `aac(3)-IXa/VIIa/VIIIa/Xa` (same conflict; environmental, rare in E. coli).

**ampicillin**
- Any acquired β-lactamase (Class BETA-LACTAM, Subtype AMR) — ResFinder rows
  for blaTEM-1A, blaSHV-1, blaCTX-M-1, blaCMY-1, blaKPC-2, blaNDM-1,
  blaVIM-1, blaIMP-1, blaOXA-48, blaOXA-1 all list Ampicillin/Amoxicillin.
- Exclusions: `blaEC*` (intrinsic, basal expression confers no phenotype;
  AMRFinderPlus scope "plus") and `blaOXA-53|blaOXA-74` (ResFinder:
  ceftazidime/cefepime-only).

**cefotaxime / ceftazidime**
- `blaCTX-M-*` — ResFinder CTX-M-1 row: Cefotaxime, Ceftazidime, Ceftriaxone.
- Acquired AmpC `blaCMY|DHA|ACC|ACT|MIR|MOX|FOX|LAT|CMH-*` — ResFinder CMY-1
  row: Cefotaxime, Ceftazidime, Cefoxitin (no carbapenems).
- `blaKPC|NDM|VIM|IMP-*` — ResFinder rows list Cefotaxime **and** Ceftazidime
  in addition to carbapenems. **OXA-48-like explicitly excluded** (its
  ResFinder row lists carbapenems but no cephalosporins).
- Subclass CEPHALOSPORIN catch-all (Lahey 2be) — catches ESBL alleles of
  narrow families (blaTEM-68, blaSHV-12 verified CEPHALOSPORIN in the
  catalog; ResFinder TEM-68 lists Cefotaxime+Ceftazidime) and
  GES/PER/VEB/BEL/TLA/SFO. Narrow blaTEM-1/blaSHV-1 (Subclass BETA-LACTAM)
  correctly do not match.
- `ampC_*` POINT — chromosomal ampC promoter/attenuator hyperexpression
  (AMRFinderPlus ampC|CEPHALOSPORIN; PointFinder ampC_promoter −42/−32/indels
  → cefotaxime+ceftazidime).
- **review**: `blaOXA-*` when tagged CEPHALOSPORIN (conflict: AMRFinderPlus
  tags OXA-1/10 CEPHALOSPORIN, ResFinder lists no 3GC for them — only
  cefepime; other OXA alleles do list 3GC; CARD ARO per-allele check
  suggested), `ftsI_*` POINT (PBP3, variable magnitude).
- Exclusion: `blaEC*` gene presence (basal intrinsic copy — would otherwise
  flag every E. coli as 3GC-resistant).
- Ceftazidime caveat: CTX-M enzymes are primarily cefotaximases; CAZ MICs vary
  by allele. Mapping identical, evidence strength noted for the report layer.

**meropenem**
- Subclass CARBAPENEM (Subtype AMR) — "carbapenemase activity" per
  AMRFinderPlus; covers KPC/NDM/VIM/IMP/OXA-48-like/carbapenemase-GES/IMI.
  Cross-validated: ResFinder KPC-2, NDM-1, VIM-1, IMP-1, OXA-48 rows all list
  Meropenem.
- **review**: `ompC|ompF|ompR` POINT — NCBI-curated porin-loss substitutions
  tagged CARBAPENEM; usually sufficient only in combination with an enzyme.

**trimethoprim-sulfamethoxazole (SXT)** — component-labeled
- Subclass TRIMETHOPRIM (dfrA*, also catches dfrB) — all 90 ResFinder dfrA
  alleles → Trimethoprim. Component: trimethoprim.
- Subclass SULFONAMIDE (sul1/2/3/4) — ResFinder → Sulfamethoxazole.
  Component: sulfamethoxazole.
- `folP_*` POINT — PointFinder folP F28/P64 → Sulfamethoxazole; AMRFinderPlus
  folP|SULFONAMIDE. Component: sulfamethoxazole.
- Either component's determinant counts as SXT evidence, reported with its
  component label.

## 3. Mappings marked `confidence: review` (full list)

| Drug | Determinant | Why review |
|---|---|---|
| ciprofloxacin | oqxA/oqxB efflux operon | AMRFinderPlus tags QUINOLONE; absent from ResFinder panel |
| ciprofloxacin | marR/soxR/soxS/acrR POINT | curated, but pleiotropic low-level efflux |
| gentamicin | aph(3')-IIa/IIb/VIa/VIb | ResFinder says gentamicin; AMRFinderPlus says no |
| gentamicin | aac(3)-IXa/VIIa/VIIIa/Xa | ResFinder says gentamicin; AMRFinderPlus generic; rare in E. coli |
| cefotaxime, ceftazidime | blaOXA-* with CEPHALOSPORIN subclass | sources conflict on OXA-1/10; family heterogeneous (CARD ARO follow-up) |
| cefotaxime, ceftazidime | ftsI (PBP3) POINT | curated; variable phenotype magnitude in E. coli |
| meropenem | ompC/ompF/ompR POINT (porin loss) | curated; usually not sufficient alone |

## 4. Sanity report: mechanism coverage vs blind spots

| Drug | Acquired/target mechanism coverage | Declared blind spots (unexplained-resistance caveat) |
|---|---|---|
| ciprofloxacin | **Complete**: QRDR points + qnr + qepA + aac(6')-Ib-cr (+2 review) | efflux overexpression beyond curated regulator points; POINT calls need `--organism Escherichia`; uncurated novel QRDR substitutions invisible (callability-gate input, not evidence) |
| gentamicin | **Complete** for AMEs + 16S RMTases (allele-aware; 2 rare review families) | 16S rRNA target mutations (PointFinder-only, not in AMRFinderPlus E. coli set); novel AME alleles |
| ampicillin | **Complete**: any acquired β-lactamase; blaEC excluded by design | ftsI/PBP3 modest MIC shifts; porin — both marginal for ampicillin |
| cefotaxime | **Complete** for CTX-M/AmpC/carbapenemase/ESBL-alleles (+2 review) | ampC hyperexpression via novel promoter/IS events; ESBL+porin-loss combinations (porin side invisible); family-level-only novel ESBL calls may fall back to Subclass BETA-LACTAM |
| ceftazidime | **Complete**, same as cefotaxime | same; plus CTX-M cefotaxime-bias makes genotype→CAZ phenotype noisier |
| meropenem | **Complete** for carbapenemases (+1 review) | porin loss without a curated point call (truncations surface only as PARTIAL/INTERNAL_STOP omp hits, not drug-tagged); efflux; weak-expression OXA-48 |
| SXT | **Complete** for dfr + sul + folP | **folA (trimethoprim target) mutations are in NEITHER panel** — a genuine trimethoprim blind spot; efflux |

All 7 drugs have complete coverage of the dominant acquired/target-mutation
mechanisms; the unexplained-resistance caveat per drug concentrates on
porin/efflux and (SXT only) folA — exactly the categories the pipeline's
"unexplained resistance rate" metric is meant to quantify (synthesis doc §2.4).

## 5. Verification

`map_evidence.py --selftest`: 31 checks pass, including the two required
cases — gyrA_S83L/parC_E84V POINT hits map to ciprofloxacin, and blaTEM-1
does NOT map to cefotaxime (while ESBL allele blaTEM-68 does).

Smoke run (`data/smoke_562.100000.tsv`, ST131-like genome with
blaCTX-M-15/blaTEM-1/blaEC, QRDR mutations, sul1+dfrA17):

| Drug | Hits | Detail |
|---|---|---|
| ciprofloxacin | 5 | gyrA_S83L, gyrA_D87N, parC_S80I, parC_E84V, parE_I529L — all confirmed, tier point |
| cefotaxime | 1 | blaCTX-M-15 (confirmed, full_gene/ALLELEX); blaTEM-1 and blaEC correctly absent |
| ceftazidime | 1 | blaCTX-M-15 |
| ampicillin | 2 | blaCTX-M-15, blaTEM-1; blaEC correctly absent |
| trimethoprim-sulfamethoxazole | 2 | dfrA17 (trimethoprim), sul1 (sulfamethoxazole) |
| gentamicin | 0 | aadA5 is STREPTOMYCIN-only — correct |
| meropenem | 0 | no carbapenemase present — correct |

## 6. Usage

```bash
features/.venv/bin/python features/map_evidence.py data/smoke_562.100000.tsv --drug ciprofloxacin
features/.venv/bin/python features/map_evidence.py data/smoke_562.100000.tsv --drug sxt --format json
features/.venv/bin/python features/map_evidence.py --selftest
features/.venv/bin/python features/map_evidence.py --list-drugs
```

Python: `features/.venv` (per-area venv, CONTRACT.md); dependency: PyYAML only.
