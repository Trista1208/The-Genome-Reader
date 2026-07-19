#!/usr/bin/env python3
"""smoke_test.py — prove the demo serves and renders all 3 curated genomes
without exceptions.

Two modes:
  demo/.venv/bin/python demo/smoke_test.py --local
      import app.py and call render_genome() directly (no server needed)
  demo/.venv/bin/python demo/smoke_test.py --url http://127.0.0.1:7860
      hit the running Gradio API via gradio_client (end-to-end)

Exit 0 on success, 1 on any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO))

REQUIRED_VERDICT_WORDS = ["likely to fail", "likely to work", "no-call"]
DISCLAIMER_SNIPPET = "Research prototype"


def curated_ids() -> dict[str, str]:
    data = json.loads((DEMO / "data" / "curated.json").read_text())
    return {slot: c["genome_id"] for slot, c in data.items()}


def check_html(slot: str, gid: str, outputs: list) -> list[str]:
    """outputs: [header, verdicts, ev x5, gate, prov]"""
    fails = []
    header, verdicts = outputs[0], outputs[1]
    if "render error" in header or "render error" in verdicts:
        fails.append(f"{slot}/{gid}: render error surfaced")
    if gid not in header:
        fails.append(f"{slot}/{gid}: genome id missing from header")
    if "among" not in verdicts and "no-call" not in verdicts:
        fails.append(f"{slot}/{gid}: no frequency framing in verdict table")
    if "Callability gate" not in outputs[-2]:
        fails.append(f"{slot}/{gid}: callability gate panel missing")
    return fails


def check_vocabulary(all_outputs: list[list]) -> list[str]:
    """The three rubric verdict words must appear verbatim across the three
    curated stories (not necessarily in every single genome's table)."""
    joined = " ".join(str(o) for outs in all_outputs for o in outs)
    return [f"verdict word {w!r} missing across all curated genomes"
            for w in REQUIRED_VERDICT_WORDS if w not in joined]


def run_local(ids: dict[str, str]) -> int:
    import app  # noqa: PLC0415

    fails, all_outs = [], []
    for slot, gid in ids.items():
        try:
            outs = app.render_genome(gid)
            all_outs.append(outs)
            fails += check_html(slot, gid, outs)
            print(f"  local {slot:12s} {gid}: render ok "
                  f"({len(outs)} blocks)", flush=True)
        except Exception as e:  # noqa: BLE001
            fails.append(f"{slot}/{gid}: exception {e!r}")
    fails += check_vocabulary(all_outs)
    # disclaimer is static UI text — assert it exists in the built Blocks
    try:
        demo = app.build_ui()
        cfg = json.dumps(demo.config)
        if DISCLAIMER_SNIPPET not in cfg:
            fails.append("disclaimer banner missing from UI config")
    except Exception as e:  # noqa: BLE001
        fails.append(f"build_ui exception {e!r}")
    return report(fails)


def run_remote(url: str, ids: dict[str, str]) -> int:
    from gradio_client import Client  # noqa: PLC0415

    fails, all_outs = [], []
    client = Client(url)
    for slot, gid in ids.items():
        try:
            outs = client.predict(gid, api_name="/report")
            outs = list(outs)
            all_outs.append(outs)
            fails += check_html(slot, gid, outs)
            print(f"  api   {slot:12s} {gid}: /report ok "
                  f"({len(outs)} blocks)", flush=True)
        except Exception as e:  # noqa: BLE001
            fails.append(f"{slot}/{gid}: api exception {e!r}")
    fails += check_vocabulary(all_outs)
    try:
        outs = client.predict("ciprofloxacin", api_name="/trust")
        if not outs or not outs[0]:
            fails.append("trust tab returned empty metrics table")
        else:
            print("  api   trust tab  : /trust ok", flush=True)
    except Exception as e:  # noqa: BLE001
        fails.append(f"trust tab: api exception {e!r}")
    return report(fails)


def report(fails: list[str]) -> int:
    if fails:
        print("\nSMOKE FAILED:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\nsmoke: all checks passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--url", default=None)
    args = ap.parse_args()
    ids = curated_ids()
    print("curated genomes:", ids)
    if args.local:
        return run_local(ids)
    if args.url:
        return run_remote(args.url, ids)
    ap.error("pass --local or --url http://127.0.0.1:7860")
    return 2


if __name__ == "__main__":
    sys.exit(main())
