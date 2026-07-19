#!/usr/bin/env python3
"""Genome Firewall — demo report app (Gradio).

Renders a per-genome antibiotic-resistance report from PRECOMPUTED artifacts
only: demo/data/genome_cache.json (built by demo/build_cache.py) plus the
live ../reports/metrics.json (re-read on every render, so a retrain that
overwrites it is picked up without restarting the app). No model inference
happens here.

Run:   demo/.venv/bin/python demo/app.py        # http://127.0.0.1:7860
Env:   GF_REPORTS_DIR   override metrics/reliability-PNG directory
       GF_AMRFINDER_DIR override AMRFinderPlus TSV directory
       PORT             server port (default 7860)
"""

from __future__ import annotations

import html
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_evidence  # noqa: E402  (vendored from features/)

DEMO_DIR = Path(__file__).resolve().parent
CACHE_PATH = DEMO_DIR / "data" / "genome_cache.json"

DISCLAIMER = ("Research prototype — all results must be confirmed with "
              "standard laboratory susceptibility testing.")

VERDICT_WORDS = {
    "likely_to_fail": "likely to fail",
    "likely_to_work": "likely to work",
    "no_call": "no-call",
}

DRUG_PRETTY = {
    "ciprofloxacin": "Ciprofloxacin",
    "gentamicin": "Gentamicin",
    "ampicillin": "Ampicillin",
    "trimethoprim/sulfamethoxazole": "Trimethoprim–sulfamethoxazole",
    "cefotaxime": "Cefotaxime",
}

# pipeline drug name -> canonical key in drug_class_map.yaml (aliases don't
# cover the pipeline's slash spelling)
DRUG_TO_MAP = {
    "trimethoprim/sulfamethoxazole": "trimethoprim-sulfamethoxazole",
}


def canon_drug(drug: str, spec: dict) -> str:
    drug = DRUG_TO_MAP.get(drug, drug)
    return map_evidence.norm_drug_name(drug, spec["drugs"])

TIER_LABEL = {
    "point": "POINT mutation",
    "full_gene": "full gene (EXACT/ALLELE)",
    "degraded": "degraded (partial / stop)",
    "unknown": "unclassified",
}

THREAT_MODEL = [
    ("Homolog leakage",
     "Random splits put near-identical strains in train and test; the model "
     "memorizes clones, not resistance biology, and collapses on unseen lineages.",
     "All splits are by skani cluster (99.5% ANI de-dup); every reported number "
     "comes from genetically grouped splits, with the held-out genetic group as "
     "the headline — never the in-distribution one.",
     "Walsh et al. 2021 DOME, Nat Methods; Hicks et al. 2019, PLoS Comput Biol"),
    ("False confidence",
     "A confidently wrong \u201clikely to work\u201d is the most dangerous output; "
     "raw ML scores are miscalibrated and users over-trust automated suggestions.",
     "Platt calibration on a held-out split only; Brier score and reliability "
     "curve published per drug; asymmetric conformal no-call band "
     "(\u03b1 susceptible-side 0.02) plus an ANI-distance hard override; "
     "confidence is always shown as a bin-level frequency, never a bare number.",
     "Van Calster et al. 2019, BMC Med; FDA CDS guidance (automation bias)"),
    ("Spurious correlation",
     "The model latches onto lineage markers that correlate with resistance in "
     "this sample but encode no mechanism (cf. Caruana's pneumonia–asthma model).",
     "Evidence is decoupled from the model: category (i) curated determinant "
     "(AMRFinderPlus + allele-aware mapping), category (ii) statistical "
     "association only, category (iii) no signal — shown separately, so a "
     "mechanism-free prediction is visibly weaker.",
     "Caruana et al. 2015, KDD; Hicks et al. 2019 (r &gt; 0.98 confounding)"),
    ("Absent-target false-susceptible",
     "\u201cNo resistance gene found\u201d reported as \u201csusceptible\u201d, "
     "including when the drug's target locus was never actually sequenced.",
     "Locus callability gate: the quinolone target loci (gyrA / parC / parE) "
     "must be verified present in the assembly before a wild-type reading is "
     "trusted; not-called loci force suspicion, never default-susceptible.",
     "BioFire K212727 labeling; Ellington et al. 2017 EUCAST WGS-AST report"),
]

# --------------------------------------------------------------------------
# data access
# --------------------------------------------------------------------------

