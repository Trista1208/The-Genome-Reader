/* Genome Firewall — static demo. All data precomputed (data/*.json);
   zero inference in the browser. */
"use strict";

const VERDICT_WORDS = {
  likely_to_fail: "likely to fail",
  likely_to_work: "likely to work",
  no_call: "no-call",
};
const DRUG_PRETTY = {
  ciprofloxacin: "Ciprofloxacin",
  gentamicin: "Gentamicin",
  ampicillin: "Ampicillin",
  "trimethoprim/sulfamethoxazole": "Trimethoprim–sulfamethoxazole",
  cefotaxime: "Cefotaxime",
};
const TIER_LABEL = {
  point: "POINT mutation",
  full_gene: "full gene (EXACT/ALLELE)",
  degraded: "degraded (partial / stop)",
  unknown: "unclassified",
};
const SLOT_ORDER = ["resistant", "susceptible", "refusal"];
const SLOT_LABEL = {
  resistant: "A · Textbook resistant",
  susceptible: "B · Honest likely-to-work",
  refusal: "C · The refusal (no-call)",
};

const S = { meta: null, genomes: null, curated: null, metrics: null,
            evidence: null, gate: null, currentDrug: null };

// ---------------------------------------------------------------- helpers
const esc = (x) => String(x).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x) => `${Math.round(100 * x)}%`;
const badge = (t, cls) => `<span class="badge ${cls}">${esc(t)}</span>`;
const verdictBadge = (v, reason) => {
  const cls = { likely_to_fail: "v-fail", likely_to_work: "v-work" }[v] || "v-nocall";
  const title = (v === "no_call" && reason) ? ` title="${esc(reason)}"` : "";
  return `<span class="badge ${cls}"${title}>${esc(VERDICT_WORDS[v] || v)}</span>`;
};
const drugName = (d) => DRUG_PRETTY[d] || d;

async function fetchJson(url, optional = false) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    if (optional) return null;
    throw e;
  }
}

// ------------------------------------------------------ frequency framing
function frequencyFraming(drug, split, p) {
  const group = split === "heldout_group" ? "heldout_group" : "seen";
  const groupWords = group === "heldout_group"
    ? "held-out genomes" : "evaluation genomes (seen clusters)";
  const rel = (((S.metrics || {})[drug] || {}).groups || {})[group];
  const rr = (rel || {}).reliability || {};
  const edges = rr.bin_edges || [], frac = rr.fraction_positive || [],
        count = rr.count || [];
  if (edges.length < 2) return "calibration data unavailable for this drug";
  let i = 0;
  for (let k = 0; k < edges.length - 1; k++) {
    if ((edges[k] <= p && p < edges[k + 1]) ||
        (k === edges.length - 2 && p <= edges[k + 1])) { i = k; break; }
    if (p >= edges[k + 1]) i = k;
  }
  const n = count[i], f = frac[i];
  const lo = edges[i].toFixed(1), hi = edges[i + 1].toFixed(1);
  if (!n || f === null || f === undefined)
    return `no ${groupWords} scored in the ${lo}–${hi} range — ` +
           `calibration offers no local frequency here`;
  return `among ${groupWords} scoring ${lo}–${hi}, ` +
         `<b>${pct(f)}</b> were resistant (n=${n})`;
}

// ---------------------------------------------------------------- renderers
function renderHeader(gid) {
  const g = S.genomes[gid];
  if (!g) return `<div class="card err">Genome <code>${esc(gid)}</code> is not
    in the scored corpus. Pick an id from the list.</div>`;
  const split = g.split || "unassigned";
  const splitCls = split === "heldout_group" ? "s-heldout" : "s-seen";
  const labels = [];
  for (const d of S.meta.drug_list) {
    const dd = (g.drugs || {})[d];
    if (dd && dd.label !== null && dd.label !== undefined)
      labels.push(`${drugName(d)} <b>${dd.label === 1 ? "R" : "S"}</b>`);
  }
  let curatedTag = "";
  for (const slot of SLOT_ORDER) {
    const c = (S.curated || {})[slot];
    if (c && c.genome_id === gid) {
      const why = (c.why || []).map((w) => `<li>${esc(w)}</li>`).join("");
      curatedTag = `<div class="cur-tag">${esc(SLOT_LABEL[slot])} — ${esc(c.headline || "")}</div>
        <ul class="story-why">${why}</ul>`;
    }
  }
  return `<div class="card">${curatedTag}
    <div class="gid mono">${esc(gid)}</div>
    <div class="meta">
      ${badge(split.replace(/_/g, " "), splitCls)}
      <span class="dim">cluster ${esc(g.cluster_id)} · clade ${esc(g.coarse_clade_id)}</span>
      <span class="dim">ANI distance to nearest training genome:
        <span class="mono">${esc(g.dist_to_train)}</span></span>
    </div>
    <div class="meta dim">Lab phenotypes (re-derived): ${
      labels.join(" · ") || "no lab phenotypes in corpus"}</div>
  </div>`;
}

