# 08 — Responsibility & Biosecurity Framing (Genome Firewall)

Research memo for the "Genome Firewall" challenge team (Hack-Nation 6th Global AI Hackathon).
Prepared 2026-07-18 from public primary sources; all claims carry inline URLs. Status caveats noted where policy is in flux.

**Bottom line:** Per-antibiotic AST prediction from a finished genome is squarely *defensive, phenotype-level* work — the same class as NCBI's AMRFinderPlus and DTU's ResFinder, run by public-health agencies themselves. The credible "strictly defensive" story is not a pledge of virtue; it is (a) a narrow capability claim (prediction only, zero design output), (b) UI text borrowed verbatim from FDA-cleared diagnostic labeling and FDA CDS guidance, and (c) one threat-model slide showing the four ways the model can mislead, each anchored to a published failure. Build the framing *into the demo's evidence panel* rather than as a separate ethics deck.

**48-hour triage:**

| Build this (hours well spent) | Ignore this (diminishing returns) |
|---|---|
| 1 disclaimer block adapted from BioFire's FDA labeling (§2.1) + "confirm with standard lab testing" banner | Reading the full DURC/PEPP policy text — it's being rewritten; cite status at headline level only (§1.2) |
| 1 threat-model slide, 4 quadrants, each with a citation (§4) | Deep dives into frontier-model bio-uplift evals — one sentence citing Anthropic/OpenAI is enough (§1.3) |
| Evidence-by-ID panel + no-call visibility in the demo (instantiates FDA Criterion 4 "independent review of basis", §3.2) | Any attempt to make the demo look "clinically usable" — FDA's Jan 2026 guidance says genomic-pattern AST software is a *device*; stay loudly non-clinical (§3.1) |
| A 3-sentence "scope & red lines" statement in the README + demo footer (§5.2) | LLM-generated free-text clinical recommendations, sequence output of any kind, mutation discussion (§5.1) |

---

## 1. Dual-use / biosecurity norms: where the line is

### 1.1 The problem space is mainstream public health, not fringe