def _resolve_dir(env_var: str, repo_rel: str, demo_rel: str,
                 sentinel: str | None = None) -> Path:
    env = os.environ.get(env_var)
    if env:
        return Path(env)
    repo = DEMO_DIR.parent / repo_rel
    if sentinel is None or (repo / sentinel).exists():
        return repo
    return DEMO_DIR / demo_rel


def reports_dir() -> Path:
    return _resolve_dir("GF_REPORTS_DIR", "reports", "reports", "metrics.json")


def amrfinder_dir() -> Path:
    return _resolve_dir("GF_AMRFINDER_DIR", "features/amrfinder",
                        "data/amrfinder")


def load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text())


def load_metrics() -> tuple[dict, str]:
    """Re-read metrics.json on EVERY render — a retrain overwriting the file
    must be picked up without restarting the app."""
    p = reports_dir() / "metrics.json"
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%H:%M:%S")
        return json.loads(p.read_text()), f"{p} (read {mtime})"
    except Exception:
        return {}, f"{p} (unavailable)"


def _yaml_sources() -> dict:
    try:
        return map_evidence.load_map(
            Path(map_evidence.__file__).parent / "drug_class_map.yaml"
        ).get("sources", {})
    except Exception:
        return {}


CACHE: dict = {}
CURATED: dict = {}
SOURCES: dict = _yaml_sources()
DRUGS: list = []
GENOME_IDS: list = []
_CACHE_MTIME: float | None = None


def reload_cache_if_changed(force: bool = False) -> None:
    """Reload genome_cache.json when it changed on disk (cache rebuild after
    a retrain). Drug-set changes still require an app restart (the UI wires
    one evidence block per drug)."""
    global CACHE, CURATED, DRUGS, GENOME_IDS, _CACHE_MTIME
    try:
        mtime = CACHE_PATH.stat().st_mtime
    except OSError:
        return
    if not force and mtime == _CACHE_MTIME:
        return
    CACHE = load_cache()
    CURATED = CACHE.get("curated", {})
    DRUGS = [d for d in CACHE.get("drug_list", []) if d in CACHE.get("drugs", {})]
    GENOME_IDS = sorted(CACHE.get("genomes", {}))
    _CACHE_MTIME = mtime


reload_cache_if_changed(force=True)

SLOT_ORDER = ["resistant", "susceptible", "refusal"]
SLOT_LABEL = {
    "resistant": "A · Textbook resistant",
    "susceptible": "B · Honest likely-to-work",
    "refusal": "C · The refusal (no-call)",
}


def slot_genome(slot: str) -> str | None:
    c = CURATED.get(slot, {})
    return c.get("genome_id")


# --------------------------------------------------------------------------
# small html helpers
# --------------------------------------------------------------------------

def esc(x) -> str:
    return html.escape(str(x))


def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{esc(text)}</span>'


def verdict_badge(verdict: str, reason: str | None = None) -> str:
    word = VERDICT_WORDS.get(verdict, verdict)
    cls = {"likely_to_fail": "v-fail", "likely_to_work": "v-work"}.get(
        verdict, "v-nocall")
    title = ""
    if verdict == "no_call" and reason:
        title = f' title="{esc(reason)}"'
    return f'<span class="badge {cls}"{title}>{esc(word)}</span>'


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


# --------------------------------------------------------------------------
# frequency framing (metrics.json reliability bins)
# --------------------------------------------------------------------------

def frequency_framing(metrics: dict, drug: str, split: str | None,
                      p: float) -> str:
    group = "heldout_group" if split == "heldout_group" else "seen"
    group_words = ("held-out genomes" if group == "heldout_group"
                   else "evaluation genomes (seen clusters)")
    rel = (metrics.get(drug, {}).get("groups", {}).get(group, {})
           .get("reliability", {}))
    edges = rel.get("bin_edges") or []
    frac = rel.get("fraction_positive") or []
    count = rel.get("count") or []
    if not edges or len(edges) < 2:
        return "calibration data unavailable for this drug"
    i = 0
    for k in range(len(edges) - 1):
        lo_e, hi_e = edges[k], edges[k + 1]
        if (lo_e <= p < hi_e) or (k == len(edges) - 2 and p <= hi_e):
            i = k
            break
        if p >= hi_e:
            i = k
    n = count[i] if i < len(count) else None
    f = frac[i] if i < len(frac) else None
    lo_s, hi_s = f"{edges[i]:.1f}", f"{edges[i + 1]:.1f}"
    if not n or f is None:
        return (f"no {group_words} scored in the {lo_s}–{hi_s} range — "
                f"calibration offers no local frequency here")
    return (f"among {group_words} scoring {lo_s}–{hi_s}, "
            f"<b>{pct(f)}</b> were resistant (n={n})")


