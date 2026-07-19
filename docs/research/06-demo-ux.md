# Genome Firewall — Research Note 06: Demo & Clinical UX

**Scope:** What existing AMR tools show per prediction, what clinical-decision-support research says about displaying confidence and abstention, Streamlit vs Gradio for the 48h build, a timed demo script that makes the NO-CALL the hero, and what hackathon judges actually remember.
**Bias throughout:** optimize for a 48-hour build and a 3–5 minute judging slot. "Build this" vs "ignore this" called out explicitly.

---

## TL;DR

1. **Every credible AMR tool already practices abstention.** ResFinder only predicts for drugs with elucidated genetics; ARESdb only for trained species–compound pairs; CARD RGI labels weak hits "Loose / discovery only." Your no-call is not a compromise — it is industry-standard behavior, and the demo should say so verbatim. The single strongest framing precedent is **EUCAST's "Area of Technical Uncertainty" (ATU)**: routine lab AST has an official "report as uncertain" mode, with guidance like *"Do not report S unless you have confirmed the result."* ([EUCAST ATU guidance v2, 2020](https://www.eucast.org/fileadmin/eucast/pdf/guidance_documents/Area_of_Technical_Uncertainty_-_guidance_v2_2020.pdf))
2. **Show numbers AND words, never words alone** — verbal probability labels ("likely") are interpreted with extreme variability; users prefer numeric + verbal combined ([J Gen Intern Med 2021 systematic review](https://link.springer.com/content/pdf/10.1007/s11606-021-07050-7.pdf)).
3. **Use Streamlit, not Gradio** — this demo is a multi-state narrative report (upload → QC gate → verdict table → evidence drawer → calibration tab), i.e. "about the data," not "about one model" ([decision rule](https://alijabbary.com/blog/streamlit-vs-gradio-2026)).
4. **The wow moment = a refusal.** Demo three genomes; the third is engineered to sit outside the training distribution, and the system declines to call it while a naive baseline confidently guesses. Judges remember contrast, not features ([JetBrains judging-table notes](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/)).
5. **Mock everything.** Precompute all demo outputs as JSON; the demo never runs the model live. "A broken demo kills even brilliant ideas" ([ainna.ai hackathon guide](https://ainna.ai/resources/faq/winning-hackathon-guide)).

---

## 1. What existing AMR tools show per prediction (UX survey)

### 1.1 ResFinder 4.0 (CGE, DTU) — the in silico antibiogram

- **Flow:** user uploads FASTA/FASTQ and is **prompted to specify the species**; the species determines a species-specific antimicrobial panel for the in silico antibiogram. An "Other" option reports all compounds but carries an explicit warning that intrinsically resistant species may *appear* predicted-susceptible because intrinsic resistance is structural, not gene-borne ([Bortolaia et al. 2020, JAC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).
- **Per-prediction output:** per-compound predicted phenotype (R/S) + the underlying detected genes/point mutations with %identity and %coverage against database entries (defaults ≥80% identity over ≥60% length). Genotype→phenotype tables attach **PubMed IDs, resistance mechanism, and curator notes** (e.g., warnings about inducible expression) to each determinant ([same paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).
- **Withholding by design:** panels only include compounds "for which the tool can actually provide an output"; drugs whose genetic basis is not fully elucidated (e.g., daptomycin in Enterococcus) are **excluded rather than guessed** ([same paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).
- **Trust-through-quality-metrics:** the paper's discordance analysis repeatedly ties wrong calls to low read depth, and the authors conclude *"This shows the importance of visualizing the 'read depth' parameter in the output"* — i.e., surfacing data-quality numbers next to predictions is a credibility feature ([same paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).
- **Usage proof:** >400,000 jobs from >32,000 IPs in 100+ countries ([same paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).
- **Steal this:** species-scoped drug panel; per-drug verdict backed by named evidence rows with identity/coverage numbers; PMID citations behind each gene→drug mapping; explicit "not in panel = not predicted" behavior.

### 1.2 CARD RGI — three evidence tiers as a first-class UX concept

- **Three hit paradigms shown to every user:** **Perfect** = exact match to curated reference/variant (used for clinical surveillance); **Strict** = non-identical match above curated, model-specific bit-score cutoffs with secondary screening for key resistance mutations; **Loose** = outside model cutoffs, for "novel, emergent threats" but explicitly "will also catalog homologous sequences and spurious partial hits" ([CARD RGI via s41598-024-73904-9](https://www.nature.com/articles/s41598-024-73904-9.pdf), [MicroScope RGI docs](https://microscope.readthedocs.io/en/stable/content/compgenomics/card.html)).
- **Web defaults are conservative:** "Perfect and Strict hits only," with a separate "Nudge ≥95% identity Loose hits to Strict" toggle and a sequence-quality selector — i.e., the UI makes the confidence tier a visible, user-controlled choice ([FDA GRAS notice quoting RGI defaults](https://www.fda.gov/media/182785/download?attachment)).
- **Steal this:** the Perfect/Strict/Loose ladder maps almost 1:1 onto the challenge's evidence categories (i) known gene/mutation ≈ Perfect, (ii) statistical association ≈ Strict/Loose, (iii) no signal. Name your badges after this lineage in the demo ("our evidence tiers follow CARD RGI's Perfect/Strict/Loose paradigm") — judges who know the field will recognize the lineage instantly.

### 1.3 BV-BRC / PATRIC — ML predictions embedded in an annotation report

- The Genome Annotation Service (RASTtk pipeline) **projects AMR phenotypes for a select group of genera using AdaBoost machine-learning classifiers** built on k-mers ([BV-BRC annotation protocol](https://www.bv-brc.org/docs/data_protocols/genome_annotation.html); [Davis et al. 2016, Sci Rep](https://www.nature.com/articles/srep27930.pdf)).
- Genome pages present predicted AMR phenotypes as a per-drug table **alongside** the AMR gene evidence from CARD, NCBI AMRFinderPlus, and PATRIC k-mer classifiers — prediction and evidence in one view ([BV-BRC protocol](https://www.bv-brc.org/docs/data_protocols/genome_annotation.html), [usage example in cjm-2023-0117](https://cdnsciencepub.com/doi/pdf/10.1139/cjm-2023-0117)).
- Note for the demo script: BV-BRC's classifier is exactly the "k-mer second evidence stream" in the team's plan sketch — a citable precedent that genotype-agnostic k-mer ML is an accepted complement to gene databases.

### 1.4 ARESdb — cloud pipeline with hard QC gates and FDA-aligned honesty numbers

- **Flow:** FASTQ upload → QC (CheckM completeness ≥90%, contamination ≤10%, quality score ≥50; 44/664 isolates rejected) → assembly → **per species–compound XGBoost 15-mer models** → downloadable S/R report ([Ferreira et al. 2020, JCM](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315026/)).
- **Abstention is structural:** predictions exist only for the 129 trained species–compound pairs; everything else simply isn't reported.
- **Honesty numbers worth reusing on a "why we're careful" slide:** overall 89% categorical agreement, ME 8%, VME 19%; FDA acceptance criteria for AST diagnostics are categorical agreement >90%, VME <1.5%, ME <3% — met simultaneously in only **36/129** pairs even by a mature commercial platform ([same paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315026/)).
- **Steal this:** a visible QC gate as the first screen state ("genome quality: PASS/FAIL — we refuse low-quality input before we refuse uncertain predictions"); FDA error-rate thresholds as the anchor for why false "likely to work" (VME) is the dangerous error.

### 1.5 AMRFinderPlus report format — your evidence table is pre-designed

If organizers ship precomputed AMRFinderPlus results, the TSV already contains everything an evidence drawer needs: `Element symbol`, `Element name`, `Scope` (core = expected to affect resistance / plus = less stringent), `Type`/`Subtype` (AMR vs POINT), `Class`/`Subclass` (**drug-class and often drug-level mapping**), `Method`, `% Coverage of reference`, `% Identity to reference`, `Closest reference accession` ([ncbi/amr wiki — Running AMRFinderPlus](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)).

The `Method` column is a free, citable confidence ladder ([same wiki](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)):

| Method | Meaning | Demo badge |
|---|---|---|
| ALLELE / EXACT | 100% identity over 100% length | strong evidence |
| BLAST | >90% length, >90% identity | solid |
| PARTIAL / PARTIAL_CONTIG_END | 50–90% length | weak / assembly artifact? |
| HMM | family-level hit only | weak |
| INTERNAL_STOP | likely disrupted gene | flag as non-functional |
| POINT | curated point mutation | strong (mutation evidence) |

**Ignore this:** building your own gene→drug mapping table. AMRFinderPlus `Class`/`Subclass` + ResFinder's published genotype→phenotype tables (57 compounds, with PMIDs) already do it ([ResFinder 4.0 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7662176/)).

### 1.6 Cross-tool pattern (the section-1 takeaway)

No credible tool predicts "susceptible" from the mere absence of a resistance marker, and every credible tool has an explicit withholding mechanism (panel scope, trained-pair scope, Loose-tier labeling, QC rejection). The challenge's required molecular-target gate + no-call is therefore **table stakes, not innovation** — and the demo's job is to make that visible and felt, not just implemented.

---

## 2. Clinical decision-support UX: confidence, abstention, and "confirm with lab testing"

### 2.1 Alert fatigue — the reason your no-call must look calm, not alarming

- Medication CDS alert override rates across studies: **46.2%–96.2%**, with 29.4%–100% of overrides classified as appropriate ([Poly et al. 2020 systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7400042/)); a recent review puts the range at 49%–96% with a pooled rate of 96.2% for medication-related alerts ([arXiv 2604.28010](https://arxiv.org/html/2604.28010v1)). Emergency-department studies report 72.8%–93% ([Yoo et al. 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7673981/)).
- Mechanism: excessive false positives erode trust → users override everything, including the true alerts. ICU clinicians state it directly: *"the initial predictions must be accurate, as too many false positives would erode trust in the system and lead to alarm fatigue"* ([JMIR Human Factors 2026, n=14 ICU clinicians](https://humanfactors.jmir.org/2026/1/e81460)).
- **Design consequence for the demo:** the verdict table must not be a wall of red/green alerts. Reserve high-salience color for "likely to fail"; render no-call in a quiet neutral (gray/blue, dashed outline), not a third alarm color. A no-call is a triage outcome ("route to lab"), not a warning.

### 2.2 How clinicians want confidence and uncertainty displayed

From [JMIR Human Factors 2026](https://humanfactors.jmir.org/2026/1/e81460) (qualitative, ICU doctors + nurses) — the most directly applicable design study found:

- **Bullet points, likelihood percentages, and short summaries** beat prose; minimal text, at-a-glance graphics.
- **Show "shades of confidence"**: confidence intervals or graded risk indicators, not just a bare score; one participant literally asked for *"maybe with confidence intervals, not just a score but some idea of how confident the system is."*
- **Traffic-light color coding** with a short "what and why" attached.
- **Detail must be optional and layered**: junior users want explanations; seniors want the headline with detail on demand. Progressive disclosure = default collapsed.
- **State certainty AND bias disclaimers** next to predictions.
- **Caution:** displaying confidence scores improves trust calibration — but people then trust the AI more whenever it shows high confidence, and explanations can inflate trust even when unwarranted. So high-confidence displays must be *calibrated* high confidence (your conformal layer earns the right to show green).
- Accurate predictions matter more than accurate explanations; discrepancies between explanation methods are tolerated if predictions are right. **Don't over-invest in explanation plumbing at the hackathon.**

### 2.3 Numbers + words, never words alone

- Verbal probability labels are interpreted with extreme variability and do not map well onto expert-panel numbers; **most patients/users prefer quantitative information, alone or combined with verbal labels** ([J Gen Intern Med 2021 systematic review of verbal probabilities in health](https://link.springer.com/content/pdf/10.1007/s11606-021-07050-7.pdf)).
- **Pattern to copy:** `LIKELY TO FAIL — 0.93 calibrated confidence (93 in 100 similar isolates)` — word + number + frequency framing in one line. Never show "high confidence" without the number.

### 2.4 The no-call precedent hiding in plain sight: EUCAST ATU

Routine phenotypic AST — the gold standard your demo tells users to confirm with — has an official "we can't call this" zone:

- **Area of Technical Uncertainty (ATU)**: "a warning to laboratory staff that the value is in an area where reproducible interpretation cannot be achieved" ([EUCAST ATU guidance v2 2020](https://www.eucast.org/fileadmin/eucast/pdf/guidance_documents/Area_of_Technical_Uncertainty_-_guidance_v2_2020.pdf)).
- Sanctioned reporting options include: **report as "uncertain" with the interpretation left blank + a comment**; an asterisk/Note instead of S/I/R; or cautious categorization with the uncertainty stated — and **"Do not report S unless you have confirmed the result"** ([EUCAST Breakpoint Tables v12.0](https://www.eucast.org/fileadmin/src/media/PDFs/EUCAST_files/Breakpoint_tables/v_12.0_Breakpoint_Tables.pdf)).
- **Demo line, ready to use:** *"The 100-year-old gold standard has an official 'uncertain' zone. We simply gave our model the same professional privilege — and the same obligation to send uncertain cases to the lab."* This reframes no-call from ML weakness to laboratory medicine orthodoxy.

### 2.5 Plain-language "confirm with lab testing" patterns

- Regulator-tested phrasing exists in direct-to-consumer genetic testing: **"Results should be confirmed in a clinical setting before taking any medical action"** (FDA-context disclaimer dissected in [PMC7010426](https://pmc.ncbi.nlm.nih.gov/articles/PMC7010426/)).
- Diagnostic-report conventions worth copying: pair the confirmation instruction with the *reason* and the *action*, e.g. EarlyTect's "A positive result is not confirmatory evidence… Patients with a positive result should be referred for diagnostic cystoscopy" ([Promis DX report language](https://www.promisdx.com/?page_id=7055)).
- **Recommended footer for every screen and the exported PDF** (short enough to actually be read):
  > **Research prototype — not a diagnostic device.** Predictions are statistical, from genome sequence only. Confirm all results with standard antimicrobial susceptibility testing before any clinical decision.
- Per-verdict microcopy:
  - Likely to fail: "Genomic evidence suggests this antibiotic may fail. Confirm with AST."
  - Likely to work: "No resistance signal detected AND drug target present. This is not a susceptibility result — confirm with AST."
  - No-call: "Insufficient genomic evidence to call. Standard lab AST required — this is the intended path, not an error."

---

## 3. Streamlit vs Gradio in 2026 — verdict for this build

**Verdict: Streamlit.** The widely cited 2026 decision rule: *if the app is about one model → Gradio; if it's about the data/narrative → Streamlit* ([alijabbary.com, June 2026](https://alijabbary.com/blog/streamlit-vs-gradio-2026); [DataBrain 2026 guide](https://www.usedatabrain.com/how-to/create-python-dashboard) gives Streamlit a 1–3 day ship time vs Gradio's 1–2 days but notes Gradio "breaks" on anything not shaped like a model demo — "no real grid layout, sparse chart support"). Genome Firewall's demo is a **multi-state report** — upload/QC state, per-drug verdict table, expandable evidence rows, calibration tab, coverage-vs-accuracy chart — squarely dashboard-shaped.

| Factor | Streamlit | Gradio | Winner here |
|---|---|---|---|
| Verdict table + evidence badges + tabs | native (`st.dataframe`, `st.tabs`, columns) | possible via Blocks, awkward | **Streamlit** |
| Reliability/coverage plots | native chart helpers + Plotly | sparse chart support | **Streamlit** |
| Wrap-one-function demo | more code | `gr.Interface` in ~10 lines | Gradio (not our shape) |
| Clickable example inputs | manual | `examples=` built-in | Gradio (replicate with `st.button` presets) |
| Auto API endpoint | no | yes | irrelevant for judging |
| Free hosting | Community Cloud | HF Spaces | tie |
| Ecosystem signal (2026-06) | 45k stars, 5.2M weekly PyPI downloads | 43k stars, 3.0M weekly | slight Streamlit ([modern-datatools](https://www.modern-datatools.com/compare/streamlit-vs-gradio-vs-dash)) |

Concrete Streamlit build kit (all verified in [current docs](https://docs.streamlit.io/develop/api-reference/status)):

- **Three-state verdict rows:** `st.error` / `st.success` for fail/work, `st.info` (or a gray custom container) for no-call; `st.status` for the pipeline run ("QC → evidence scan → gate check → calibrated call").
- **Progressive disclosure:** `st.expander` per drug row for the evidence drawer (gene table + %identity + PMIDs + association stats).
- **Speed:** `@st.cache_data` on everything; **precompute demo outputs to JSON and load those** — never run inference during judging.
- **Polish in minutes:** `st.metric` for headline stats (coverage %, Brier score), `st.columns` for the drug-panel grid, `st.tabs` for Report / Evidence / Calibration / Threat-model.

**Ignore this:** Gradio's auto-API, HF Spaces deployment, real-time streaming, custom CSS theming, authentication. A local Streamlit run with a recorded backup video beats a deployed app that hiccups on venue Wi-Fi.

---

## 4. Demo script (3.5–4 min) — the NO-CALL as the product's spine

**Core trick:** three pre-loaded genomes, three contrasting outcomes, one engineered refusal. Everything precomputed; the "run" is theater over cached JSON ([mock-everything advice](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/)).

**0:00–0:30 — Problem, felt not stated.** "Empiric antibiotic therapy fails 10–39% of ICU patients because resistance is invisible at prescription time ([ARESdb paper background](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315026/)). Genomes can predict it — but a wrong 'this will work' kills. We built a system whose proudest feature is knowing when *not* to answer."

**0:30–1:00 — Screen state 1: Upload + QC gate.** Drop a FASTA → `st.status` walks QC → evidence scan → target gate → calibrated call. Call out: "Step one is a quality gate — like ARESdb, we reject bad genomes before we ever make a prediction ([QC precedent](https://pmc.ncbi.nlm.nih.gov/articles/PMC7315026/))."

**1:00–1:45 — Screen state 2: Genome A, the textbook resistant.** Verdict table: 3–5 drugs, one red `LIKELY TO FAIL — 0.97`. Expand the evidence drawer: `blaCTX-M-15 — ALLELE match, 100% identity / 100% coverage — PMID citation`. Narrate the badge ladder: "Evidence tier 1: a known gene, cited. Tier 2 would be statistical association only, labeled as such. No hidden mush." (This is CARD RGI's Perfect/Strict/Loose lineage — [source](https://www.nature.com/articles/s41598-024-73904-9.pdf).)

**1:45–2:30 — Screen state 3: Genome B, the honest "likely to work."** Green verdict — then immediately show **why**: the molecular-target gate panel: "We never infer 'works' from absence of resistance genes. This call required (a) no resistance marker, (b) the drug's molecular target present and intact, (c) calibrated confidence ≥ threshold. Absence of evidence is not evidence of absence — that's a rule in our code, not a slogan."

**2:30–3:30 — THE MOMENT — Screen state 4: Genome C, the refusal.** Upload a genome from a held-out phylogenetic group (or with the drug target absent/atypical — exactly the case the hidden test set is designed to contain). The row renders gray: `NO-CALL — outside reliable evidence`. Now the pivot: "Every other tool you've seen today will give you an answer for this genome. Ours refuses — and it's *right* to." Reveal the comparison: naive always-answer baseline vs Genome Firewall on held-out groups, **accuracy-at-coverage curve**: "At 100% coverage the baseline is X% balanced accuracy. We answer 80% of cases — and on those, we're at Y%. The 20% we decline are exactly the ones it gets wrong." Then the ATU closer: "The 100-year-old gold standard has an official 'uncertain' zone — EUCAST's Area of Technical Uncertainty, where labs are told *do not report S unless confirmed* ([EUCAST](https://www.eucast.org/fileadmin/eucast/pdf/guidance_documents/Area_of_Technical_Uncertainty_-_guidance_v2_2020.pdf)). We gave our model the same professional privilege."

**3:30–4:00 — Screen state 5: Trust tab + disclaimer.** Reliability plot + per-drug Brier scores + de-duplication-by-homology one-liner ("train/test split by genetic group, so our numbers survive unseen lineages"). End on the footer every screen already carries: *"Research prototype — confirm all results with standard AST."* Closing line: "A system that says 'I don't know' on cue is the one you can believe when it says 'I do.'"

**Fallback plan (do all three):** (a) pre-recorded screen-capture video of the exact same run; (b) static screenshots in the deck in the same order; (c) the app runs fully offline from cached JSON. Demo failure is the top project-killer ([ainna.ai](https://ainna.ai/resources/faq/winning-hackathon-guide)).

**Build this:** the five screen states above, the coverage-vs-accuracy chart, the ATU quote, the footer.
**Ignore this:** live model inference in the demo, user accounts, PDF export polish, LLM-generated narrative *during* judging (if the LLM report writer is shown at all, pre-generate its output and scroll it).

---

## 5. What hackathon judges remember (pattern survey)

From judges and winner writeups ([JetBrains judging-table notes, June 2026](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/); [Music Hackspace pitch guide](https://musichackspace.org/blog/hackathon-presentation-tips); [ainna.ai](https://ainna.ai/resources/faq/winning-hackathon-guide); [Devpost video tips](https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video)):

1. **"A strong project with a confusing demo loses to a simpler project that the judges understand."** Judges see you for 3–5 minutes; they cannot evaluate your code — only the demo and the story.
2. **Problem first, always.** Every judge in the JetBrains panel said a version of it: make the judges *feel* the problem ("share your frustration") before showing anything.
3. **Something working within ~90 seconds.** The demo *is* the pitch; one clear "oh, that's possible now" moment beats a feature tour. For us: the refusal moment is that moment — one wow, not five.
4. **Scope to one flow.** "If the demo runs long, that's not a pacing problem — it's a scope problem." Five verdict-table features = cut to three genomes and one contrast.
5. **Mock everything.** Pre-fill forms, mock slow calls, remove every place the demo can stall. Honesty about what works reads as confidence, not weakness — which conveniently aligns with the entire Genome Firewall thesis.
6. **Polish the visible 20%.** [One analysis of winning patterns](https://aitmpl.com/blog/hackathon-ai-strategist-agent/): "Polish the visible 20%, skip the invisible 80% — perception of completeness matters more than actual completeness." For us: the verdict table, evidence drawer, and coverage chart get the polish; the model card stays a plain text file.
7. **Rehearse and time it.** Teams that practiced look like they practiced; your best speaker presents ([Music Hackspace](https://musichackspace.org/blog/hackathon-presentation-tips): reserve ~2 hours for presentation prep; [ainna.ai](https://ainna.ai/resources/faq/winning-hackathon-guide): allocate ≥20% of total hackathon time to the pitch).
8. **Event context:** Hack-Nation is an MIT-rooted, high-production global event (2026 edition: $30k+ prize pool, virtual + in-person, sponsor/corporate tracks, ~24–48h builds) ([opportunitiesforyouth.org](https://opportunitiesforyouth.org/2026/04/02/hack-nation-global-ai-hackathon-2026-build-innovate-and-compete-for-30000-in-prizes/), [techpression.com](https://techpression.com/applications-open-for-hack-nation-global-ai-hackathon-2026-with-30000-prize-pool/)). Expect judges from OpenAI/industry: they will have seen a hundred confident demos that day; the *calibrated* one is the differentiator. Tie the closer to the judging rubric explicitly: "hidden-test generalization, calibration, and coverage-aware accuracy are exactly what we demoed."

---

## Copy deck (strings ready to paste)

- **Footer (every screen):** "Research prototype — not a diagnostic device. Predictions are statistical, from genome sequence only. Confirm all results with standard antimicrobial susceptibility testing before any clinical decision." (Pattern: [23andMe/FDA disclaimer](https://pmc.ncbi.nlm.nih.gov/articles/PMC7010426/))
- **Verdict labels:** `LIKELY TO FAIL` / `LIKELY TO WORK` / `NO-CALL — LAB TEST REQUIRED`, each followed by `— 0.XX calibrated confidence` where applicable ([numbers+words evidence](https://link.springer.com/content/pdf/10.1007/s11606-021-07050-7.pdf)).
- **Evidence badges:** `[TIER 1 · KNOWN GENE]` blaCTX-M-15 · ALLELE 100%/100% · [PMID]; `[TIER 2 · STATISTICAL ASSOCIATION]` k-mer cluster · χ² p=… · n=…; `[TIER 3 · NO KNOWN SIGNAL]`. (Lineage: [CARD RGI Perfect/Strict/Loose](https://www.nature.com/articles/s41598-024-73904-9.pdf).)
- **Gate panel:** "Target-presence gate: PASS — molecular target of {drug} detected and intact. A 'likely to work' call is never issued from absence of resistance markers alone."
- **No-call row:** "Insufficient genomic evidence — this genome differs from training data in ways we can measure. Standard lab AST is the intended path, not a fallback." (Precedent: [EUCAST ATU](https://www.eucast.org/fileadmin/eucast/pdf/guidance_documents/Area_of_Technical_Uncertainty_-_guidance_v2_2020.pdf).)

---

## Self-roast

1. **The "refusal as wow moment" could read as a product that doesn't work.** The entire script rests on judges interpreting the no-call as sophistication rather than failure. If the pivot is fumbled — wrong audience, rushed timing, no baseline contrast on screen — the memorable thing becomes "the demo where it shrugged." The ATU/EUCAST analogy also presumes judges with enough clinical-lab context to find it resonant; AI-industry judges may not know or care what EUCAST is. Mitigation: the accuracy-at-coverage curve (a quantitative, field-agnostic artifact) must carry the moment, with ATU as garnish, not the main course — but if the curve's numbers are unimpressive, the whole spine collapses.
2. **Streamlit may be the wrong call for *this* team.** The recommendation is genre-logic ("dashboard-shaped → Streamlit"), not measurement. If the team's strongest demo instinct is a single input→report flow, Gradio's `Interface` + `examples=` is genuinely faster, and an hour lost wrestling Streamlit's re-run model at 3 a.m. costs more than the layout polish buys. Worse: my "mock everything, run from cached JSON" advice, if taken literally, risks a demo that can't handle a judge's reasonable request ("try *this* genome from your own test set") — over-scripting can look like hiding. A halfway option (cached by default, one real fast path for a judge-supplied input) is safer than pure theater.
3. **The clinical-UX citations may be over-weighted for a hackathon.** Alert-fatigue override rates and ICU XAI interviews concern deployed hospital systems, not a 4-minute judging slot; a judge scoring "technical execution + innovation" may experience the disclaimer footer, three-tier badges, and calibration tab as *bureaucracy that ate the demo*. There is a real tension: every minute spent making the no-call look clinically responsible is a minute not spent on a flashier technical flex (live LLM report, interactive genome browser). The bet that restraint reads as maturity is evidence-informed but still a bet — at some hackathons, with some panels, the team that demos a working conformal-prediction dial will beat the team that demos good manners.
