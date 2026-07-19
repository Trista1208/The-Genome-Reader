// static_smoke.js — screenshot-free smoke for the static demo.
// Stubs just enough DOM to execute app.js's render functions against the
// real data/*.json payloads and checks all 3 curated genomes render without
// exceptions and that the rubric verdict words appear.
// Run: node demo/static_smoke.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const STATIC = path.join(__dirname, "static");
const read = (f) => JSON.parse(fs.readFileSync(path.join(STATIC, f), "utf8"));

const genomes = read("data/genomes.json");
const curated = read("data/curated.json");
const metrics = read("data/metrics.json");
const evidence = read("data/evidence.json");
const gate = fs.existsSync(path.join(STATIC, "data/gate_status.json"))
  ? read("data/gate_status.json") : null;

// ---- minimal DOM stub -----------------------------------------------------
const elements = {};
const mkEl = () => ({
  innerHTML: "", textContent: "", value: "", src: "", alt: "",
  classList: { add() {}, remove() {}, toggle() {}, contains: () => true },
  style: {}, dataset: {}, clientWidth: 560,
  addEventListener() {}, appendChild() {},
  getContext: () => new Proxy({}, { get: () => () => {} }),
});
const document = {
  getElementById: (id) => (elements[id] ??= mkEl()),
  querySelectorAll: () => [],
  createElement: () => mkEl(),
};
const window = { devicePixelRatio: 1, addEventListener() {} };

// ---- load app.js into a sandbox with the data pre-seeded ------------------
const src = fs.readFileSync(path.join(STATIC, "app.js"), "utf8");
const sandbox = {
  document, window, console,
  fetch: async (url) => {           // serve from disk instead of HTTP
    const body = fs.readFileSync(path.join(STATIC, url), "utf8");
    return { ok: true, json: async () => JSON.parse(body) };
  },
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

(async () => {
  await vm.runInContext(src + "\n;globalThis.bootstrap_done = boot();", sandbox);
  await sandbox.bootstrap_done;

  const fails = [];
  const ids = Object.fromEntries(
    Object.entries(curated).map(([k, v]) => [k, v.genome_id]));
  console.log("curated genomes:", ids);

  const WORDS = ["likely to fail", "likely to work", "no-call"];
  let joinedAll = "";
  for (const [slot, gid] of Object.entries(ids)) {
    try {
      await vm.runInContext(`renderGenome(${JSON.stringify(gid)})`, sandbox);
      const html = elements["genome-out"].innerHTML;
      joinedAll += html;
      if (html.includes("render error") || !html.includes(gid))
        fails.push(`${slot}/${gid}: bad render`);
      if (!html.includes("Callability gate"))
        fails.push(`${slot}/${gid}: gate panel missing`);
      console.log(`  ${slot.padEnd(12)} ${gid}: render ok (${html.length} bytes)`);
    } catch (e) {
      fails.push(`${slot}/${gid}: exception ${e.stack || e}`);
    }
  }
  for (const w of WORDS)
    if (!joinedAll.includes(w)) fails.push(`verdict word ${w} missing overall`);
  for (const needle of ["abstention band", "frequency framing"])
    if (!joinedAll.includes(needle)) fails.push(`${needle} missing overall`);
  if (!joinedAll.includes("among held-out genomes") &&
      !joinedAll.includes("among evaluation genomes"))
    fails.push("frequency framing missing overall");

  // trust tab renders
  try {
    await vm.runInContext(`renderTrust("ciprofloxacin")`, sandbox);
    if (!elements["trust-numbers"].innerHTML.includes("no-call rate"))
      fails.push("trust: no-call table missing");
    console.log("  trust tab   : render ok");
  } catch (e) { fails.push(`trust: exception ${e.stack || e}`); }

  // arbitrary lookup + unknown genome
  try {
    await vm.runInContext(`renderGenome("562.100000")`, sandbox);
    if (!elements["genome-out"].innerHTML.includes("562.100000"))
      fails.push("lookup 562.100000 failed");
    await vm.runInContext(`renderGenome("999.999999")`, sandbox);
    const norm = elements["genome-out"].innerHTML.replace(/\s+/g, " ");
    if (!norm.includes("not in the scored corpus"))
      fails.push("unknown genome not handled gracefully");
    console.log("  arbitrary + unknown genome: ok");
  } catch (e) { fails.push(`lookup: exception ${e.stack || e}`); }

  if (fails.length) {
    console.error("\nSTATIC SMOKE FAILED:");
    for (const f of fails) console.error("  - " + f);
    process.exit(1);
  }
  console.log("\nstatic smoke: all checks passed");
})().catch((e) => { console.error(e); process.exit(1); });