# --------------------------------------------------------------------------
# renderers
# --------------------------------------------------------------------------

def render_header(gid: str) -> str:
    g = CACHE["genomes"].get(gid)
    if g is None:
        return (f'<div class="card err">Genome <code>{esc(gid)}</code> is not '
                f'in the scored corpus (features/feature_matrix.csv). '
                f'Pick an id from the dropdown.</div>')
    split = g.get("split") or "unassigned"
    split_cls = "s-heldout" if split == "heldout_group" else "s-seen"
    labels = []
    for d in DRUGS:
        dd = g["drugs"].get(d)
        if dd and dd.get("label") is not None:
            lab = "<b>R</b>" if dd["label"] == 1 else "<b>S</b>"
            labels.append(f"{DRUG_PRETTY.get(d, d)} {lab}")
    lab_html = " · ".join(labels) if labels else "no lab phenotypes in corpus"
    curated_tag = ""
    for slot, c in CURATED.items():
        if c.get("genome_id") == gid:
            why = "".join(f"<li>{esc(w)}</li>" for w in c.get("why", []))
            curated_tag = (f'<div class="cur-tag">{esc(SLOT_LABEL[slot])} — '
                           f'{esc(c.get("headline", ""))}</div>'
                           f'<ul class="story-why">{why}</ul>')
    return f"""
<div class="card">
  {curated_tag}
  <div class="gid mono">{esc(gid)}</div>
  <div class="meta">
    {badge(split.replace('_', ' '), split_cls)}
    <span class="dim">cluster {esc(g.get('cluster_id'))} · clade {esc(g.get('coarse_clade_id'))}</span>
    <span class="dim">ANI distance to nearest training genome:
      <span class="mono">{g.get('dist_to_train', '?')}</span></span>
  </div>
  <div class="meta dim">Lab phenotypes (re-derived): {lab_html}</div>
</div>"""


def render_verdicts(gid: str, metrics: dict) -> str:
    g = CACHE["genomes"].get(gid)
    if g is None:
        return ""
    bands = CACHE["drugs"]
    rows = []
    for d in DRUGS:
        dd = g["drugs"].get(d)
        if dd is None:
            rows.append(f"""<tr>
<td class="drug">{esc(DRUG_PRETTY.get(d, d))}</td>
<td>{verdict_badge('no_call')}</td>
<td class="mono dim">—</td>
<td class="dim">not scored — no lab phenotype for this drug in the corpus</td>
<td class="dim">—</td></tr>""")
            continue
        p, v, reason = dd["p"], dd["verdict"], dd["nocall_reason"]
        if v == "no_call" and reason == "distance":
            thr = bands[d].get("dist_threshold")
            why = (f'no-call — outside the training distribution '
                   f'(ANI distance {g["dist_to_train"]:.2f} &gt; threshold '
                   f'{thr:.2f}); the score {p:.3f} was <i>not</i> trusted')
        elif v == "no_call":
            lo, hi = bands[d]["band"]
            why = (f'no-call — score {p:.3f} inside the abstention band '
                   f'[{lo:.3f}, {hi:.3f}]')
        else:
            why = frequency_framing(metrics, d, g.get("split"), p)
        n_i = sum(1 for _ in evidence_hits(gid, d))
        n_ii = len(dd.get("model_features", []))
        ev = (f'<span class="ev-i">i:{n_i}</span> '
              f'<span class="ev-ii">ii:{n_ii}</span>')
        lab = dd.get("label")
        lab_chip = ('<span class="lab r">lab R</span>' if lab == 1 else
                    '<span class="lab s">lab S</span>' if lab == 0 else
                    '<span class="lab dim">lab —</span>')
        rows.append(f"""<tr class="row-{v}">
<td class="drug">{esc(DRUG_PRETTY.get(d, d))}<br>{lab_chip}</td>
<td>{verdict_badge(v, reason)}</td>
<td class="mono">{p:.3f}</td>
<td class="frame">{why}</td>
<td class="mono">{ev}</td></tr>""")
    return f"""
<div class="card">
<table class="vt">
<thead><tr><th>Drug</th><th>Verdict</th><th>p</th>
<th>Calibration (frequency framing)</th><th>Evidence</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<div class="foot-note">Verdicts are a pure function of (calibrated score,
no-call band, ANI distance) — recomputed from cached scores; never read from a
stale artifact. Evidence: (i) curated determinant hits · (ii) model
association features.</div>
</div>"""