function renderVerdicts(gid) {
  const g = S.genomes[gid];
  if (!g) return "";
  const rows = [];
  for (const d of S.meta.drug_list) {
    const dd = (g.drugs || {})[d];
    if (!dd) {
      rows.push(`<tr><td class="drug">${esc(drugName(d))}</td>
        <td>${verdictBadge("no_call")}</td><td class="mono dim">—</td>
        <td class="dim">not scored — no lab phenotype for this drug in the corpus</td>
        <td class="dim">—</td></tr>`);
      continue;
    }
    const { p, verdict, nocall_reason, label } = dd;
    let why;
    if (verdict === "no_call" && nocall_reason === "distance") {
      const thr = (S.meta.drugs[d] || {}).dist_threshold;
      why = `no-call — outside the training distribution (ANI distance ` +
            `${Number(g.dist_to_train).toFixed(2)} &gt; threshold ` +
            `${thr === null ? "n/a" : Number(thr).toFixed(2)}); the score ` +
            `${p.toFixed(3)} was <i>not</i> trusted`;
    } else if (verdict === "no_call") {
      const band = (S.meta.drugs[d] || {}).band || ["?", "?"];
      why = `no-call — score ${p.toFixed(3)} inside the abstention band ` +
            `[${Number(band[0]).toFixed(3)}, ${Number(band[1]).toFixed(3)}]`;
    } else {
      why = frequencyFraming(d, g.split, p);
    }
    const ev = (S.evidence || {})[gid] || {};
    const nI = (ev[d] || []).length;
    const nII = (dd.model_features || []).length;
    const labChip = label === 1 ? '<span class="lab r">lab R</span>'
      : label === 0 ? '<span class="lab s">lab S</span>'
      : '<span class="lab dim">lab —</span>';
    rows.push(`<tr class="row-${verdict}">
      <td class="drug">${esc(drugName(d))}<br>${labChip}</td>
      <td>${verdictBadge(verdict, nocall_reason)}</td>
      <td class="mono">${p.toFixed(3)}</td>
      <td class="frame">${why}</td>
      <td class="mono"><span class="ev-i">i:${nI}</span> <span class="ev-ii">ii:${nII}</span></td>
    </tr>`);
  }
  return `<div class="card"><table class="vt">
    <thead><tr><th>Drug</th><th>Verdict</th><th>p</th>
    <th>Calibration (frequency framing)</th><th>Evidence</th></tr></thead>
    <tbody>${rows.join("")}</tbody></table>
    <div class="foot-note">Verdicts are a pure function of (calibrated score,
    no-call band, ANI distance) — precomputed; this page runs no model.
    Evidence: (i) curated determinant hits · (ii) model association
    features.</div></div>`;
}

