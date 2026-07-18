#!/usr/bin/env python3
"""Print evaluation report (use scripts/benchmark_models.py for full benchmark)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/processed/models/evaluation_report.json"))
    parser.add_argument("--json-only", action="store_true")
    args, rest = parser.parse_known_args()
    cmd = [
        sys.executable,
        str(ROOT / "scripts/benchmark_models.py"),
        "--out",
        str(args.out.with_name("benchmark_report.json")),
    ]
    if args.json_only:
        cmd.append("--json-only")
    raise SystemExit(subprocess.call(cmd + rest))


if __name__ == "__main__":
    main()