def evidence_hits(gid: str, drug: str) -> list[dict]:
    tsv = amrfinder_dir() / f"{gid}.tsv"
    if not tsv.exists():
        return []
    try:
        spec = map_evidence.load_map(
            Path(map_evidence.__file__).parent / "drug_class_map.yaml")
        canon = canon_drug(drug, spec)
        hits = map_evidence.read_amrfinder_tsv(str(tsv))
        return map_evidence.map_hits(hits, spec["drugs"][canon])
    except Exception:
        return []


def _cite_family(rule_name: str, drug: str, spec: dict) -> str:
    try:
        canon = canon_drug(drug, spec)
        for r in spec["drugs"][canon].get("rules", []):
            if r["name"] == rule_name:
                fams = []
                for ref in r.get("sources", []):
                    cite = SOURCES.get(ref, {}).get("cite") or \
                        SOURCES.get(ref, {}).get("title") or ref
                    fams.append(cite.split(";")[0].strip())
                return "; ".join(fams)
    except Exception:
        pass
    return ""


def render_evidence(gid: str, drug: str) -> str:
    g = CACHE["genomes"].get(gid)
    dd = (g or {}).get("drugs", {}).get(drug, {})
    spec = map_evidence.load_map(
        Path(map_evidence.__file__).parent / "drug_class_map.yaml")
    canon = canon_drug(drug, spec)
    hits = evidence_hits(gid, drug)

    # category (i)
    if hits:
        rows = []
        for h in hits:
            comp = (f' <span class="dim">({esc(h["component"])} component)</span>'
                    if h.get("component") else "")
            conf_cls = "c-conf" if h["confidence"] == "confirmed" else "c-rev"
            cite = _cite_family(h["rule"], drug, spec)
            rows.append(f"""<tr>
<td class="mono">{esc(h['element_symbol'])}{comp}<br>
<span class="dim small">{esc(h['element_name'])}</span></td>
<td>{badge(TIER_LABEL.get(h['tier'], h['tier']), 't-' + h['tier'])}</td>
<td><span class="{conf_cls}">{esc(h['confidence'])}</span><br>
<span class="dim small">rule: {esc(h['rule'])}</span></td>
<td class="small dim">{esc(cite)}</td></tr>""")
        cat_i = f"""<table class="et"><thead><tr>
<th>Determinant</th><th>Tier</th><th>Confidence</th><th>Citation family</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>"""
    else:
        cat_i = '<div class="dim">no spectrum-confirmed determinant detected.</div>'

    # category (ii)
    feats = dd.get("model_features", [])
    if feats:
        lis = "".join(
            f'<li><span class="mono">{esc(f["feature"])}</span> '
            f'<span class="dim">(weight {f["coef"]:+.3f}, points to '
            f'{esc(f["direction"])})</span></li>' for f in feats)
        cat_ii = (f'<ul class="mfl">{lis}</ul><div class="small dim">Strongest '
                  f'nonzero model features present in this genome. Association '
                  f'only — no curated mechanism.</div>')
    else:
        cat_ii = '<div class="dim">no model association features present.</div>'

    # category (iii)
    if not hits and not feats:
        cat_iii = (f'<div class="nosig">No signal: no curated determinant and '
                   f'no model association for {esc(DRUG_PRETTY.get(drug, drug))} '
                   f'in this genome.</div>')
    else:
        cat_iii = ('<div class="dim">signal present — see categories (i) / '
                   '(ii) above.</div>')

    blind = spec["drugs"][canon].get("blind_spots", "")
    blind_html = (f'<details class="blind"><summary>Known blind spots '
                  f'(declared)</summary><p>{esc(blind)}</p></details>'
                  if blind else "")
    return f"""<div class="ev-wrap">
<h4>(i) Known determinant — spectrum-confirmed</h4>{cat_i}
<h4>(ii) Statistical association — model only</h4>{cat_ii}
<h4>(iii) No-signal check</h4>{cat_iii}
{blind_html}
</div>"""


