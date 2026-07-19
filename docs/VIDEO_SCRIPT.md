# Genome Firewall — video plan (Hack-Nation submission)

Three videos: **V1 technical (~3 min)**, **V2 demo (~2 min)**, **V3 team intro (~20 s)**.
Record 16:9, 1080p, export **MP4 / H.264** (do a 10 s codec + upload test before the
real take). Narration below is exact spoken text — read at ~150 wpm to hit the marks.
Numbers are **model v2** (1,434 genomes, held-out genetic groups). If v3 lands and
ships, update only the lines marked `<!--V3-SLOT-->`; everything else stands.

**Recording assets**

| Asset | Path / URL |
|---|---|
| Static demo app (HF Space) | https://huggingface.co/spaces/Darkroom4364/genome-firewall (local fallback: `cd demo/static && python3 -m http.server 8791`) |
| Colab notebook | `notebooks/GenomeFirewall_Demo.ipynb` |
| Inference API | `api/serve.py` (`/predict`, `/health`) |
| Metrics + reliability plots | `reports/metrics.json`, `reports/reliability_*.png` |
| Curated genomes rationale | `demo/static/data/curated.json` |

Curated story genomes (already wired into the app's story buttons):
**resistant** `562.140931` · **susceptible** `562.100280` · **refusal** `562.100124`.

---

## Video 1 — technical (~3:00)

Slides: build 6 simple slides from this script (contents fully specified below).
Dark background, one idea per slide, numbers huge. Voice: presenter audio over slides.

### Shot list

| # | Time | Shot | On screen |
|---|---|---|---|
| 1 | 0:00–0:18 | Problem numbers slide | Title "The blind prescription". Three big numbers: **1.27 M** deaths attributable to AMR (2019, Murray et al., *Lancet*); **1–3 days** for lab susceptibility results; **10–39%** empiric-therapy failure in ICU patients |
| 2 | 0:18–0:50 | Pipeline diagram | The 5-stage pipeline drawn as boxes (from README): FASTA → AMRFinderPlus 4.2.7 → ~900-gene/mutation feature grid → per-drug elastic-net LR + Platt calibration → honesty layers (no-call band · ANI override · callability gate) → evaluation on skani cluster splits |
| 3 | 0:50–1:25 | Small-model slide | "**80 nonzero weights**" (ciprofloxacin model, of ~900 features; 86–162 across the other four drugs). Side note: ~340 training genomes per drug, a handful of outbreak clones |
| 4 | 1:25–2:25 | Honesty-architecture slide | Four numbered layers: ① skani ANI ≥99.5% cluster splits, headline numbers on unseen lineages only ② asymmetric conformal no-call band (α 0.02 susceptible-side / 0.10 resistant-side) + ANI-distance hard override ③ target-locus callability gate (gyrA/parC/parE) ④ evidence decoupled from model (curated determinant vs statistical association) |
| 5 | 2:25–2:50 | Failure-modes slide | Three rows: homolog leakage → cluster splits; false confidence → calibration + abstention (cefotaxime as proof: R-recall 0.39, 58% abstained); absent-target false-susceptible → callability gate |
| 6 | 2:50–3:00 | Close slide | "We answer ~40% of unseen genomes — at 92% accuracy. The rest go to the lab." |

<!--V3-SLOT: if v3 ships, re-record shot 6 numbers (coverage / accuracy-when-called) and the cefotaxime figures in shot 5; fallback = v2 numbers as written below.-->

### Narration (exact text)

**[Shot 1 · 0:00]** "Every year, antimicrobial resistance kills more than a million
people — 1.27 million deaths in 2019 alone, more than HIV or malaria. When a septic
patient arrives, the lab needs one to three days to say which antibiotics will work —
so the first prescription is a guess, and that guess fails in up to a third of ICU
patients. The bacterium's genome is available hours earlier. The question is whether
we can read it — honestly."

**[Shot 2 · 0:18]** "Genome Firewall is a five-stage pipeline. NCBI's AMRFinderPlus —
the same tool public-health agencies run — turns a raw genome into a panel of about
nine hundred resistance genes and curated point mutations. For each drug, a small
elastic-net logistic regression scores that panel, and Platt calibration turns the
score into a probability that means what it says. Then three honesty layers decide
whether we answer at all. And every number we report comes from bacterial lineages
the model never saw in training."

**[Shot 3 · 0:50]** "Why logistic regression, in 2026? Because the data regime demands
it. We have roughly 340 training genomes per drug, dominated by a handful of outbreak
clones. In that regime, a big model doesn't learn resistance biology — it memorizes
clones. Our ciprofloxacin model has exactly eighty nonzero weights out of nine hundred
candidate features. Every one of them can be read and audited — and most are known
resistance mechanisms. Small isn't the limitation here. Small is the control that
keeps the model honest."

**[Shot 4 · 1:25]** "Four design decisions do the real work. One: we split by genetic
group, never at random — genomes are clustered at 99.5% ANI, and headline numbers come
only from clusters held out of training. Two: a no-call band — asymmetric conformal
prediction, tuned so that 'likely to work' must clear a stricter bar than 'likely to
fail', because a false 'work' is the dangerous error — plus a hard override that
refuses any genome farther from training data than anything we were ever right about.
Three: a callability gate — before we trust 'no mutation found', we verify the drug's
target loci were actually sequenced. Four: evidence is decoupled from the model — the
report separates curated genetic determinants from statistical associations, so a
mechanism-free prediction is visibly weaker."

**[Shot 5 · 2:25]** "We engineered against the three ways systems like this mislead.
Homolog leakage — near-identical strains on both sides of a random split — is why
published accuracy collapses on new lineages; our grouped splits make that collapse
visible instead of hiding it. False confidence is answered by calibration and
abstention — and cefotaxime is the proof: the held-out clone carries resistance
alleles absent from all training lineages, resistant-recall drops to 0.39, and the
system abstains on 58 percent of cases rather than guess. And the absent-target
false-susceptible — 'no gene found' reported as 'susceptible' — is exactly what the
callability gate forbids."

**[Shot 6 · 2:50]** "The result: on lineages it never saw, Genome Firewall declines to
answer on about six in ten genomes — and on the four in ten it does call, it is right
about nine times out of ten. That is what honest AMR prediction looks like."

<!--V3-SLOT: shot 6 close — v2 says "six in ten abstained, nine in ten correct when called" (mean no-call 0.60, mean accuracy-when-called 0.92 across the 5 drugs). Recompute both means from reports/metrics.json if v3 ships.-->

---

## Video 2 — demo (~2:00)

Single continuous screen recording of the **static demo app** (HF Space; local
fallback `http://127.0.0.1:8791`). No cuts needed except the overlays noted below.
Rehearse the click path once before recording: story buttons → evidence drawer →
Trust tab. If the Space is degraded, record the Colab notebook
(`notebooks/GenomeFirewall_Demo.ipynb`) running the same three stories as fallback.

### Shot list

| # | Time | Shot | Asset / screen |
|---|---|---|---|
| 1 | 0:00–0:08 | App opens on the report tab; click the **refusal** story button (`562.100124`). Verdict table renders: all five drugs gray **NO-CALL** | Static app `#tab-report` → story buttons → verdict table |
| 2 | 0:08–0:20 | Zoom on the ciprofloxacin row: score **0.088**, verdict NO-CALL (reason: abstention band). Text overlay: *"naive 0.5-threshold caller: 0.088 < 0.5 → 'likely to work' — lab truth: RESISTANT"* | Verdict table row + overlay (edit in post, or browser zoom) |
| 3 | 0:20–0:40 | Click the **resistant** story button (`562.140931`). Ciprofloxacin row: **LIKELY TO FAIL**, score 0.979. Open the ciprofloxacin **evidence drawer**: category (i) curated determinants (gyrA S83L + D87N, parC S80I + E84V, parE I529L, with tiers and citation families), category (ii) statistical associations labeled mechanism-free | Static app `#tab-report` → evidence drawer |
| 4 | 0:40–0:55 | Highlight the frequency-framed confidence line under the ciprofloxacin verdict: *"among held-out genomes scoring 0.9–1.0, 99% were resistant (n=116)"* | Evidence drawer / verdict confidence line (from `reports/metrics.json` reliability bins) |
| 5 | 0:55–1:15 | Click the **susceptible** story button (`562.100280`). Verdict: **LIKELY TO WORK** on 5/5 drugs. Open the **callability-gate panel** for ciprofloxacin: gyrA / parC / parE = wild-type-intact (k-mer-verified sequenced) | Static app `#tab-report` → gate panel |
| 6 | 1:15–1:35 | Switch to the **Trust tab**. Show the per-drug scoreboard (balanced accuracy on held-out genetic groups), then the accuracy-vs-coverage chart | Static app `#tab-trust` → `#trust-numbers`, `#cov-chart` |
| 7 | 1:35–1:50 | Scroll the threat-model table ("How this model can mislead — and what we did about it", 4 rows) | Static app `#tab-trust` → threat-model table |
| 8 | 1:50–2:00 | End on the disclaimer banner (bottom of every view) | Static app banner |

<!--V3-SLOT: shot 6 — the scoreboard reads from reports/metrics.json at render time; if v3 ships after a cache rebuild + Space redeploy, re-record this shot. Narration numbers for shot 6 are v2 below.-->

### Narration (exact text)

**[Shots 1–2 · 0:00, cold open]** "This is E. coli genome 562.100124 — from a lineage
the model never saw in training. A naive caller reads its ciprofloxacin score of 0.088
and says 'likely to work'. The lab truth is: resistant. Genome Firewall says something
different: nothing. Five drugs, five no-calls. That refusal is not the failure. That
refusal is the product."

**[Shot 3 · 0:20]** "Here is the opposite case. Genome 562.140931 — also from a
held-out lineage. Ciprofloxacin: likely to fail, calibrated score 0.979. Open the
evidence drawer: category one is mechanism — point mutations in gyrA, parC and parE,
the classic quinolone-resistance mutations, each cited to the AMRFinderPlus and
ResFinder catalogs. Category two is statistics — the model's strongest features,
explicitly labeled as associations, not mechanism."

**[Shot 4 · 0:40]** "And confidence is never a bare number: among held-out genomes
that scored in this bin, 99 percent were truly resistant. You always see the base rate
behind the claim."

**[Shot 5 · 0:55]** "The third case: 562.100280, susceptible in the lab to all five
drugs. A 'likely to work' from us is not the absence of evidence — the callability
gate first verifies that the gyrA, parC and parE target loci were actually sequenced,
and read as wild-type. Only then do we say: likely to work — five for five."

**[Shot 6 · 1:15]** "The scoreboard, on genetic groups never seen in training:
ciprofloxacin 0.956 balanced accuracy, trimethoprim-sulfamethoxazole 0.906,
gentamicin 0.877, ampicillin 0.838, cefotaxime 0.694 — where the system detects its
own weakness and abstains instead of guessing. And this curve is the contract:
accuracy against coverage. We answer about forty percent of unseen genomes — at about
ninety-two percent accuracy. The rest go to the lab — which is where uncertain cases
always belonged."

**[Shot 7 · 1:35]** "Every failure mode we could name is engineered against: homolog
leakage, false confidence, spurious correlation, and the absent-target
false-susceptible — each with a countermeasure that is built, not promised."

**[Shot 8 · 1:50]** "Every screen carries it: research prototype — confirm all results
with standard laboratory susceptibility testing. Genome Firewall doesn't replace the
lab. It tells you tonight which antibiotic not to start with."

<!--V3-SLOT: shot 6 narration — v2 balanced accuracies 0.956 / 0.906 / 0.877 / 0.838 / 0.694 and "~40% coverage at ~92% accuracy". Update from reports/metrics.json heldout_group if v3 ships; keep the same sentence rhythm.-->

---

## Video 3 — group intro (~20 s)

Mostly for the team to own. Skeleton only:

| Time | Shot | Content |
|---|---|---|
| 0:00–0:05 | All members on camera (grid or single frame) | "We're [team name], and we built Genome Firewall." |
| 0:05–0:15 | Each member, one line, name on lower third | Name + role: data & labels · modeling & evaluation · demo & deployment (adjust to actual split) |
| 0:15–0:20 | All on camera | "Genome Firewall — an honest AI defense against superbugs." Cut to project logo/title card |

Recording notes: same 16:9 1080p MP4/H.264 settings as V1–V2; natural light or one
lamp, quiet room, phone-mic is fine at this length; one take per line, pick best.
