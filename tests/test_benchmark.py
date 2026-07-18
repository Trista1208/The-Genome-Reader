"""Benchmark and backend smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from genome_firewall.config import DEFAULT_PATHS
from genome_firewall.layer4_scoring.explanations import training_skip_reason
from genome_firewall.layer4_scoring.predictor import decide_prediction
from genome_firewall.layer5_evaluation.benchmark import BenchmarkRunner


def _has_benchmark_data() -> bool:
    return (
        (DEFAULT_PATHS.features_dir / "feature_matrix.npz").exists()
        and (DEFAULT_PATHS.splits_dir / "genome_split.tsv").exists()
        and bool(list(DEFAULT_PATHS.models_dir.glob("*_model.joblib")))
    )


@pytest.mark.skipif(not _has_benchmark_data(), reason="benchmark artifacts not built")
class TestBenchmark:
    def test_benchmark_runs(self):
        report = BenchmarkRunner().run()
        assert report["benchmark_status"] in {"pass", "warn", "fail"}
        assert "drugs" in report
        assert "summary" in report
        assert len(report["drugs"]) == 5

    def test_benchmark_report_schema(self):
        report = BenchmarkRunner().run()
        for drug in report["drugs"]:
            assert "antibiotic" in drug
            assert "training_status" in drug
            if drug["training_status"] == "trained":
                assert "metrics" in drug
                assert "passes_eval" in drug
                assert "failure_reasons" in drug
                m = drug["metrics"]
                for key in (
                    "balanced_accuracy_called",
                    "recall_resistant",
                    "recall_susceptible",
                    "brier",
                    "n_test",
                    "test_resistant",
                    "test_susceptible",
                ):
                    assert key in m
            else:
                assert drug["passes_eval"] is False
                assert "skip_reason" in drug

    def test_benchmark_json_serializable(self):
        report = BenchmarkRunner().run()
        text = json.dumps(report)
        assert "benchmark_status" in text

    def test_write_report(self, tmp_path):
        out = tmp_path / "benchmark_report.json"
        report = BenchmarkRunner().write_report(out)
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["benchmark_status"] == report["benchmark_status"]


class TestScoringLogic:
    def test_no_call_in_uncertain_band(self):
        pred, _, _, reason = decide_prediction(
            0.5, no_call_low=0.35, no_call_high=0.65, target_ok=True
        )
        assert pred == "no_call"
        assert reason == "uncertain_probability_band"

    def test_no_call_when_target_gate_fails(self):
        pred, _, _, reason = decide_prediction(
            0.9, no_call_low=0.35, no_call_high=0.65, target_ok=False
        )
        assert pred == "no_call"
        assert reason == "missing_drug_target"

    def test_likely_to_fail_above_threshold(self):
        pred, _, _, reason = decide_prediction(
            0.8, no_call_low=0.35, no_call_high=0.65, target_ok=True
        )
        assert pred == "likely_to_fail"
        assert reason is None

    def test_gentamicin_skip_reason(self):
        skip = training_skip_reason(
            "gentamicin",
            n_labeled=80,
            n_resistant=0,
            n_susceptible=80,
            n_with_features=80,
        )
        assert skip is not None
        assert skip[0] == "single_class_all_susceptible"


class TestPrerequisites:
    def test_missing_models_blocked(self, tmp_path):
        from dataclasses import replace

        if not (DEFAULT_PATHS.features_dir / "feature_matrix.npz").exists():
            pytest.skip("no feature matrix")
        paths = replace(DEFAULT_PATHS, models_dir=tmp_path / "empty_models")
        report = BenchmarkRunner(paths=paths).run()
        assert report["benchmark_status"] == "blocked"