def render_gate(gid: str) -> str:
    g = CACHE["genomes"].get(gid)
    if g is None:
        return ""
    call = g.get("callability", {})
    meta = CACHE.get("callability", {})
    rows, fires, all_wt = [], False, True
    for locus in CACHE.get("gate_loci", []):
        c = call.get(locus, {})
        st = c.get("status", "unknown")
        muts = ", ".join(c.get("mutations") or [])
        frac = c.get("kmer_frac")
        frac_s = "n/a" if frac is None else pct(frac)
        if st == "mutation_present":
            all_wt = False
            cell = badge(f"mutation found: {muts}", "g-mut")
        elif st == "wild_type_intact":
            cell = badge("wild type — locus verified sequenced", "g-wt")
        elif st == "not_called":
            cell = badge("locus NOT called", "g-nc")
            fires = True
        else:
            cell = badge("unknown (assembly unavailable)", "g-nc")
            fires = True
        rows.append(f"""<tr><td class="mono">{esc(locus)}</td><td>{cell}</td>
<td class="mono">{frac_s}</td></tr>""")
    cipro = g.get("drugs", {}).get("ciprofloxacin", {})
    v = cipro.get("verdict")
    if fires and v == "likely_to_work":
        gate_msg = ('<div class="gate-fires">Gate fires: a \u201clikely to '
                    'work\u201d call would be unsafe — a quinolone target '
                    'locus was not verifiably sequenced.</div>')
    elif all_wt:
        gate_msg = ('<div class="gate-ok">All quinolone target loci were '
                    'verified sequenced and read wild type. \u201cNo mutation '
                    'found\u201d here is a measured wild type, not a missing '
                    'locus.</div>')
    else:
        gate_msg = ('<div class="gate-ok">Target loci verified sequenced; '
                    'curated substitutions are listed above.</div>')
    return f"""
<div class="card">
<div class="gate-title">Callability gate — ciprofloxacin target loci
<span class="dim small">(k-mer locus check, k={meta.get('k', 31)}, ≥
{pct(meta.get('callable_frac', 0.75))} of locus k-mers required)</span></div>
<table class="et"><thead><tr><th>Locus</th><th>Status</th>
<th>Locus k-mers found</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{gate_msg}
<div class="foot-note">Within one species the target is never truly absent —
this is a locus-callability / wild-type-intactness check (APHL wording): we
verify the target locus was actually sequenced before trusting
\u201cno mutation found\u201d.</div>
</div>"""


# --------------------------------------------------------------------------
# trust tab
# --------------------------------------------------------------------------

def render_trust_numbers(metrics: dict) -> str:
    rows = []
    for d in DRUGS:
        groups = metrics.get(d, {}).get("groups", {})
        for grp, label in (("seen", "seen clusters"),
                           ("heldout_group", "held-out group")):
            g = groups.get(grp, {})
            if not g:
                continue
            nc = g.get("no_call_rate")
            acc = g.get("accuracy_after_no_call")
            ba = g.get("balanced_accuracy")
            br = g.get("brier")
            rows.append(f"""<tr><td class="drug">{esc(DRUG_PRETTY.get(d, d))}</td>
<td>{label}</td><td class="mono">{g.get('n', '—')}</td>
<td class="mono">{'—' if nc is None else pct(nc)}</td>
<td class="mono">{'—' if acc is None else pct(acc)}</td>
<td class="mono">{'—' if ba is None else f'{ba:.3f}'}</td>
<td class="mono">{'—' if br is None else f'{br:.3f}'}</td></tr>""")
    if not rows:
        return ('<div class="card dim">metrics.json unavailable — run the '
                'training pipeline or set GF_REPORTS_DIR.</div>')
    return f"""
<div class="card">
<table class="vt"><thead><tr><th>Drug</th><th>Group</th><th>n</th>
<th>no-call rate</th><th>accuracy when called</th><th>balanced acc</th>
<th>Brier</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<div class="foot-note">The no-call is not a compromise — routine lab AST has
an official \u201creport as uncertain\u201d mode (EUCAST Area of Technical
Uncertainty). This table is the same behavior, automated and measured.</div>
</div>"""


