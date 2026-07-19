# Genome Firewall — video scripts (60s max each)

Three videos, each ≤60 seconds, ~150 spoken words max. Read at a brisk but calm pace;
every second is budgeted. Numbers are v3 (metrics.json v3-3000-20260719).
Refusal-genome ID is a slot — filled from the final curated picks (see
demo/data/curated.json at record time).

---

## Video 1 — technical (60s)

**Shots:** 5 slides, screen-captured, no talking heads needed.

| # | Time | Slide | Narration (exact) |
|---|---|---|---|
| 1 | 0:00–0:10 | Problem | "Antimicrobial resistance kills over a million people a year. Lab answers take one to three days. We predict them from the genome in minutes." |
| 2 | 0:10–0:25 | Pipeline diagram | "FASTA in. AMRFinderPlus reads resistance genes. Five small logistic models — one per antibiotic — vote. Platt calibration keeps the probabilities honest." |
| 3 | 0:25–0:40 | Honesty layers | "Four layers: genetic-cluster splits, so tests are truly unseen lineages. A conformal no-call band that abstains when evidence is weak. A distance override for far-out genomes. A gate that verifies the drug's target was actually sequenced." |
| 4 | 0:40–0:52 | Scorecard | "On never-seen strains: ciprofloxacin 0.92, SXT and cefotaxime 0.95 balanced accuracy — and when it answers, it's right about 95% of the time." |
| 5 | 0:52–0:60 | Close | "Open models, open evidence, and it says 'I don't know' when it doesn't. Genome Firewall. Research prototype — confirm with standard lab testing." |

## Video 2 — demo (60s)

**One continuous screen recording** of the static app (HF Space; local fallback).
No narration edits needed beyond the table — record in one take.

| # | Time | Screen | Narration (exact) |
|---|---|---|---|
| 1 | 0:00–0:12 | Refusal genome (curated #3) | "This genome made the naive caller confidently wrong — truth is resistant. Watch ours." *(click)* "No-call. On all five drugs. That's the feature, not the failure." |
| 2 | 0:12–0:28 | Resistant genome (562.135587) | "Same move, resistant case: ciprofloxacin — likely to fail, and here's why: gyrA S83L, D87N, parC mutations. Named evidence, not a black box." |
| 3 | 0:28–0:40 | Susceptible genome (562.100171) | "Susceptible case: likely to work — because the gate verified the drug's target locus was actually sequenced and intact." |
| 4 | 0:40–0:52 | Trust tab | "Held-out lineages only: 0.92 mean balanced accuracy, calibration curves, and the coverage chart — accuracy when it answers." |
| 5 | 0:52–0:60 | Disclaimer footer | "Every screen says it: research prototype — confirm with standard laboratory susceptibility testing." |

## Video 3 — group intro (60s, team-led)

Team records this; we supply the 3-beat skeleton:
1. (0:00–0:20) Who we are + one line each.
2. (0:20–0:45) "The lab needs days; bacteria don't wait. We built the system that says which antibiotic not to start with — and when to say 'I don't know'."
3. (0:45–0:60) The number: "0.92 balanced accuracy on strains it never saw — and it abstains instead of guessing." Names + thanks.

---

### Recording notes
- Static app URL: https://darkroom4364-genome-firewall.hf.space (local fallback:
  `cd demo/static && python3 -m http.server 8791`).
- Trust tab numbers come from `reports/metrics.json` at render time — record AFTER
  the v3 cache rebuild lands so the scoreboard shows v3.
- If the refusal genome changed in the v3 curated re-pick, swap its ID into Video 2
  shot 1's click path; the narration is genome-agnostic.
- Codec: MP4/H.264. Do a 10-second test upload before the real one.