function renderEvidence(gid, drug) {
  const g = S.genomes[gid] || {};
  const dd = ((g.drugs || {})[drug]) || {};
  const hits = (((S.evidence || {})[gid] || {})[drug]) || [];

  let catI;
  if (hits.length) {
    const rows = hits.map((h) => {
      const comp = h.component ? ` <span class="dim">(${esc(h.component)} component)</span>` : "";
      const confCls = h.confidence === "confirmed" ? "c-conf" : "c-rev";
      const cite = (h.citations || []).join("; ");
      return `<tr>
        <td class="mono">${esc(h.element_symbol)}${comp}<br>
          <span class="dim small">${esc(h.element_name)}</span></td>
        <td>${badge(TIER_LABEL[h.tier] || h.tier, "t-" + h.tier)}</td>
        <td><span class="${confCls}">${esc(h.confidence)}</span><br>
          <span class="dim small">rule: ${esc(h.rule)}</span></td>
        <td class="small dim">${esc(cite)}</td></tr>`;
    }).join("");
    catI = `<table class="et"><thead><tr><th>Determinant</th><th>Tier</th>
      <th>Confidence</th><th>Citation family</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  } else {
    catI = '<div class="dim">no spectrum-confirmed determinant detected.</div>';
  }

  const feats = dd.model_features || [];
  const catII = feats.length
    ? `<ul class="mfl">${feats.map((f) =>
        `<li><span class="mono">${esc(f.feature)}</span>
         <span class="dim">(weight ${Number(f.coef).toFixed(3)}, points to
         ${esc(f.direction)})</span></li>`).join("")}</ul>
       <div class="small dim">Strongest nonzero model features present in this
       genome. Association only — no curated mechanism.</div>`
    : '<div class="dim">no model association features present.</div>';

  const catIII = (!hits.length && !feats.length)
    ? `<div class="nosig">No signal: no curated determinant and no model
       association for ${esc(drugName(drug))} in this genome.</div>`
    : '<div class="dim">signal present — see categories (i) / (ii) above.</div>';

  const blind = ((S.meta.blind_spots || {})[drug]) || "";
  const blindHtml = blind
    ? `<details class="blind"><summary>Known blind spots (declared)</summary>
       <p>${esc(blind)}</p></details>` : "";

  return `<details class="drawer"><summary>${esc(drugName(drug))}</summary>
    <div class="drawer-body"><div class="ev-wrap">
    <h4>(i) Known determinant — spectrum-confirmed</h4>${catI}
    <h4>(ii) Statistical association — model only</h4>${catII}
    <h4>(iii) No-signal check</h4>${catIII}
    ${blindHtml}</div></div></details>`;
}

function renderGate(gid) {
  if (!S.gate) {
    return `<div class="card"><div class="gate-title">Callability gate</div>
      <div class="dim">gate_status.json not shipped with this build — the
      locus callability panel is unavailable here.</div></div>`;
  }
  const call = S.gate[gid];
  if (!call) return "";
  const meta = S.meta.callability || {};
  let fires = false, allWt = true;
  const rows = (S.meta.gate_loci || []).map((locus) => {
    const c = call[locus] || {};
    const st = c.status || "unknown";
    const muts = (c.mutations || []).join(", ");
    const fracS = (c.kmer_frac === null || c.kmer_frac === undefined)
      ? "n/a" : pct(c.kmer_frac);
    let cell;
    if (st === "mutation_present") {
      allWt = false;
      cell = badge(`mutation found: ${muts}`, "g-mut");
    } else if (st === "wild_type_intact") {
      cell = badge("wild type — locus verified sequenced", "g-wt");
    } else if (st === "not_called") {
      cell = badge("locus NOT called", "g-nc"); fires = true;
    } else {
      cell = badge("unknown (assembly unavailable)", "g-nc"); fires = true;
    }
    return `<tr><td class="mono">${esc(locus)}</td><td>${cell}</td>
      <td class="mono">${fracS}</td></tr>`;
  }).join("");
  const cip = ((S.genomes[gid] || {}).drugs || {}).ciprofloxacin || {};
  let gateMsg;
  if (fires && cip.verdict === "likely_to_work") {
    gateMsg = `<div class="gate-fires">Gate fires: a “likely to work” call
      would be unsafe — a quinolone target locus was not verifiably
      sequenced.</div>`;
  } else if (allWt) {
    gateMsg = `<div class="gate-ok">All quinolone target loci were verified
      sequenced and read wild type. “No mutation found” here is a measured
      wild type, not a missing locus.</div>`;
  } else {
    gateMsg = `<div class="gate-ok">Target loci verified sequenced; curated
      substitutions are listed above.</div>`;
  }
  return `<div class="card">
    <div class="gate-title">Callability gate — ciprofloxacin target loci
      <span class="dim small">(k-mer locus check, k=${esc(meta.k || 31)},
      ≥${pct(meta.callable_frac ?? 0.3)} of locus k-mers required)</span></div>
    <table class="et"><thead><tr><th>Locus</th><th>Status</th>
      <th>Locus k-mers found</th></tr></thead><tbody>${rows}</tbody></table>
    ${gateMsg}
    <div class="foot-note">Within one species the target is never truly
    absent — this is a locus-callability / wild-type-intactness check (APHL
    wording): we verify the target locus was actually sequenced before
    trusting “no mutation found”.</div></div>`;
}

function renderGenome(gid) {
  gid = (gid || "").trim();
  const out = [renderHeader(gid), renderVerdicts(gid)];
  for (const d of S.meta.drug_list) out.push(renderEvidence(gid, d));
  out.push(renderGate(gid));
  out.push(`<div class="prov">cache built ${esc(S.meta.built_at || "?")} ·
    ${Object.keys(S.genomes).length} genomes × ${S.meta.drug_list.length}
    drugs · no live inference</div>`);
  document.getElementById("genome-out").innerHTML = out.join("");
  for (const b of document.querySelectorAll("#story-btns .btn"))
    b.classList.toggle("active", b.dataset.gid === gid);
}

// ---------------------------------------------------------------- trust tab
function renderTrustNumbers() {
  const rows = [];
  for (const d of S.meta.drug_list) {
    const groups = ((S.metrics || {})[d] || {}).groups || {};
    for (const [grp, label] of [["seen", "seen clusters"],
                                ["heldout_group", "held-out group"]]) {
      const g = groups[grp];
      if (!g) continue;
      rows.push(`<tr><td class="drug">${esc(drugName(d))}</td><td>${label}</td>
        <td class="mono">${g.n ?? "—"}</td>
        <td class="mono">${g.no_call_rate == null ? "—" : pct(g.no_call_rate)}</td>
        <td class="mono">${g.accuracy_after_no_call == null ? "—" : pct(g.accuracy_after_no_call)}</td>
        <td class="mono">${g.balanced_accuracy == null ? "—" : g.balanced_accuracy.toFixed(3)}</td>
        <td class="mono">${g.brier == null ? "—" : g.brier.toFixed(3)}</td></tr>`);
    }
  }
  document.getElementById("trust-numbers").innerHTML = rows.length
    ? `<div class="card"><table class="vt"><thead><tr><th>Drug</th><th>Group</th>
       <th>n</th><th>no-call rate</th><th>accuracy when called</th>
       <th>balanced acc</th><th>Brier</th></tr></thead>
       <tbody>${rows.join("")}</tbody></table>
       <div class="foot-note">The no-call is not a compromise — routine lab
       AST has an official “report as uncertain” mode (EUCAST Area of
       Technical Uncertainty). This table is the same behavior, automated and
       measured.</div></div>`
    : '<div class="card dim">metrics.json unavailable in this build.</div>';
}

function drawCoverage(drug) {
  const cv = document.getElementById("cov-chart");
  const W = cv.clientWidth || 560, H = 380;
  const dpr = window.devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.height = H + "px";
  const ctx = cv.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const pad = { l: 52, r: 18, t: 34, b: 44 };
  const groups = ((S.metrics || {})[drug] || {}).groups || {};
  const series = [];
  for (const [grp, label, color] of [["seen", "seen clusters", "#8b979e"],
                                     ["heldout_group", "held-out group", "#39d5b0"]]) {
    const rc = (groups[grp] || {}).risk_coverage || {};
    const pts = [];
    (rc.coverage || []).forEach((c, i) => {
      const a = (rc.accuracy || [])[i];
      if (a !== null && a !== undefined) pts.push([c, a]);
    });
    pts.sort((a, b) => a[0] - b[0]);
    if (pts.length) series.push({ label, color, pts });
  }
  ctx.fillStyle = "#8b979e";
  ctx.font = "12px Inter, system-ui, sans-serif";
  ctx.fillText(`Accuracy vs coverage — ${drugName(drug)} ` +
               `(answers withheld from least confident first)`, pad.l, 20);
  if (!series.length) {
    ctx.fillText("risk-coverage data unavailable for this drug", pad.l, H / 2);
    return;
  }
  const yMin = Math.min(0.9, ...series.flatMap((s) => s.pts.map((p) => p[1])));
  const x = (c) => pad.l + c * (W - pad.l - pad.r);
  const y = (a) => pad.t + (1 - (a - yMin) / (1 - yMin)) * (H - pad.t - pad.b);
  ctx.strokeStyle = "#182228"; ctx.fillStyle = "#8b979e"; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const a = yMin + (1 - yMin) * i / 4, yy = y(a);
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
    ctx.fillText(a.toFixed(2), 10, yy + 4);
    const c = i / 4, xx = x(c);
    ctx.fillText(c.toFixed(1), xx - 8, H - pad.b + 18);
  }
  ctx.fillText("accuracy on called genomes", 10, pad.t - 6);
  ctx.fillText("coverage (fraction called)", W - pad.r - 150, H - 8);
  series.forEach((s, si) => {
    ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    ctx.beginPath();
    s.pts.forEach(([c, a], i) => { i ? ctx.lineTo(x(c), y(a)) : ctx.moveTo(x(c), y(a)); });
    ctx.stroke();
    ctx.fillStyle = s.color;
    s.pts.forEach(([c, a]) => { ctx.beginPath(); ctx.arc(x(c), y(a), 2.5, 0, 7); ctx.fill(); });
    ctx.fillRect(pad.l + si * 150, H - 24, 10, 3);
    ctx.fillStyle = "#b9c4c9";
    ctx.fillText(s.label, pad.l + 16 + si * 150, H - 18);
  });
}

function renderTrust(drug) {
  S.currentDrug = drug;
  renderTrustNumbers();
  const img = document.getElementById("rel-img");
  img.src = `assets/reliability_${drug.replace(/\//g, "_")}.png`;
  img.alt = `Reliability — ${drugName(drug)}`;
  drawCoverage(drug);
  document.getElementById("trust-prov").textContent =
    `metrics: data/metrics.json · cache built ${S.meta.built_at || "?"}`;
}

// ---------------------------------------------------------------- boot
async function boot() {
  const [genomes, curated, metrics, evidence, gate] = await Promise.all([
    fetchJson("data/genomes.json"),
    fetchJson("data/curated.json", true),
    fetchJson("data/metrics.json", true),
    fetchJson("data/evidence.json", true),
    fetchJson("data/gate_status.json", true),   // panel degrades if absent
  ]);
  S.meta = genomes.meta; S.genomes = genomes.genomes;
  S.curated = curated || {}; S.metrics = metrics || {};
  S.evidence = evidence || {}; S.gate = gate;

  const list = document.getElementById("genome-list");
  list.innerHTML = Object.keys(S.genomes).sort()
    .map((g) => `<option value="${esc(g)}">`).join("");

  const btnBox = document.getElementById("story-btns");
  for (const slot of SLOT_ORDER) {
    const c = S.curated[slot];
    if (!c) continue;
    const b = document.createElement("button");
    b.className = "btn story"; b.dataset.gid = c.genome_id;
    b.textContent = `${SLOT_LABEL[slot]} — ${c.headline || ""}`;
    b.onclick = () => {
      document.getElementById("picker").value = c.genome_id;
      renderGenome(c.genome_id);
    };
    btnBox.appendChild(b);
  }

  const picker = document.getElementById("picker");
  picker.addEventListener("change", () => renderGenome(picker.value));
  picker.addEventListener("input", () => {
    if (S.genomes[picker.value.trim()]) renderGenome(picker.value);
  });

  const drugSel = document.getElementById("trust-drug");
  drugSel.innerHTML = S.meta.drug_list
    .map((d) => `<option value="${esc(d)}">${esc(drugName(d))}</option>`).join("");
  drugSel.addEventListener("change", () => renderTrust(drugSel.value));

  for (const t of document.querySelectorAll(".tab-btn")) {
    t.addEventListener("click", () => {
      for (const x of document.querySelectorAll(".tab-btn")) x.classList.remove("active");
      t.classList.add("active");
      document.getElementById("tab-report").classList.toggle("hidden", t.dataset.tab !== "report");
      document.getElementById("tab-trust").classList.toggle("hidden", t.dataset.tab !== "trust");
      if (t.dataset.tab === "trust") drawCoverage(S.currentDrug || S.meta.drug_list[0]);
    });
  }
  window.addEventListener("resize", () => {
    if (!document.getElementById("tab-trust").classList.contains("hidden"))
      drawCoverage(S.currentDrug || S.meta.drug_list[0]);
  });

  const defaultGid = (S.curated.resistant || {}).genome_id ||
    Object.keys(S.genomes)[0];
  picker.value = defaultGid;
  renderGenome(defaultGid);
  renderTrust(S.meta.drug_list[0]);
}

boot().catch((e) => {
  document.getElementById("genome-out").innerHTML =
    `<div class="card err"><b>failed to load data</b><br>${esc(e.message)}<br>
     <span class="dim">serve this directory over HTTP
     (python3 -m http.server) — fetch() does not work from file://</span></div>`;
});