def render_reliability(drug: str):
    safe = drug.replace("/", "_")
    png = reports_dir() / f"reliability_{safe}.png"
    if png.exists():
        return gr.Image(value=str(png), label=f"Reliability — {drug}",
                        show_label=True, interactive=False, height=420)
    return gr.Image(value=None, label=f"Reliability — {drug} (PNG missing)",
                    show_label=True, interactive=False, height=120)


def render_coverage(drug: str, metrics: dict):
    recs = []
    groups = metrics.get(drug, {}).get("groups", {})
    for grp, label in (("seen", "seen clusters"),
                       ("heldout_group", "held-out group")):
        rc = groups.get(grp, {}).get("risk_coverage", {})
        cov, acc = rc.get("coverage") or [], rc.get("accuracy") or []
        for c, a in zip(cov, acc):
            if a is not None:
                recs.append({"coverage": c, "accuracy": a, "group": label})
    if not recs:
        return gr.LinePlot(value=pd.DataFrame({"coverage": [], "accuracy": [],
                                               "group": []}),
                           x="coverage", y="accuracy", color="group",
                           title="Accuracy vs coverage (unavailable)")
    df = pd.DataFrame(recs)
    return gr.LinePlot(value=df, x="coverage", y="accuracy", color="group",
                       title=f"Accuracy vs coverage — {drug} "
                             f"(answers withheld from least confident first)",
                       x_title="coverage (fraction of genomes called)",
                       y_title="accuracy on called genomes", height=380)


def render_threat_model() -> str:
    rows = "".join(f"""<tr><td class="tm-name">{esc(a)}</td>
<td>{esc(b)}</td><td>{c}</td><td class="small dim">{d}</td></tr>"""
                   for a, b, c, d in THREAT_MODEL)
    return f"""
<div class="card">
<div class="gate-title">How this model can mislead — and what we did about it</div>
<table class="vt tm"><thead><tr><th>Failure mode</th><th>Failure story</th>
<th>Countermeasure (built, not promised)</th><th>Anchor</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>"""


def render_provenance(metrics_src: str) -> str:
    built = CACHE.get("built_at", "?")
    return (f'<div class="prov dim">metrics: {esc(metrics_src)} · '
            f'cache built {esc(built)} · '
            f'{len(GENOME_IDS)} genomes × {len(DRUGS)} drugs · '
            f'AMRFinderPlus TSVs: {esc(amrfinder_dir())}</div>')


# --------------------------------------------------------------------------
# page render (one fn -> all genome-dependent outputs)
# --------------------------------------------------------------------------

def render_genome(gid: str):
    reload_cache_if_changed()
    gid = (gid or "").strip()
    try:
        metrics, src = load_metrics()
        outs = [render_header(gid), render_verdicts(gid, metrics)]
        outs += [render_evidence(gid, d) for d in DRUGS]
        outs.append(render_gate(gid))
        outs.append(render_provenance(src))
        return outs
    except Exception:
        traceback.print_exc()
        err = (f'<div class="card err"><b>render error</b><pre>'
               f'{esc(traceback.format_exc(limit=3))}</pre></div>')
        # [header, verdicts, ev per drug, gate, prov]
        return [err] + [""] * (4 + len(DRUGS) - 1)


def render_trust(drug: str):
    metrics, src = load_metrics()
    return [render_trust_numbers(metrics), render_reliability(drug),
            render_coverage(drug, metrics), render_provenance(src)]


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root{
  --void:#04070a; --panel:#0a1014; --line:#182228;
  --ink:#e8eef0; --ash:#8b979e; --silver:#b9c4c9;
  --teal:#39d5b0; --teal-dim:rgba(57,213,176,.14);
  --amber:#ffb829; --gray-nc:#9aa3b2;
}
body,.gradio-container{background:var(--void)!important;color:var(--ink);
  font-family:'Inter',system-ui,sans-serif!important}
.mono,code,pre{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace!important}
.gradio-container{max-width:1180px!important;margin:auto!important}
h1,h2,h3,h4{font-weight:500;letter-spacing:-.01em}
.dim{color:var(--ash)} .small{font-size:11px}
.banner{background:#101a17;border:1px solid rgba(255,184,41,.4);
  border-left:3px solid var(--amber);border-radius:8px;
  padding:10px 16px;margin:10px 0;color:var(--silver);font-size:13.5px}
