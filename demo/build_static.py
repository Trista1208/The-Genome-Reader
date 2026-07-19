#!/usr/bin/env python3
"""build_static.py — emit demo/static/, a fully self-contained static version
of the Genome Firewall demo (for a free *static* HF Space or any web server;
no frameworks, no build step, no runtime backend).

Reads (repo-relative):
  demo/data/genome_cache.json   per-genome scores/verdicts/callability
  demo/data/curated.json        the 3 story genomes
  reports/metrics.json          calibration bins for frequency framing
  reports/reliability_*.png     trust-tab plots
  features/amrfinder/*.tsv      category-(i) evidence (precomputed per genome)

Writes:
  demo/static/index.html        (hand-written, not generated — left in place)
  demo/static/app.js            (hand-written, left in place)
  demo/static/styles.css        (hand-written, left in place)
  demo/static/data/genomes.json      slim per-genome records (all 1434)
  demo/static/data/curated.json      story copy
  demo/static/data/metrics.json      calibration copy
  demo/static/data/evidence.json     category-(i) hits per genome per drug
  demo/static/data/gate_status.json  gyrA/parC/parE callability per genome
  demo/static/assets/reliability_*.png

Run:  demo/.venv/bin/python demo/build_static.py      (stdlib + PyYAML)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
STATIC = DEMO / "static"

sys.path.insert(0, str(DEMO))
import map_evidence  # noqa: E402  (vendored)


def slim_genome(gid: str, g: dict) -> dict:
    return {
        "split": g.get("split"),
        "cluster_id": g.get("cluster_id"),
        "coarse_clade_id": g.get("coarse_clade_id"),
        "dist_to_train": g.get("dist_to_train"),
        "drugs": g.get("drugs", {}),
    }


def main() -> int:
    cache = json.loads((DEMO / "data" / "genome_cache.json").read_text())
    curated = json.loads((DEMO / "data" / "curated.json").read_text())
    spec = map_evidence.load_map(DEMO / "drug_class_map.yaml")
    sources = spec.get("sources", {})

    out_data = STATIC / "data"
    out_assets = STATIC / "assets"
    out_data.mkdir(parents=True, exist_ok=True)
    out_assets.mkdir(parents=True, exist_ok=True)

    # ---- per-genome records + evidence + gate ------------------------------
    amr_dir = ROOT / "features" / "amrfinder"
    genomes_out, evidence_out, gate_out = {}, {}, {}
    n_ev = 0
    for gid, g in cache["genomes"].items():
        genomes_out[gid] = slim_genome(gid, g)
        gate_out[gid] = g.get("callability", {})
        tsv = amr_dir / f"{gid}.tsv"
        if not tsv.exists():
            continue
        try:
            hits_all = map_evidence.read_amrfinder_tsv(str(tsv))
        except Exception:
            continue
        per_drug = {}
        for drug in cache.get("drug_list", []):
            map_name = {"trimethoprim/sulfamethoxazole":
                        "trimethoprim-sulfamethoxazole"}.get(drug, drug)
            try:
                canon = map_evidence.norm_drug_name(map_name, spec["drugs"])
            except KeyError:
                continue
            rows = map_evidence.map_hits(hits_all, spec["drugs"][canon])
            if not rows:
                continue
            # attach citation family per rule
            rule_src = {r["name"]: r.get("sources", [])
                        for r in spec["drugs"][canon].get("rules", [])}
            for r in rows:
                fams = []
                for ref in rule_src.get(r["rule"], []):
                    cite = (sources.get(ref, {}).get("cite")
                            or sources.get(ref, {}).get("title") or ref)
                    fams.append(cite.split(";")[0].strip())
                r["citations"] = fams
            per_drug[drug] = rows
            n_ev += len(rows)
        if per_drug:
            evidence_out[gid] = per_drug

    blind_spots = {}
    for drug in cache.get("drug_list", []):
        map_name = {"trimethoprim/sulfamethoxazole":
                    "trimethoprim-sulfamethoxazole"}.get(drug, drug)
        try:
            canon = map_evidence.norm_drug_name(map_name, spec["drugs"])
            blind_spots[drug] = spec["drugs"][canon].get("blind_spots", "")
        except KeyError:
            pass

    payload_meta = {
        "built_at": cache.get("built_at"),
        "drug_list": cache.get("drug_list", []),
        "drugs": cache.get("drugs", {}),          # bands / thresholds
        "gate_loci": cache.get("gate_loci", []),
        "callability": cache.get("callability", {}),
        "blind_spots": blind_spots,
    }

    (out_data / "genomes.json").write_text(json.dumps(
        {"meta": payload_meta, "genomes": genomes_out}, separators=(",", ":")))
    (out_data / "evidence.json").write_text(json.dumps(
        evidence_out, separators=(",", ":")))
    (out_data / "gate_status.json").write_text(json.dumps(
        gate_out, separators=(",", ":")))
    (out_data / "curated.json").write_text(json.dumps(curated, indent=1))

    metrics_src = ROOT / "reports" / "metrics.json"
    if metrics_src.exists():
        shutil.copy(metrics_src, out_data / "metrics.json")
    for png in (ROOT / "reports").glob("reliability_*.png"):
        shutil.copy(png, out_assets / png.name)

    total = sum(f.stat().st_size for f in STATIC.rglob("*") if f.is_file())
    print(f"[build_static] genomes={len(genomes_out)} "
          f"evidence_genomes={len(evidence_out)} hits={n_ev}")
    for f in sorted(out_data.glob("*.json")):
        print(f"  {f.name:22s} {f.stat().st_size/1e6:.2f} MB")
    print(f"[build_static] demo/static total: {total/1e6:.1f} MB "
          f"(budget < 10 MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