- WHO: bacterial AMR was associated with **>4.7 million deaths in 2021**; **1 in 6** lab-confirmed bacterial infections worldwide were antibiotic-resistant in 2023; resistance rose in >40% of monitored pathogen–drug combinations 2018–2023. WHO's Global Action Plan on AMR (2026–2036) explicitly calls to "accelerate antimicrobial resistance research and innovation" and strengthen surveillance. [WHO AMR fact sheet](https://www.who.int/news-room/fact-sheets/detail/antimicrobial-resistance)
- GRAM study (Lancet 2024 update): **1.27 M deaths attributable / 4.95 M associated** with bacterial AMR in 2019, with forecasts to 2050. [Lancet 2024](https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(24)01867-1/fulltext)
- CDC 2019 AR Threats Report: **>2.8 M resistant infections and >35,000 deaths/year** in the US. [CDC](https://www.cdc.gov/antimicrobial-resistance/data-research/threats/index.html) / [report PDF](https://www.cdc.gov/antimicrobial-resistance/media/pdfs/2019-ar-threats-report-508.pdf)
- Genotype→AST prediction is already a government-run public service: NCBI operates [AMRFinderPlus](https://www.ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance/AMRFinder/) and hosts ML-based AST research ([Davis et al. 2016, PATRIC/RAST, Sci Rep 6:27930](https://doi.org/10.1038/srep27930)); DTU hosts ResFinder/PointFinder. The challenge's task is a *benchmarked, calibrated* version of an existing, sanctioned capability.

### 1.2 The governance frameworks (and their current flux)

- **US dual-use oversight (DURC/PEPP).** The May 2024 *USG Policy for Oversight of DURC and Pathogens with Enhanced Pandemic Potential* covered research "reasonably anticipated" to enhance transmissibility/virulence or disrupt countermeasures, and suggested *voluntary* review for **"In Silico Models and Computational Approaches […] directly enabling the design of a PEPP or a novel biological agent or toxin"** ([Frontiers dual-use AI-bio review, 2026](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2026.1832974/full)). On 2025-05-05, EO 14292 paused "dangerous gain-of-function" research funding and ordered the 2024 policy revised/replaced; NIH rescinded its implementation notice (NOT-OD-25-112) ([NIH OSP](https://osp.od.nih.gov/white-house-issues-executive-order-on-improving-the-safety-and-security-of-biological-research/), [NIH Nexus](https://nexus.od.nih.gov/all/2025/01/14/nih-implementation-of-the-u-s-government-policy-for-oversight-of-dual-use-research-of-concern-durc-and-pathogens-with-enhanced-pandemic-potential-pepp/)). A Sept 2025 "Policy and Guidance for Oversight of DURC-PEPP" circulates via institutional biosafety offices ([example copy](https://offices.vassar.edu/grants/wp-content/uploads/sites/25/2025/09/Policy-and-Guidance-for-Oversight-of-DURC-PEPP-FINAL-Sept-2025-1.pdf)); treat the exact wording as moving. **Takeaway for us:** the regulated category is *enhancement/design of pathogens* — phenotype *prediction* on natural genomes is not DURC territory, and even the in-silico clause targeted models "directly enabling design."
- **Nucleic-acid synthesis screening.** The concrete chokepoint norm: 2023 HHS Screening Framework Guidance → 2024 OSTP Framework for Nucleic Acid Synthesis Screening (providers screen orders for Sequences of Concern, verify customers) → 2025 EO directing it be strengthened ([policy evolution review](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2026.1827740/full); [IGSC Harmonized Screening Protocol mentioned here](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2026.1819510/full)). **Takeaway:** the field's red line is *physical constructability* — our system must never emit sequences, constructs, or design instructions.
- **Frontier-AI bio frameworks** (useful as *vocabulary*, one slide mention max):
  - OpenAI Preparedness Framework (v2, 2025): biology is a tracked category; "High" = "meaningful counterfactual uplift to novice actors that allows them to create known biological threats" ([framework page](https://openai.com/preparedness/); definition quoted in [OpenAI's gpt-oss safety analysis](https://arxiv.org/html/2508.03153v1)).
  - Anthropic Responsible Scaling Policy: ASL tiers modeled on biosafety levels; **first-ever ASL-3 activation (May 2025, Claude Opus 4)** was precautionary and driven by CBRN-capability uncertainty; deployment measures are "narrowly focused on preventing… extended, end-to-end CBRN workflows… additive to what is already possible without large language models," with vetted exemptions for dual-use science users ([Anthropic announcement](https://www.anthropic.com/news/activating-asl3-protections)).
  - Google DeepMind's Frontier Safety Framework tracks CBRN "critical capability levels" (referenced in [arXiv:2601.11516](https://arxiv.org/html/2601.11516v2)).
  - **Takeaway:** the accepted risk unit across all three is *uplift toward weaponization workflows* — nothing in AST prediction approaches it. Citing these shows we know the landscape; dwelling on them invites judges to think about misuse we never enabled.

### 1.3 A usable "line" test (for the deck and for internal decisions)

Three questions; any "yes" = stop and redesign:

1. **Design test:** Does any output propose, rank, or optimize a genetic change (mutation, gene, construct, protocol)? — If yes, that's the DURC-adjacent side. Our system outputs *predictions about existing genomes only*.
2. **Uplift test:** Does the output give a non-expert something they couldn't already get from AMRFinderPlus/ResFinder/CARD plus public dashboards? — Our delta is calibration/honesty (no-call, grouped evaluation), not new biological capability.
3. **Countermeasure test:** Could the output help evade a diagnostic, a synthesis screen, or a therapy? — We never discuss how resistance *could be engineered*; we report what *is observed*.

---

## 2. How real clinical-genomics products/papers phrase honesty (steal this wording)

### 2.1 BioFire FilmArray Pneumonia Panel — FDA-cleared labeling (best template)

From the FDA 510(k) summary/labeling ([K212727, accessdata.fda.gov](https://www.accessdata.fda.gov/cdrh_docs/pdf21/K212727.pdf)):

> "Negative results for these antimicrobial resistance gene assays do not indicate susceptibility to corresponding classes of antimicrobials, as multiple mechanisms of antimicrobial resistance exist. […] A 'Not Detected' result for a genetic marker of antimicrobial resistance does not indicate susceptibility to associated antimicrobial drugs or drug classes. […] Culture is required to obtain isolates for antimicrobial susceptibility testing, and FilmArray Pneumonia Panel results should be used in conjunction with culture results for determination of bacterial susceptibility or resistance."

This is the exact rhetorical shape the challenge demands: *absence-of-marker ≠ susceptible* + *defer to phenotypic testing*. Adapt directly (§2.4).

### 2.2 APHL TB WGS drug-susceptibility reporting FAQ — report-phrase conventions

US public-health labs distinguish two "negative" wordings ([APHL MDL TB WGS DST FAQs PDF](https://www.aphl.org/programs/infectious_disease/tuberculosis/Documents/MDL%20TB%20WGS%20DST%20FAQs.pdf)):

> "'No mutations detected': when the gene does not have any mutations (i.e. 'wild-type', WT). 'No high confidence mutations detected': gene contains mutations that are not likely to cause resistance [synonymous; WHO-catalogue neutral mutations; promoter mutations not covered by expert rules]."

Lesson: a defensible "susceptible-side" call requires *positive evidence of the interrogated target* (wild-type allele actually observed), and unknown variants degrade the call to a weaker statement — this is precisely the challenge's "molecular-target-presence gate" and our no-call tier.

### 2.3 Tool documentation — AMRFinderPlus

NCBI's own docs encode the same discipline ([Running AMRFinderPlus wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)):

> "`--mutation_all <point_mut_report>` […] allows you to distinguish between called point mutations that were the sensitive variant and the point mutations that could not be called because the sequence was not found."
> "For point mutations the reference is the sensitive 'wild-type' allele."

I.e., the reference implementation ships three states — resistant variant / confirmed-sensitive variant / **not callable** — which maps 1:1 onto the challenge's likely-to-fail / likely-to-work / **no-call**.

### 2.4 Review-literature framing (for the "limitations" slide/section)

- [Kim et al. 2022, *Clin Microbiol Rev* 35:e00179-21](https://doi.org/10.1128/cmr.00179-21) — the standard citation that AMR ML is *not clinically deployable* today: models are species- and drug-specific, phenotype labels depend on breakpoint choice, and clinical use would require regulatory-grade validation.
- [Hicks et al. 2019, *PLoS Comput Biol* 15(9):e1007349](https://doi.org/10.1371/journal.pcbi.1007349) — quotable honest-generalization language: model performance "varies by drug, dataset, resistance metric, and species"; "resistance model performance may be strongly associated with the distributions of both resistance phenotypes and genetic features and thus can be highly population-specific"; AZM balanced accuracy ranged **57–94% across datasets** vs CIP ≥93%.

**Adapted disclaimer block (drop into README + demo footer, edit brackets):**

> This tool is a research demonstration. It predicts antibiotic response from genome sequence using statistical models; it is **not a diagnostic device** and has **not** been validated for patient care. A "likely to work" prediction means only that the model found evidence of a drug's molecular target and no known resistance determinant — **absence of a detected resistance marker does not establish susceptibility**. All predictions must be confirmed with standard laboratory antimicrobial susceptibility testing (e.g., CLSI/EUCAST methods) before any clinical or public-health use. [Model version, training-data snapshot, and grouped-split evaluation results: see METRICS.md.]

---

## 3. Human oversight beyond boilerplate: FDA CDS guidance + WHO

### 3.1 FDA Clinical Decision Support Software guidance — and why it tells us to stay non-clinical

The **final CDS guidance is now the January 2026 revision** (supersedes the Sept 2022 version) ([FDA guidance page](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software); full-text transcript: [Innolitics](https://innolitics.com/articles/fda-guidance-clinical-decision-support-software-2026/)). It interprets the four statutory criteria (FD&C Act §520(o)(1)(E)) for "Non-Device CDS":

- **Criterion 1 (the killer for us):** software that analyzes a medical image, IVD signal, or **"pattern"** stays a *device*. FDA now says explicitly: *"Genetic sequences, including datasets of sequence variants that differ from reference sequences… (such as variant call format files or VCFs), are examples of patterns,"* and *"Software functions that process or analyze the genetic sequence or patterns from an NGS analyzer to identify genetic variants or mutations or their clinical implications or relevance do not meet Criterion 1."* → **A genome→AST predictor marketed for clinical use would be a regulated medical device.** Our demo must therefore never claim or imply clinical use; "research/education only" is the honest and the *regulatorily literate* position.
- **Criterion 3:** Non-device CDS "provides condition-, disease-, and/or patient-specific information and options to an HCP to enhance, inform and/or influence a health care decision; does not provide a specific preventive, diagnostic, or treatment output or directive; and is not intended to replace or direct the HCP's judgment." Even FDA's own antibiotic example ("recommends a specific FDA-approved antibiotic agent… based on symptoms, recent hospitalizations, and previous antibiotic exposure") is non-device only because its inputs are medical information — not genomic patterns.
- **Criterion 4 (the design spec for our demo):** the HCP must be able to **"independently review the basis for such recommendations… so that they do not rely primarily on such recommendations, but rather on their own judgment."** FDA operationalizes this as: state intended user/population; identify required inputs and data-quality requirements; plain-language description of algorithm development and validation ("data relied upon… representative of their patient population… independent development and validation datasets"); and surface "knowns/unknowns" including "missing, corrupted, or unexpected input data values."
- **Automation bias** (named in the guidance): *"the propensity of humans to over-rely on a suggestion from an automated system… errors of commission (following incorrect advice) or omission (failing to act because of not being prompted to do so)."* Time-critical decisions fail Criterion 4 outright.

### 3.2 Turning Criterion 4 into 5 concrete demo features (this is "oversight beyond boilerplate")

1. **Evidence panel by ID:** every prediction shows its basis — AMRFinderPlus hit IDs/alleles, or "statistical association only (no curated marker)" — satisfying "independently review the basis."
2. **No-call as a first-class outcome**, not hidden: unknown targets/alleles force abstention (mirrors the APHL wording discipline, §2.2).
3. **Accuracy-at-coverage curve + reliability plot in the UI:** the user sees *when* the model is trustworthy, countering automation bias with calibrated uncertainty rather than a bare verdict.
4. **Population-shift warning:** "this genome is unlike the training distribution (novel genetic group)" — FDA's "assess whether the data is representative of their patient population" applied to genomes; the organizer's hidden test deliberately includes unseen groups, so show this proudly.
5. **Non-time-critical framing + "confirm with standard lab testing" banner** on every result screen (§2.4 text).

### 3.3 WHO framing (one slide line each)

- WHO *Ethics & Governance of AI for Health* (2021), six principles — the relevant one is **"protect human autonomy": humans must remain in control of health-care systems and medical decisions**; plus transparency/explainability and responsibility/accountability. [WHO publication](https://www.who.int/publications/i/item/9789240029200)
- WHO *Regulatory Considerations on AI for Health* (2023): emphasizes documentation of data provenance, predetermined change control, total-product-lifecycle oversight, and human-in-the-loop for high-risk uses. [WHO IRIS](https://iris.who.int/handle/10665/373421) (both summarized in [WHO's UN CSTD brief](https://unctad.org/system/files/non-official-document/cstd2025-26_ai_c26_who_en.pdf))

---

## 4. Threat-model-of-failure-modes slide (concept + citations)

**Layout:** one slide, 2×2 grid. Each quadrant: *failure story (1 line) → published anchor (1 citation) → our mitigation (1 line)*. Title: **"How this model can mislead — and what we did about it."** This is high-leverage: it converts the judging rubric (honest generalization, calibration, no-call, target gate) into a security-style narrative.

| Quadrant | Failure story | Published anchor | Mitigation in our build |
|---|---|---|---|
| **Homolog leakage** | Random splits put near-identical strains in train and test; the model memorizes clones, not resistance biology, and collapses on unseen lineages. | Data leakage is a named failure mode in biological ML validation: [Walsh et al. 2021, DOME recommendations, *Nat Methods* 18:1122–1127](https://doi.org/10.1038/s41592-021-01205-4); [Bernett et al. 2024, "Guiding questions to avoid data leakage in biological ML", *Nat Methods* 21](https://doi.org/10.1038/s41592-024-02362-y); [Whalen et al. 2022, "Navigating the pitfalls of applying ML in genomics", *Nat Rev Genet* 23:169–181](https://doi.org/10.1038/s41576-021-00434-9). AMR-specific: Hicks et al. 2019 showed classifiers trained without the test population perform **significantly worse** (P<0.0005 in most datasets) — "factors such as population-specific resistance mechanisms… and/or confounding effects may constrain model reliability across populations" ([paper](https://doi.org/10.1371/journal.pcbi.1007349)). | Sequence-homology de-dup before splitting; report metrics only on the organizer's **genetically grouped** splits; treat the hidden unseen groups as the headline number, not the in-distribution one. |
| **False confidence** | A confidently wrong "likely to work" is the most dangerous output; raw ML scores are typically miscalibrated, and users over-trust automated suggestions. | [Van Calster et al. 2019, "Calibration: the Achilles heel of predictive analytics", *BMC Med* 17:230](https://doi.org/10.1186/s12916-019-1466-7) — "poorly calibrated algorithms can be misleading and potentially harmful for clinical decision-making." FDA names **automation bias** in the CDS guidance (§3.1). | Held-out **calibration split**; report Brier + reliability plot per drug; conformal/abstention layer so confidence below threshold → no-call; never show a probability without its calibration context. |
| **Spurious correlation** | The model latches onto lineage markers or dataset artifacts that correlate with resistance in this sample but encode no mechanism. | Canonical clinical-ML case: [Caruana et al. 2015, *KDD*, pneumonia models learned "asthma ⇒ lower risk"](https://doi.org/10.1145/2783258.2788613) — true in training data (asthmatics got ICU-level care), lethal if deployed. AMR-specific: Hicks et al. 2019 — "a substantial portion of the model may be overfit, or based on confounding factors or noise, rather than biologically-meaningful resistance variants"; sensitivity/specificity ratio tracks NS:S class ratio with **Pearson r>0.98**. Also their RpoB I491F example: a rifampicin-resistance mutation causing commercial-assay failure was <5% of MDR-TB globally but **~30% in Eswatini** — geography-confounded diagnostic performance. | Three-tier evidence labels — (i) curated marker, (ii) **statistical association only**, (iii) no known signal — so a category-(ii) prediction is visibly weaker; grouped evaluation exposes lineage-driven features as failing on unseen groups. |
| **Absent-target false-susceptible** | "No resistance gene found" is reported as "susceptible," including when the drug's target is absent/unknown or the allele couldn't be called. | FDA-cleared labeling: "A 'Not Detected' result for a genetic marker of antimicrobial resistance **does not indicate susceptibility**" ([BioFire K212727](https://www.accessdata.fda.gov/cdrh_docs/pdf21/K212727.pdf)); EUCAST's WGS-AST position report reached the same conclusion for in-silico AST ([Ellington et al. 2017, *Clin Microbiol Infect* 23:2–22](https://doi.org/10.1016/j.cmi.2016.11.012)); AMRFinderPlus itself requires the **sensitive wild-type allele** to be *found* before a sensitive call, and logs uncalled sites separately ([docs](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)). Microbiology floor truth: organisms lacking the target are intrinsically resistant (e.g., mycoplasmas vs β-lactams — no cell wall), which no absence-of-marker test can see. | **Deterministic molecular-target-presence gate**: "likely to work" only when the drug's target/mechanism evidence is present *and* callable; otherwise no-call, never default-susceptible. |

**Presentation tip:** put the absent-target quadrant last and frame it as "the bug we were explicitly asked to design against — here is the industry precedent (FDA labeling) that proves it's the right call."

---

## 5. Demo red lines & a credible "strictly defensive" commitment

### 5.1 Red lines for the demo (hard rules, enforce in code where possible)

1. **No sequence output, ever.** Results are labels, evidence IDs, and plots. No FASTA snippets of resistance alleles, no primers, no constructs. (Synthesis-screening logic: the field's chokepoint is physical constructability — §1.2.)
2. **No mutation-design or engineering language.** The UI and the LLM report writer must not contain phrases like "mutations that would confer," "how to make it resistant," "evade," "enhance." The constrained LLM writer gets a system prompt restricted to: template prose + cited evidence IDs; it must refuse freeform mechanism speculation beyond the curated evidence table. (Mirrors Anthropic's "narrowly targeted" CBRN-deployment philosophy: block the workflow, not the topic — §1.2.)
3. **No clinical directives.** Never "treat with X." Output is "likely to fail / likely to work / no-call" + evidence + the §2.4 disclaimer. (FDA Criterion 3: information and options, not a "specific treatment output or directive" — §3.1.)
4. **No implied novelty of capability.** Say plainly: AMRFinderPlus/ResFinder do marker detection today; our contribution is calibration, honest generalization, and abstention. (Uplift test, §1.3.)
5. **Public data only, attributed.** BV-BRC/PATRIC + organizer data; no patient-identifying metadata displayed.
6. **The "confirm with standard lab testing" banner is on every screen, not a one-time modal** — judges will click around; make the message unmissable.

### 5.2 The commitment statement (paste-ready)

> **Scope & intent.** Genome Firewall is a defensive biosurveillance tool. It predicts, for a fixed panel of already-approved antibiotics, whether an *existing* bacterial genome is likely to respond to treatment, and — just as importantly — when it *cannot say*. It performs phenotype prediction only: it does not propose, rank, or design genetic modifications, and it generates no sequence data, constructs, or protocols. The task it automates — genotype-based antimicrobial-susceptibility screening — is today performed as a public service by NCBI (AMRFinderPlus) and DTU (ResFinder); our contribution is calibrated confidence, honest out-of-group generalization, and a molecular-target gate so that "no marker found" is never sold as "susceptible." Every output carries the instruction to confirm with standard laboratory susceptibility testing. This framing follows WHO's human-autonomy principle for health AI, FDA's clinical decision support criteria, and the biosecurity community's design-vs-prediction boundary.

Credibility comes from *specificity*: naming the boundary (design vs prediction), naming the incumbents (AMRFinderPlus/ResFinder), and naming the external vocabularies (WHO autonomy principle, FDA CDS criteria) — instead of asserting "we are ethical."

---

## Key sources (quick index)

- WHO AMR fact sheet: https://www.who.int/news-room/fact-sheets/detail/antimicrobial-resistance
- GRAM/Lancet 2024: https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(24)01867-1/fulltext
- CDC AR Threats: https://www.cdc.gov/antimicrobial-resistance/data-research/threats/index.html
- DURC/PEPP status: https://osp.od.nih.gov/white-house-issues-executive-order-on-improving-the-safety-and-security-of-biological-research/ ; in-silico clause quoted: https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2026.1832974/full
- Synthesis screening: https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2026.1827740/full
- OpenAI Preparedness: https://openai.com/preparedness/ (threshold quote via https://arxiv.org/html/2508.03153v1)
- Anthropic ASL-3: https://www.anthropic.com/news/activating-asl3-protections
- FDA CDS guidance (Jan 2026): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software ; transcript: https://innolitics.com/articles/fda-guidance-clinical-decision-support-software-2026/
- WHO AI ethics 2021: https://www.who.int/publications/i/item/9789240029200 ; WHO regulatory 2023: https://iris.who.int/handle/10665/373421
- BioFire labeling: https://www.accessdata.fda.gov/cdrh_docs/pdf21/K212727.pdf
- APHL TB WGS FAQ: https://www.aphl.org/programs/infectious_disease/tuberculosis/Documents/MDL%20TB%20WGS%20DST%20FAQs.pdf
- AMRFinderPlus docs: https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus ; paper: https://www.nature.com/articles/s41598-021-91456-0
- Hicks 2019: https://doi.org/10.1371/journal.pcbi.1007349 ; Kim 2022: https://doi.org/10.1128/cmr.00179-21 ; Davis 2016: https://doi.org/10.1038/srep27930
- Leakage: https://doi.org/10.1038/s41592-021-01205-4 (DOME), https://doi.org/10.1038/s41592-024-02362-y (Bernett), https://doi.org/10.1038/s41576-021-00434-9 (Whalen)
- Calibration: https://doi.org/10.1186/s12916-019-1466-7 ; Spurious: https://doi.org/10.1145/2783258.2788613 ; EUCAST WGS-AST: https://doi.org/10.1016/j.cmi.2016.11.012

---

## Self-roast

1. **This may be over-scoped for a 48h hackathon.** The judging rubric rewards metrics (balanced accuracy, F1/AUROC/PR-AUC, Brier, coverage curves), not governance fluency. Every hour spent perfecting FDA/WHO citations is an hour not spent on the conformal layer or the homology de-dup that judges actually score. The honest minimum is: one disclaimer block, one threat-model slide, one red-lines paragraph — roughly §2.4, §4, §5.2 and nothing else. The rest of this memo is ammunition in case a judge probes, but if the team reads it as a to-do list, it will actively hurt the submission.
2. **Citing 2026 regulatory/policy status can backfire.** The FDA CDS guidance was *just* revised (January 2026) and the DURC/PEPP regime is mid-rewrite under EO 14292; a hackathon judge who knows this space could catch any oversimplification ("FDA says X") and read it as compliance theater. There is also a subtle risk in the "this would be a device under FDA criteria" framing: it is accurate and shows literacy, but said carelessly it sounds like the team thinks it built a near-clinical product — inviting clinical-validation questions the demo cannot survive. The safer posture may be to skip regulatory citations in the deck entirely and keep only the BioFire-style disclaimer wording.
3. **Elaborate "strictly defensive" framing can be performative or counterproductive.** AST prediction sits far below any plausible uplift threshold — AMRFinderPlus has been a public NCBI service for years — so a heavy red-lines section risks (a) signaling to judges that the team *worried* this might be dangerous, planting a misuse thought that wasn't there, and (b) looking like ethics-washing if any disclaimer is contradicted by the demo (e.g., a chatty LLM panel that happily discusses resistance mechanisms). A one-paragraph scope statement plus consistent UI behavior is more credible than a manifesto — and the LLM report writer is the single most likely place the framing gets violated in front of judges, so constrain it in code or cut it.