.banner b{color:var(--amber);font-weight:600}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:18px 20px;margin:12px 0}
.card.err{border-color:#7a3434;color:#e0a9a9}
.gid{font-size:26px;font-weight:600;letter-spacing:.02em;margin:2px 0 8px}
.meta{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:4px 0;
  font-size:13px}
.cur-tag{color:var(--teal);font-family:'JetBrains Mono',monospace;
  font-size:11px;letter-spacing:.14em;text-transform:uppercase;margin-bottom:6px}
.badge{display:inline-block;padding:3px 10px;border-radius:5px;font-size:12px;
  font-weight:600;letter-spacing:.06em;border:1px solid transparent}
.v-fail{color:var(--amber);border-color:rgba(255,184,41,.55);
  background:rgba(255,184,41,.08)}
.v-work{color:var(--teal);border-color:rgba(57,213,176,.5);
  background:var(--teal-dim)}
.v-nocall{color:var(--gray-nc);border-color:rgba(154,163,178,.5);
  border-style:dashed;background:rgba(154,163,178,.06)}
.s-heldout{color:#c9a7ff;border-color:rgba(160,110,255,.5);
  background:rgba(160,110,255,.08)}
.s-seen{color:var(--silver);border-color:var(--line);background:#0d1418}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;color:var(--ash);font-weight:500;font-size:11px;
  letter-spacing:.12em;text-transform:uppercase;padding:8px 10px;
  border-bottom:1px solid var(--line)}
td{padding:10px;border-bottom:1px solid #121b20;vertical-align:top}
tr:last-child td{border-bottom:0}
.vt .drug{font-weight:500}
.vt tr.row-no_call td{background:rgba(154,163,178,.03)}
.frame{color:var(--silver);line-height:1.5}
.foot-note{margin-top:12px;color:var(--ash);font-size:12px;line-height:1.6}
.ev-i{color:var(--teal)} .ev-ii{color:var(--ash)}
.lab{font-size:10.5px;padding:1px 6px;border-radius:4px;letter-spacing:.05em}
.lab.r{color:var(--amber);border:1px solid rgba(255,184,41,.4)}
.lab.s{color:var(--teal);border:1px solid rgba(57,213,176,.35)}
.et td{font-size:13px}
.t-point{color:#7fd7ff;border-color:rgba(127,215,255,.45);
  background:rgba(127,215,255,.07)}
.t-full_gene{color:var(--teal);border-color:rgba(57,213,176,.45);
  background:var(--teal-dim)}
.t-degraded{color:var(--gray-nc);border-color:rgba(154,163,178,.4);
  background:rgba(154,163,178,.06)}
.t-unknown{color:var(--ash);border-color:var(--line)}
.c-conf{color:var(--teal);font-weight:600}
.c-rev{color:var(--amber);font-weight:600}
.c-rev::after{content:" ⚠";font-size:11px}
.mfl{margin:4px 0 8px 18px;color:var(--silver)}
.mfl li{margin:3px 0;font-size:13px}
.nosig{color:var(--gray-nc);border:1px dashed rgba(154,163,178,.4);
  border-radius:6px;padding:8px 12px;font-size:13px}
.blind{margin-top:10px;font-size:12.5px;color:var(--ash)}
.blind summary{cursor:pointer;color:var(--silver)}
.blind p{margin:8px 0 0;line-height:1.6}
.ev-wrap h4{color:var(--ash);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;margin:16px 0 6px}
.gate-title{font-size:15px;font-weight:500;margin-bottom:10px}
.g-mut{color:#7fd7ff;border-color:rgba(127,215,255,.45);
  background:rgba(127,215,255,.07)}
.g-wt{color:var(--teal);border-color:rgba(57,213,176,.45);
  background:var(--teal-dim)}
.g-nc{color:var(--gray-nc);border-color:rgba(154,163,178,.5);
  border-style:dashed}
.gate-ok{margin-top:12px;color:var(--teal);font-size:13.5px;line-height:1.55}
.gate-fires{margin-top:12px;color:var(--amber);font-size:13.5px;line-height:1.55}
.tm td{font-size:12.5px;line-height:1.55}
.tm-name{font-weight:600;white-space:nowrap}
.prov{font-size:11.5px;margin:8px 4px;font-family:'JetBrains Mono',monospace}
.story-why{margin:4px 0 8px 18px;color:var(--silver);font-size:13px;
  line-height:1.6}
.story-btn{min-width:200px}
footer{display:none}
"""

OUTPUTS: list = []


def build_ui() -> gr.Blocks:
    global OUTPUTS
    default_gid = slot_genome("resistant") or (GENOME_IDS[0] if GENOME_IDS else "")
    story_choices = [(f"{SLOT_LABEL[s]} — {CURATED[s]['headline']}",
                      CURATED[s]["genome_id"])
                     for s in SLOT_ORDER if s in CURATED]

    with gr.Blocks(title="Genome Firewall", css=CSS,
                   theme=gr.themes.Base(),
                   js="() => {document.body.classList.add('dark');}") as demo:
        gr.HTML(f"""
<div style="padding:26px 4px 0">
  <div class="cur-tag">Hack-Nation Challenge 06 · E. coli · 5 drugs</div>
  <h1 style="margin:0;font-size:40px">Genome <span style="color:var(--teal)">Firewall</span></h1>
  <div class="dim" style="margin-top:6px;max-width:760px;line-height:1.6">
  Per-antibiotic verdicts from a reconstructed genome —
  <span class="mono" style="color:var(--amber)">likely to fail</span> ·
  <span class="mono" style="color:var(--teal)">likely to work</span> ·
  <span class="mono" style="color:var(--gray-nc)">no-call</span> —
  with calibrated confidence as held-out frequencies, spectrum-confirmed
  evidence, and a target-locus callability gate. The genome doesn't replace
  the lab; it tells you which cases to rush and which antibiotic not to start
  with.</div>
</div>""")
        gr.HTML(f'<div class="banner"><b>Disclaimer.</b> {esc(DISCLAIMER)}</div>')

        with gr.Tabs():
            with gr.Tab("Genome report"):
                with gr.Row():
                    picker = gr.Dropdown(
                        choices=[(g, g) for g in GENOME_IDS],
                        value=default_gid, label="Genome (BV-BRC id)",
                        allow_custom_value=True, filterable=True, scale=2)
                with gr.Row():
                    story_btns = []
                    for label, gid in story_choices:
                        b = gr.Button(label, variant="secondary",
                                      elem_classes=["story-btn"], scale=1)
                        story_btns.append((b, gid))
                    reload_btn = gr.Button("↻ Re-read metrics", scale=1)
                header = gr.HTML()
                verdicts = gr.HTML()
                gate = gr.HTML()
                with gr.Accordion("Evidence drawer — per drug, three "
                                  "categories", open=False):
                    ev_blocks = []
                    for d in DRUGS:
                        gr.HTML(f'<div class="cur-tag" style="margin-top:14px">'
                                f'{esc(DRUG_PRETTY.get(d, d))}</div>')
                        ev_blocks.append(gr.HTML())
                prov = gr.HTML()

            with gr.Tab("Trust & calibration"):
                trust_drug = gr.Dropdown(
                    choices=DRUGS, value=DRUGS[0] if DRUGS else None,
                    label="Drug")
                trust_nums = gr.HTML()
                rel_img = gr.Image(label="Reliability", interactive=False,
                                   height=420)
                cov_plot = gr.LinePlot()
                gr.HTML(render_threat_model())
                prov2 = gr.HTML()

        gr.HTML(f'<div class="banner"><b>Disclaimer.</b> {esc(DISCLAIMER)} '
                f'<span class="dim">— No-call means \u201croute to the lab\u201d, '
                f'not \u201calarm\u201d. Scope: prediction only; no sequence '
                f'output, no clinical recommendations.</span></div>')

        OUTPUTS = [header, verdicts, *ev_blocks, gate, prov]
        trust_outputs = [trust_nums, rel_img, cov_plot, prov2]

        picker.change(render_genome, inputs=picker, outputs=OUTPUTS,
                      api_name="report")
        reload_btn.click(render_genome, inputs=picker, outputs=OUTPUTS)
        reload_btn.click(render_trust, inputs=trust_drug,
                         outputs=trust_outputs)
        for b, gid in story_btns:
            b.click(lambda g=gid: g, outputs=picker).then(
                render_genome, inputs=picker, outputs=OUTPUTS)
        trust_drug.change(render_trust, inputs=trust_drug,
                          outputs=trust_outputs, api_name="trust")
        demo.load(render_genome, inputs=picker, outputs=OUTPUTS)
        demo.load(render_trust, inputs=trust_drug, outputs=trust_outputs)
    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name=os.environ.get("HOST", "127.0.0.1"),
               server_port=int(os.environ.get("PORT", "7860")))
