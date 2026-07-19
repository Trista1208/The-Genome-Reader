---
marp: true
theme: default
---

# Genome Firewall

**The AI that knows when to say "I don't know."**

One bacterial genome in → per antibiotic: `ALLOW` · `BLOCK` · `QUARANTINE`

---

## The problem

- Empiric antibiotic therapy fails in **10–39% of ICU patients** — resistance is invisible at prescription time
- Lab susceptibility testing takes **1–3 days**
- A confident wrong answer is worse than no answer

---

## What it does

Upload one genome → a firewall decision per antibiotic:

- 🔴 **BLOCK** — likely to fail, with named genetic evidence (gene, mutation, citation)
- 🟢 **ALLOW** — likely to work, only after passing our molecular-target gate
- ⚪ **QUARANTINE** — not enough evidence → routed to the lab. *The intended path, not an error.*

Every call carries calibrated confidence.

---

## The moment

A genome from an unseen lineage:

- Standard tools: confidently wrong
- **Genome Firewall: refuses to answer**

We answer **[X]%** of genomes — at **[Y]%** balanced accuracy.
The ones we decline are exactly the ones everyone else gets wrong.

*(one coverage curve on screen)*

---

## Why you can trust the numbers

- Train/test split **by genetic group** (ANI clustering) — no leakage, numbers survive unseen lineages
- Calibrated confidence — when we say 90%, we're right ~90% of the time
- Labels re-derived from raw lab data against current breakpoints — **3 species audited**, not 1

---

## Responsibility

> The 100-year-old gold standard has an official "uncertain" zone — EUCAST's Area of Technical Uncertainty.
> **We gave our model the same professional privilege.**

Research prototype — confirm all results with standard lab testing. On every screen.

---

## Close

> **"A system that says 'I don't know' on cue is the one you can believe when it says 'I do.'"**

Genome Firewall — it doesn't replace the lab. It tells you tonight which cases to rush, and which antibiotic not to start with.

---

<!-- Fill [X] and [Y] from the real grouped-CV run before presenting. Never invent them. -->
