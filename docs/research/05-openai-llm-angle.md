# 05 — OpenAI / LLM Angle for the Genome Firewall Challenge

Research date: 2026-07-18. All pricing and API facts verified against official OpenAI pages on this date; event facts against the official Hack-Nation site.

## ⚠️ First: two corrections to the team's operating assumptions

1. **The event is 24 hours, not ~48.** The official Hack-Nation schedule is: kick-off Sat 12:00 PM ET, hacking begins ~12:15–1:00 PM Sat, **submission deadline Sunday 9:00 AM ET**. Finalist pitches (3 min each) happen a week later, Sat July 25, and only the top 16 teams pitch. Sources: [hack-nation.ai/hackathon](https://hack-nation.ai/hackathon), [projects.hack-nation.ai](https://projects.hack-nation.ai/). Every hour budget below assumes ~20 usable hours.
2. **Submission is an MP4 video + project page, and the final round is a 3-minute pitch.** Video must be MP4 with H.264 codec (other formats are blocked on upload). Projects can be edited/resubmitted freely until the deadline. Source: [projects.hack-nation.ai FAQ](https://projects.hack-nation.ai/). This means the LLM's highest-leverage output may be *the pitch and demo narrative*, not in-app text.

---

## Q1 — Highest-leverage uses of OpenAI models, ranked by demo impact per hour

| Rank | Use | Effort | Why |
|---|---|---|---|
| 1 | **Grounded report writer with citation-by-ID + schema-enforced disclaimer** | 3–4 h | This is the single artifact that makes the challenge's core requirements *visible*: evidence categories (i)/(ii)/(iii), calibrated no-calls, the molecular-target gate, and the mandatory "confirm with standard lab testing" line. Judges see a clinician-style one-pager that cites its evidence — that reads as technical maturity. |
| 2 | **LLM-assisted pitch + demo narrative** (3-min finalist script, MP4 voiceover script, README, judge FAQ) | 1–2 h | The final round is a 3-min pitch; Hack-Nation's own site hosts a "How to Pitch Like a Winner" guide from a past challenge winner, and its Venture Track selects teams on "technical execution **and venture potential**" ([hack-nation.ai/venture-track](https://hack-nation.ai/venture-track)). Use the strongest model available to draft, then humans edit. |
| 3 | **"Ask the report" Q&A over the structured report JSON** | 2–3 h, only after #1 ships | Judges love interactive demos, and a bounded Q&A ("why did you no-call ciprofloxacin on genome 1142?") shows the evidence plumbing works. No vector DB needed — the whole evidence bundle is 2–4k tokens and goes straight into the prompt (RAG-lite). Mitigate live-demo risk with pre-seeded question buttons and cached fallbacks. |
| 4 | **Honest NL explanation of feature importance** | 0 h standalone — fold into #1 as template rules | As free-form LLM generation this is the top hallucination/causation risk (see Q2). As *constrained prose* (the model may only restate signed coefficients/conformal set sizes already in the evidence bundle, with banned-phrase linting) it costs ~30 min extra inside #1. |
| 5 | **Demo narratives / synthetic clinician persona stories** | ≤1 h, last | Nice for the video intro ("Dr. X gets a WGS result at 2 AM…"). Zero technical credit; do only if the model work is frozen. |

**Not on the list (explicitly):** LLMs reading FASTA directly (a 5 Mbp genome ≈ 1.3–1.7M tokens at ~3–4 chars/token — near or beyond context limits and strictly worse than AMRFinderPlus output), fine-tuning (OpenAI is [winding down the fine-tuning platform](https://platform.openai.com/docs/pricing)), and LLM-generated "explanations" of the ML model's SHAP values without constraints (see Q2).

The pattern the literature supports: **LLMs in genomics succeed as grounded narrators and tool-users, fail as parametric knowledge sources.** GeneGPT (Jin et al., *Bioinformatics* 2024;40(2):btae075) scored 0.83 avg on the GeneTuring benchmark by teaching the LLM to call NCBI Web APIs, vs 0.44 for a retrieval-augmented chat LLM answering from its own knowledge ([PubMed](https://pubmed.ncbi.nlm.nih.gov/37131884/), [arXiv](https://arxiv.org/pdf/2304.09667v3)). ChatTogoVar (*Journal of Human Genetics*, 2026) similarly found that grounding in a trusted variant database "reduced hallucinations in variant interpretation," while general-purpose LLMs still produced "incorrect gene–variant associations or unsupported claims" ([Nature](https://www.nature.com/articles/s41439-026-00344-4)). Our analog: the LLM never decides anything about the genome — AMRFinderPlus + the ML model decide; the LLM only narrates a pre-computed evidence bundle.

---

## Q2 — Hallucination / overclaiming risks and concrete guardrails

### The risk, quantified

- **Citation fabrication is the default, not the edge case.** A Deakin University study (2025) of GPT-4o-generated literature reviews found **56% of citations were fabricated or erroneous**, ~1 in 5 entirely fake; among fabricated citations with DOIs, **64% pointed to real but unrelated papers** — the hardest kind to spot ([Study Finds](https://studyfinds.org/chatgpts-hallucination-problem-fabricated-references/)). The Columbia Journalism Review/Tow Center audit (Mar 2025) of eight AI search tools found >60% collective error on source attribution: ChatGPT Search 67% wrong, Perplexity 37%, Grok-3 94% ([summary via digitalapplied](https://www.digitalapplied.com/blog/ai-search-agents-google-perplexity-chatgpt); tabulated in [OWASP AISVS](https://github.com/OWASP/AISVS/blob/main/research/chapters/C07-Model-Behavior/C07-02-Hallucination-Detection.md)). A head-and-neck surgery writing study found only **10% of 50 ChatGPT references fully correct** ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0196070923001941?via%3Dihub=)).
- **In microbial genomics specifically**, the four recurring LLM failure modes are: invented genes/mechanisms/PMIDs, biological overinterpretation (gene presence → phenotype claims), and irreproducible or unsafe statements ([*Life* 2026, "Responsible Use of LLMs in Microbial Genomics"](https://www.mdpi.com/2075-1729/16/6/1032)). "A statistical association with gyrA_S83L" becoming "this strain is fluoroquinolone-resistant because gyrA S83L disrupts DNA gyrase" is exactly the biological-overinterpretation failure — plausible, mechanistic-sounding, and unsupported by our model.
- **Why this matters for scoring:** the challenge *rewards abstention* (no-call rate vs accuracy-at-coverage). OpenAI's own Sept 2025 research, ["Why Language Models Hallucinate"](https://openai.com/index/why-language-models-hallucinate/), argues models hallucinate because "standard training and evaluation procedures reward guessing over acknowledging uncertainty," and that evals should "penalize confident errors more than… uncertainty and give partial credit for appropriate expressions of uncertainty." That is precisely what this challenge's scoring does — a point worth making verbatim in the pitch (see Q5).

### Guardrail stack (build in this order; each layer is cheap)

**Layer 1 — The LLM never generates facts. Code writes numbers; the LLM writes words.**
The report pipeline produces an *evidence bundle* JSON: AMRFinderPlus hits (gene, %identity, %coverage, contig, coordinates), model outputs per drug (call, calibrated probability, conformal set size), dataset context (n training genomes for that drug, prevalence), and the target-gate result. All numbers, gene names, and the call itself are rendered into the report by string templates. The LLM only writes narrative fields that *reference* bundle entries.

**Layer 2 — Citation-by-ID, deterministically validated.**
Every bundle entry gets an ID (`E1`…`En`). The output schema requires `cited_evidence_ids` on every narrative claim, and a post-generation validator rejects/regenerates any report citing a nonexistent ID:

```python
def validate(report: dict, bundle_ids: set[str]) -> None:
    for d in report["per_drug"]:
        bad = [e for e in d["cited_evidence_ids"] if e not in bundle_ids]
        if bad:
            raise HallucinatedEvidence(f"{d['drug']}: cited {bad}, not in bundle")
```

**Layer 3 — Schema-constrained output via Structured Outputs (strict mode).**
Use `client.responses.parse(..., text_format=PydanticModel)` or raw `text: {format: {type: "json_schema", strict: true, schema: ...}}`. Guarantees syntactic schema adherence — "you don't need to worry about the model omitting a required key, or hallucinating an invalid enum value" ([OpenAI Structured Outputs docs](https://platform.openai.com/docs/guides/structured-outputs)). Constraints to know (all verified in those docs):
- `additionalProperties: false` required on every object; **all fields must be `required`** (emulate optional with `{"type": ["string","null"]}`).
- Root must be an object, no root-level `anyOf`; no `allOf`/`not`/`if`/`then`.
- Supported model lineages: `gpt-4o-2024-08-06`/`gpt-4o-mini` and later — covers the current gpt-5.x family.
- Outputs follow schema key ordering; first request with a new schema has extra latency.
- Handle the dedicated `refusal` field — safety refusals are programmatically detectable rather than schema-breaking.

Sneaky-useful trick: **enforce the mandatory lab-testing disclaimer in the schema itself** as a single-value enum, so it is structurally impossible to omit:

```json
"lab_confirmation_notice": {
  "type": "string",
  "enum": ["Research-grade prediction only. Not for clinical use. Confirm all results with standard laboratory antimicrobial susceptibility testing."]
}
```

Also pin `call` and `evidence_category` as enums (`likely_to_fail | likely_to_work | no_call`, `known_resistance_marker | statistical_association_only | no_known_signal`) so the LLM cannot soften a no-call into a prediction.

**Layer 4 — Refusal-to-speculate prompting + abstention mirroring.**
System prompt: "You narrate a completed analysis. If the evidence bundle does not support a statement, do not make it. If evidence is thin, say so explicitly in `speculation_note`. Never infer mechanism from association. Never state or imply clinical validation." Include a nullable `speculation_note` field so the model has a schema-sanctioned place to express doubt (this mirrors OpenAI's Model Spec position that it is "better to indicate uncertainty… than provide confident information that may be incorrect" — [same source](https://openai.com/index/why-language-models-hallucinate/)).

**Layer 5 — Banned-phrase lint on output.**
Regex scan for causation/authority words: `caus`, `confers resistance`, `proven`, `clinically validated`, `FDA`, `treatment recommendation`, `patient`. Category (i) evidence may state the *database-annotated* mechanism (that comes from AMRFinderPlus, i.e., from the bundle, not the LLM); categories (ii)/(iii) may not contain mechanism language at all. Fail → regenerate once → fall back to pure template text.

**Layer 6 (optional) — Second-model faithfulness check.**
A cheap model (gpt-5.4-nano) gets the report + bundle and answers "list any claim not directly supported by a cited bundle entry." Useful in the *eval harness* (Q3) to measure faithfulness; do not rely on it as a runtime gate — it has its own error rate.

**Eval harness for the LLM layer (1–2 h, worth it):** 25–30 synthetic evidence bundles including adversarial cases (empty bundle, conflicting hits, drug with 12 training genomes, target-gate failure). Metrics: citation-ID validity rate (target 100% after retries), banned-phrase rate (0%), no-call softening rate (0%), faithfulness per Layer 6. This is also demo-able: "we red-teamed our own narrator."

---

## Q3 — Budgeting $50 of API credits

Official per-1M-token prices, [platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing) (fetched 2026-07-18, short-context tier):

| Model | Input | Cached input | Output | Cost per report call* |
|---|---|---|---|---|
| gpt-5.4-nano | $0.20 | $0.02 | $1.25 | ~$0.0018 |
| gpt-5.4-mini | $0.75 | $0.075 | $4.50 | ~$0.0066 |
| gpt-5.4 | $2.50 | $0.25 | $15.00 | ~$0.022 |
| gpt-5.5 | $5.00 | $0.50 | $30.00 | ~$0.050 |

\* ~4,000 input tokens (static system prompt + evidence bundle) + ~800 output tokens. Prompt caching is automatic and cuts the repeated system-prompt prefix to ~10% of list price.

**Bottom line: $50 is 20–100× headroom for this use case; the binding constraints are time and reliability, not money.** Suggested split:

- **~$3 — prompt/schema iteration:** gpt-5.4-nano or mini, 300–500 calls. Nano is genuinely capable enough for "rewrite this narrative given these 8 JSON facts."
- **~$5 — LLM eval harness runs:** gpt-5.4-mini; use the **Batch API (50% off, ≤24 h completion, up to 50k requests/file)** for the big adversarial sweep overnight if timing allows ([Batch API docs referenced in pricing page]; 50% discount confirmed across multiple integrations, e.g. [spring-ai#3905](https://github.com/spring-projects/spring-ai/issues/3905)).
- **~$10 — judge-visible report generation:** gpt-5.4 for all reports in the demo video and anything a judge might click. Reserve gpt-5.5 for a single "hero" report if it reads noticeably better.
- **~$3 — Q&A feature:** gpt-5.4-mini with gpt-5.4 fallback.
- **~$29 — untouched reserve** for the final 3 hours (regenerating everything with the frozen pipeline, pitch drafts, panic).

**Do not spend on:** the web-search tool ($10/1k calls + content tokens — all knowledge needed is already in the evidence bundle), Realtime/audio (gpt-realtime-2 text is $4/$24 per 1M — a voice demo has zero judging value here), image generation for anything "scientific" (a made-up picture of a bacterium undermines the honesty framing), and fine-tuning (platform is being wound down for new users — [pricing page note](https://platform.openai.com/docs/pricing)).

**Demo-safety rule that costs nothing:** pre-generate *every* judge-facing report offline and ship them as cached JSON. Live API calls in the demo are a bonus layer with the cached version as instant fallback. Never let an API round-trip stand between the team and the 9:00 AM deadline.

---

## Q4 — "Multimodal integration" that is not a gimmick

The honest reading of "multimodal" for this challenge: **combining text, structured tables, and scientific figures in one coherent report artifact** — not LLM image generation.

Build this:

1. **A genome-track evidence figure.** Plot AMRFinderPlus hit locations on a linear genome map (contig position, gene, strand), colored by drug class, directly beside the per-drug call. This makes evidence category (i) *visible* — a judge sees "the blaCTX-M-15 hit is really there at 2.1 Mb with 99.8% identity" instead of trusting prose. Tooling: [DNA Features Viewer](https://github.com/Edinburgh-Genome-Foundry/DnaFeaturesViewer) (pure-Python SVG/PNG, drops straight into Streamlit) if hits are few; [JBrowse 2](https://jbrowse.org/jb2/) (Diesh et al., *Genome Biology* 2023, [paper](https://link.springer.com/article/10.1186/s13059-023-02914-z), 900+ citations; React embeddable, client-side only) only if someone already knows React — otherwise it's a 5-hour rabbit hole.
2. **The scoring metrics as first-class report figures.** Reliability diagram, per-drug PR curves, and the no-call-rate-vs-accuracy-at-coverage curve rendered inside the app. The challenge judges on Brier score and coverage curves — *showing them in the demo* signals the system was built around its own evaluation, which is exactly the "honest generalization" story.
3. **A clinician-style one-page report layout** (exportable PDF): header with genome ID + QC summary, traffic-light per-drug call table, evidence panel with clickable E-IDs that scroll to the underlying AMRFinderPlus row, footer with the mandatory lab-testing disclaimer and evidence-category legend. Layout *is* multimodal communication; a well-composed page photographs well in the MP4.
4. If Q&A (Q1 #3) ships: the chat answers with inline `[E3]` chips that highlight the referenced evidence row. Text + UI state, again honest multimodality.

Ignore: AI-generated pathogen imagery, 3-D protein-structure renders "for flavor," voice interfaces, vision-LLM "reading" of plots back into text. All cost hours, add no evidence, and the image ones actively clash with the defensive-bioscience framing.

---

## Q5 — What OpenAI/MIT-ecosystem hackathon judges publicly reward

**Hack-Nation's own public signals** (no explicit rubric is published; these are from the organizer's pages):
- "Ship a **working AI product** in 24 hours" and "move beyond demos and build systems that matter" ([hack-nation.ai](https://hack-nation.ai/), [Luma event page](https://luma.com/c3yfi6vu)).
- Venture Track selects the top 15 teams on "**technical execution and venture potential**" — the framing is startup-like: real problem, defensible approach, credible path ([venture-track page](https://hack-nation.ai/venture-track)). A past winner's "How to Pitch Like a Winner" guide is hosted on the [submission platform](https://projects.hack-nation.ai/) — watch it before scripting the video.
- Rootedin the MIT Sloan AI community; sponsors include OpenAI and Databricks ([Darpass event listing](https://darpass.com/event/hack-nation-global-ai-hackathon/)).

**Generic AI-hackathon rubrics converge on the same 4–5 axes:** AAAI 2025 Hackathon scores Technology / Design / Completion / Learning equally, telling teams "judges award points based on the criteria, not dock efforts" ([AAAI rules PDF](https://aaai.org/wp-content/uploads/2025/02/AAAI-2025-Hackathon-Rules.pdf)); TAIKAI lists creativity, technical execution, functional MVP, problem-solution fit — and notes **the final pitch is often decisive** among technically-equal teams ([TAIKAI](https://taikai.network/en/blog/hackathon-judging)); Devpost's organizer guidance warns that submissions are routinely disqualified for missing baseline requirements — for us that means the Streamlit/Gradio demo, the disclaimer, and the three evidence categories must be unmistakably present in the video ([Devpost](https://info.devpost.com/blog/understanding-hackathon-submission-and-judging-criteria)).

**The OpenAI-alignment play (inference, not a published rubric — flagged as such):** I found no public statements from OpenAI staff about judging this event. But OpenAI's current public research messaging is unusually well-matched to this challenge: ["Why Language Models Hallucinate"](https://openai.com/index/why-language-models-hallucinate/) (Sept 2025) argues evaluations should reward calibrated abstention over confident guessing, calls humility a core value, and cites the Model Spec's instruction to prefer expressing uncertainty over confident incorrectness. The Genome Firewall scoring (no-call rate vs accuracy-at-coverage, Brier/reliability) is a working implementation of that philosophy. **Say this explicitly in the pitch**: "OpenAI's own research says evals should penalize confident errors more than abstention — we built a system where both the classifier and the LLM narrator can say 'I don't know,' and we scored them for it." That one sentence ties the whole architecture to the sponsor's worldview.

**Venture framing for the clinical setting:** position as *decision support that routes genomes to the right confirmatory test faster*, never as lab replacement. The mandatory "confirm with standard lab testing" messaging then doubles as regulatory realism (awareness that this is SaMD/IVD territory), which operator-judges read as maturity, not weakness.

---

## Concrete build plan for the LLM slice (fits inside 24 h, parallel to ML work)

- **H0–2:** Define the evidence-bundle JSON contract and Pydantic report schema (strict-mode compliant). Draft system prompt v1. Owner: 1 person, no ML dependency.
- **H2–5:** Report writer v1 on gpt-5.4-mini; citation-ID validator; banned-phrase lint; test on 5 genomes from public BV-BRC data.
- **H5–7:** Adversarial eval set (25–30 bundles); measure validity/faithfulness; fix prompt, not code, where possible.
- **H7–11:** Streamlit integration: report page + genome-track figure + metrics figures + PDF export. Pre-generate cached reports.
- **H11–13:** Optional Q&A with canned question buttons.
- **H13–15:** Pitch script + MP4 script + README via gpt-5.4, human-edited. Freeze all prompts.
- **H15+:** Regenerate everything with the frozen pipeline; Batch-API the eval sweep for appendix numbers ("citation validity 100% over 30 adversarial bundles"); sleep.

---

## Self-roast

1. **The entire LLM slice may be worth ~0 leaderboard points.** Balanced accuracy, per-drug F1/AUROC/PR-AUC, Brier, and coverage curves are computed from the ML pipeline, not the prose. If LLM polish steals 6+ hours from grouped-split validation, de-duplication checks, or the conformal layer, we optimized the exhibit and lost the exam. The ranking in Q1 assumes the metrics harness is genuinely already built; if it isn't, everything here drops two priority levels.
2. **Citation-by-ID can produce an illusion of grounding that a domain-expert judge would puncture.** Our validator checks that cited IDs *exist*, not that the narrative *faithfully represents* them — "E3 shows the model no-called this drug" and "E3 supports likely-to-fail" both pass. Worse, the faithfulness checker in Layer 6 is itself an LLM with its own error rate, so we may be shipping unfalsifiable confidence in our verification. A clinician-judge catching prose contradicting the AMRFinderPlus table is a worse look than plain template text would have been.
3. **The "OpenAI judges reward abstention" thesis is a bet, not evidence.** No Hack-Nation judging rubric is public; the judges are plausibly investors and operators who reward a slick, confident product story in a 3-minute pitch. A demo whose centerpiece is "our system says I-don't-know a carefully calibrated 18% of the time" is scientifically right and could still fall flat on stage — and pre-generating all reports (my own demo-safety rule) makes the "live" demo partly canned, which interactive probing by judges can expose as scripted.
