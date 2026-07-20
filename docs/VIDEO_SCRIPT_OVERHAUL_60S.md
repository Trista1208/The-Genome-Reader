# Genome Firewall — overhauled single video (60s)

Replaces the spliced v2/v3 draft. One train of thought, one evaluation pass.
All numbers trace to `reports/metrics.json` (v3-3000) and `features/metadata.json`
(886 features). Slides: `docs/slides_60s.html` (6 slides, one per beat).
~155 spoken words — brisk but calm pace.

Train of thought: **problem → what it answers → architecture → safety wrapper →
proof → we caught our own failure → close.**

| # | Time | Slide | Narration (exact) |
|---|---|---|---|
| 1 | 0:00–0:08 | Hook | "Lab susceptibility takes one to three days. The genome is ready in hours. Genome Firewall reads it now — and answers per antibiotic: likely to fail, likely to work, or no-call." |
| 2 | 0:08–0:20 | Architecture | "AMRFinderPlus turns the FASTA into 886 binary features — one per resistance element. Five small elastic-net models, one per drug, Platt-calibrated for honest probabilities." |
| 3 | 0:20–0:30 | Safety wrapper | "Then the safety wrapper decides call versus abstain: conformal no-call bands, a distance override for out-of-distribution genomes, and a gate that verifies the drug's target was actually sequenced." |
| 4 | 0:30–0:42 | Scorecard | "Tested on genetic lineages never seen in training — not random splits. 0.92 mean balanced accuracy, four of five drugs above 0.91. Ampicillin 0.82 — reported, not rounded." |
| 5 | 0:42–0:52 | The failure we caught | "We caught our own failure: an unseen ESBL allele collapsed cefotaxime to 0.69. Adding lineages fixed it to 0.95. And when evidence is weak, it abstains — two in ten genomes, 95% accurate on the rest." |
| 6 | 0:52–0:60 | Close | "Small honest models. Explicit abstention. Open on Hugging Face. Genome Firewall — research prototype; confirm every call with standard lab testing." |

## What changed from the spliced draft, and why

- **One evaluation pass.** The draft evaluated twice ("all passed 90%" → later
  "ampicillin 0.82"). Kept the v3 pass; deleted the v2 one. "All passed 90%" was
  false under balanced accuracy (ampicillin 0.823) and self-contradicting.
- **Cefotaxime story promoted to the climax.** 0.69 → 0.95 is verified
  (v2 → v3 metrics) and is the strongest honesty beat — it was buried at the end.
- **Dropped the 562.100124 anecdote.** Under v3 that genome no-calls on only 1/5
  drugs and is a false "likely to work" on ciprofloxacin (lab label: resistant).
  If a refusal anecdote is wanted, use the curated pick `562.141421`
  (demo/data/genome_cache.json): cipro p=0.80 → no-call, lab truth susceptible.
- **Cut "Docker inference API" and "Next.js + Convex".** Not in the repo; web/ is
  Vite + React. Kept the one shipping claim that is live: Hugging Face models.
- **Kept (verified):** 886 features, AMRFinderPlus, Platt, conformal bands,
  ANI override, target-locus gate, skani held-out lineages, 0.92 mean,
  4/5 > 0.91, ampicillin 0.82, ~2/10 abstain, 95% accurate when called.

## Recording notes
- Slide deck: open `docs/slides_60s.html`, press → / space to advance; `?s=N`
  opens slide N directly (for retakes).
- Record after the v3 demo cache rebuild so any screen capture matches
  these numbers.
