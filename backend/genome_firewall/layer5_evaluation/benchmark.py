from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genome_firewall.config import DEFAULT_PATHS, Paths
from genome_firewall.services.evaluation_service import EvaluationService


@dataclass(frozen=True)
class BenchmarkGate:
    min_genomes_with_features: int = 100
    min_test_genomes: int = 5
    min_test_resistant: int = 1
    min_test_susceptible: int = 1
    min_trained_drugs: int = 3


class BenchmarkRunner:
    """Hack-Nation-style benchmark on homology-held-out test split."""

    def __init__(
        self,
        paths: Paths = DEFAULT_PATHS,
        gates: BenchmarkGate | None = None,
    ) -> None:
        self.paths = paths
        self.gates = gates or BenchmarkGate()
        self.evaluation = EvaluationService(paths)

    def check_prerequisites(self) -> list[str]:
        missing: list[str] = []
        if not (self.paths.features_dir / "feature_matrix.npz").exists():
            missing.append("Feature matrix missing — run scripts/build_feature_matrix.py")
        if not (self.paths.splits_dir / "genome_split.tsv").exists():
            missing.append("Split file missing — run scripts/homology_split.py")
        if not list(self.paths.models_dir.glob("*_model.joblib")):
            missing.append("No trained models — run scripts/train_models.py")
        return missing

    def run(self) -> dict[str, Any]:
        prereq = self.check_prerequisites()
        if prereq:
            return {
                "benchmark_status": "blocked",
                "failure_reasons": prereq,
                "drugs": [],
                "summary": {},
            }

        report = self.evaluation.build_report()
        trained = [d for d in report["drugs"] if d["training_status"] == "trained"]
        skipped = [d for d in report["drugs"] if d["training_status"] == "skipped"]
        passing = [d for d in trained if d["passes_eval"]]
        failing = [d for d in trained if not d["passes_eval"]]

        def avg_metric(key: str) -> float | None:
            vals = [
                d["metrics"][key]
                for d in trained
                if d.get("metrics", {}).get(key) is not None
            ]
            return round(sum(vals) / len(vals), 4) if vals else None

        cohort_issues = list(report["cohort"]["failure_reasons"])
        benchmark_issues: list[str] = []
        if report["cohort"]["n_genomes_with_features"] < self.gates.min_genomes_with_features:
            benchmark_issues.append(
                f"Cohort size {report['cohort']['n_genomes_with_features']} "
                f"< {self.gates.min_genomes_with_features} genomes with features."
            )
        if len(trained) < self.gates.min_trained_drugs:
            benchmark_issues.append(
                f"Only {len(trained)} trained drugs (need ≥{self.gates.min_trained_drugs})."
            )
        if len(passing) == 0 and trained:
            benchmark_issues.append("No drug passed evaluation gates on the test split.")

        status = "pass"
        if benchmark_issues or failing or skipped:
            status = "warn" if passing else "fail"
        if prereq or (not trained and skipped):
            status = "fail" if not trained else status

        return {
            **report,
            "benchmark_status": status,
            "benchmark_gates": {
                "min_genomes_with_features": self.gates.min_genomes_with_features,
                "min_test_genomes": self.gates.min_test_genomes,
                "min_test_resistant": self.gates.min_test_resistant,
                "min_test_susceptible": self.gates.min_test_susceptible,
            },
            "summary": {
                "n_drugs_total": len(report["drugs"]),
                "n_drugs_trained": len(trained),
                "n_drugs_skipped": len(skipped),
                "n_drugs_passing_eval": len(passing),
                "n_drugs_failing_eval": len(failing),
                "mean_balanced_accuracy": avg_metric("balanced_accuracy_called"),
                "mean_brier": avg_metric("brier"),
                "mean_recall_resistant": avg_metric("recall_resistant"),
                "mean_recall_susceptible": avg_metric("recall_susceptible"),
            },
            "benchmark_failure_reasons": benchmark_issues + cohort_issues,
            "skipped_drugs": [
                {"antibiotic": d["antibiotic"], "reason": d["skip_reason"], "detail": d["skip_detail"]}
                for d in skipped
            ],
            "failing_drugs": [
                {
                    "antibiotic": d["antibiotic"],
                    "metrics": d.get("metrics"),
                    "failure_reasons": d.get("failure_reasons", []),
                }
                for d in failing
            ],
        }

    def write_report(self, out_path: Path) -> dict[str, Any]:
        report = self.run()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        out_path.write_text(json.dumps(report, indent=2) + "\n")
        return report

    def exit_code(self, report: dict[str, Any], *, strict: bool = False) -> int:
        if report.get("benchmark_status") == "blocked":
            return 2
        if strict and report.get("benchmark_status") != "pass":
            return 1
        return 0
