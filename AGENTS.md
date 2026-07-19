# AGENTS.md — Genome Firewall

Operational knowledge for anyone (human or agent) working in this repo. Read before
touching anything. Written 2026-07-19 after the v1–v3 build; see also RETROSPECTIVE
lessons below — they were paid for in hours.

## Project

Predicts per-antibiotic likely-to-fail / likely-to-work / no-call from an E. coli
genome FASTA (Hack-Nation × OpenAI, Challenge 06). Strictly defensive: never design
or modify organisms. All outputs require "confirm with standard lab testing."

## Environment rules

- **No conda on this machine.** Python deps go in per-area `.venv` dirs (gitignored).
- **Bioinformatics CLIs run in Docker** (amd64 images → Rosetta emulation on Apple
  Silicon, ~2× slower). Pinned image: `staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1`
  (tool + DB versions baked in — do not upgrade mid-project).
- **skani is the one exception worth building native**: `cargo install skani` gives an
  arm64 build ~2× faster than the emulated Docker image. Use it for any new clustering.
- AMRFinderPlus v4 TSV headers say **"Element symbol"** (v3 "Gene symbol" is deprecated).

## Git rules

- Work on `sprint/baseline` (the working line), never directly on `main`. Merges to
  `main` only on explicit user request.
- Remotes: `origin` = Darkroom4364/genome-firewall, `team` = Trista1208/The-Genome-Reader.
  Push to both after every meaningful commit.
- Data and regenerable outputs stay gitignored (genomes, TSVs, models, reports, edges).
  Code, configs, docs, and small JSON artifacts go in.

## Data contracts (violating these caused real bugs)

- **genome_id is a STRING everywhere.** pandas parses "562.100000" as float64 → 562.1
  and silently corrupts joins. Always `dtype={'genome_id': str}`. This bug happened twice.
- Labels: `data/clean/labels_clean_*.csv` — MIC-only, re-derived vs EUCAST v16.1
  (breakpoints in `data/breakpoints.yaml`); never use `evidence == "Computational Method"` rows.
- Antibiotic name for SXT is the slash form: `trimethoprim/sulfamethoxazole`.
- metrics.json SXT key may differ from the model dir name (`trimethoprim_sulfamethoxazole`).

## Retrospective — scheduling/architecture lessons (consider these before re-running)

1. **Decide the corpus once, then compute each expensive thing exactly once.** skani
   ran on 1,434 then again on 3,000 (~2.5h duplicated). Corpus-size decisions come
   before clustering, not after.
2. **skani is all-vs-all (quadratic).** 3,000 genomes ≈ 3h under emulation. For
   additions, compute only new-vs-all edges; never recompute the full triangle.
3. **Batches run at constant low parallelism to completion** — hot-cold-hot scheduling
   (pause/kill/resume) costs more than it saves and risks partial outputs. All batch
   scripts are resumable; check newest TSVs for partials after any kill.
4. **`/tmp` is not durable** for multi-hour pipelines. A stratification file in /tmp
   vanished mid-run and killed the splits step at hour 3. Stage intermediates inside
   the repo (gitignored) or regenerate them in the same process that consumes them.
5. **Version-stamp every artifact** (models, metrics.json, demo cache, bundles) with a
   shared run tag. A silent model re-save invalidated the demo cache once already.
6. **Demo caches must be rebuilt after every model retrain.** Order: retrain →
   build_cache.py → build_static.py → redeploy Space → regenerate demo_bundle.json.
7. **Long compute goes to plain background processes; agents don't babysit them.**
   Agents that "wait for skani" just time out. Fire the process, then resume the agent.
8. **HF Spaces: static = free; Gradio/Docker = PRO.** skops `trusted=` takes a list
   (from `get_untrusted_types`), not True. Static subdomain provisioning can fail
   silently — have the local-video + Colab fallback ready.
9. **macOS shell traps:** `xargs -I{}` has a tiny replacement limit (use a helper
   script); `head` closes pipes (SIGPIPE kills python producers); BSD grep/awk choke
   on some GNU-isms — prefer script files over long one-liners.
10. **Evaluation discipline is non-negotiable:** metrics harness before model; nested
    grouped folds; never tune on the folds you report; report seen vs heldout_group
    separately; the random-vs-grouped gap is a headline number, not an afterthought.

## Key files

- `CONTRACT.md` — data/feature/split formats (the interface contract)
- `PREBUILT.md` — pre-event work disclosure
- `CONTEXT.md` — team handoff snapshot
- `pipeline/PIPELINE.md` — pipeline setup + commands
- `features/MAPPING_NOTES.md` — drug→determinant mapping sources

---

## Product stack notes (Next.js + Convex)

<!-- convex-ai-start -->

This project uses [Convex](https://convex.dev) as its backend.

When working on Convex code, **always read
`convex/_generated/ai/guidelines.md` first** for important guidelines on
how to correctly use Convex APIs and patterns. The file contains rules that
override what you may have learned about Convex from training data.

Convex agent skills for common tasks can be installed by running
`npx convex ai-files install`.

<!-- convex-ai-end -->
