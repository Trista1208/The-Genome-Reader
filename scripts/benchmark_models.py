#!/usr/bin/env python3
"""Benchmark Random Forest models on the homology-held-out test split.

Writes JSON report with Hack-Nation metrics + failure reasons.

Usage:
  python3 scripts/benchmark_models.py
  python3 scripts/benchmark_models.py --strict   # exit 1 unless all gates pass
  python3 scripts/benchmark_models.py --json-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from genome_firewall.config import DEFAULT_PATHS
from genome_firewall.layer5_evaluation.benchmark import BenchmarkGate, BenchmarkRunner


def print_table(report: dict) -> None:
    if report.get("benchmark_status") == "blocked":
        print("BENCHMARK BLOCKED")
        for reason in report.get("failure_reasons", []):
            print(f"  ! {reason}")
        return

    summary = report.get("summary", {})
    print(f"Benchmark status: {report.get('benchmark_status', 'unknown').upper()}")
    print(
        f"Genomes w/ features: {report['cohort']['n_genomes_with_features']} | "
        f"Trained drugs: {summary.get('n_drugs_trained')} | "
        f"Passing eval: {summary.get('n_drugs_passing_eval')}/{summary.get('n_drugs_trained')}"
    )
    if summary.get("mean_balanced_accuracy") is not None:
        print(
            f"Mean BalAcc={summary['mean_balanced_accuracy']}  "
            f"Mean Rec-R={summary.get('mean_recall_resistant')}  "
            f"Mean Brier={summary.get('mean_brier')}"
        )

    for reason in report.get("benchmark_failure_reasons", []):
        print(f"  ! {reason}")

    print(f"\n{'Drug':<26} {'Status':<8} {'BalAcc':>7} {'Rec-R':>6} {'Rec-S':>6} {'Brier':>6} {'Test R/S':>9}")
    print("-" * 82)
    for d in report.get("drugs", []):
        if d["training_status"] == "skipped":
            print(f"{d['antibiotic']:<26} {'SKIP':<8} {'—':>7} {'—':>6} {'—':>6} {'—':>6} {'—':>9}")
            continue
        m = d["metrics"]
        flag = "PASS" if d["passes_eval"] else "FAIL"
        rs, ss = m["test_resistant"], m["test_susceptible"]
        bal = m.get("balanced_accuracy_called")
        print(
            f"{d['antibiotic']:<26} {flag:<8} "
            f"{bal if bal is not None else 'n/a':>7} "
            f"{m.get('recall_resistant') if m.get('recall_resistant') is not None else 'n/a':>6} "
            f"{m.get('recall_susceptible') if m.get('recall_susceptible') is not None else 'n/a':>6} "
            f"{m.get('brier') if m.get('brier') is not None else 'n/a':>6} "
            f"{rs:>2}/{ss:<6}"
        )

    failing = report.get("failing_drugs", [])
    if failing:
        print("\n=== Why drugs fail ===")
        for d in failing:
            print(f"\n{d['antibiotic']}:")
            for reason in d.get("failure_reasons", []):
                print(f"  ! {reason}")

    skipped = report.get("skipped_drugs", [])
    if skipped:
        print("\n=== Skipped drugs ===")
        for d in skipped:
            print(f"  {d['antibiotic']}: {d['reason']} — {d['detail']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/models/benchmark_report.json"),
    )
    parser.add_argument(
        "--min-genomes",
        type=int,
        default=100,
        help="Minimum genomes with features for benchmark pass (default 100)",
    )
    parser.add_argument("--strict", action="store_true", help="Exit 1 unless benchmark_status=pass")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    gates = BenchmarkGate(min_genomes_with_features=args.min_genomes)
    runner = BenchmarkRunner(gates=gates)
    report = runner.write_report(args.out)

    if args.json_only:
        print(json.dumps(report, indent=2))
    else:
        print(f"Wrote {args.out}\n")
        print_table(report)

    raise SystemExit(runner.exit_code(report, strict=args.strict))


if __name__ == "__main__":
    main()
