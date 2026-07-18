from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from genome_firewall.config import DEFAULT_PATHS, Paths
from genome_firewall.layer1_ingestion.cohort import load_labels, load_split
from genome_firewall.layer2_features.matrix import load_feature_store
from genome_firewall.layer3_model.random_forest import CalibratedRandomForest
from genome_firewall.layer3_model.target_gate import passes_target_gate
from genome_firewall.layer4_scoring.explanations import metric_quality_issues, training_skip_reason
from genome_firewall.layer5_evaluation.metrics import evaluate_drug_model


class EvaluationService:
    def __init__(self, paths: Paths = DEFAULT_PATHS) -> None:
        self.paths = paths

    def build_report(self) -> dict:
        labels = load_labels(self.paths.labels)
        splits = load_split(self.paths.splits_dir / "genome_split.tsv")
        genome_ids, X_all, catalog = load_feature_store(self.paths.features_dir)
        gid_to_row = {g: i for i, g in enumerate(genome_ids)}
        featured = set(genome_ids)
        n_features = X_all.shape[1]

        trained = {
            joblib.load(p)["drug"]: p
            for p in self.paths.models_dir.glob("*_model.joblib")
        }

        drug_reports: list[dict] = []
        for drug in sorted(labels["antibiotic"].unique()):
            sub = labels[labels["antibiotic"] == drug]
            in_feat = sub[sub["genome_id"].isin(featured & set(splits))]
            n_resist = int((in_feat["label"] == "likely_to_fail").sum())
            n_susc = int((in_feat["label"] == "likely_to_work").sum())

            if drug not in trained:
                skip = training_skip_reason(
                    drug,
                    n_labeled=len(in_feat),
                    n_resistant=n_resist,
                    n_susceptible=n_susc,
                    n_with_features=len(in_feat),
                )
                drug_reports.append(
                    {
                        "antibiotic": drug,
                        "training_status": "skipped",
                        "passes_eval": False,
                        "skip_reason": skip[0] if skip else "unknown",
                        "skip_detail": skip[1] if skip else "Model not trained.",
                        "failure_reasons": [skip[1]] if skip else ["Model not trained."],
                    }
                )
                continue

            bundle = joblib.load(trained[drug])
            if bundle.get("n_features", n_features) != n_features:
                drug_reports.append(
                    {
                        "antibiotic": drug,
                        "training_status": "skipped",
                        "passes_eval": False,
                        "skip_reason": "stale_model_features",
                        "skip_detail": (
                            f"Saved model has {bundle.get('n_features')} features but "
                            f"current matrix has {n_features}. Re-run train_models.py."
                        ),
                        "failure_reasons": ["Model feature dimension mismatch."],
                    }
                )
                continue
            model = CalibratedRandomForest.from_bundle(bundle)
            idxs, ys, gids, split_names = [], [], [], []
            for _, row in in_feat.iterrows():
                gid = row["genome_id"]
                idxs.append(gid_to_row[gid])
                ys.append(int(row["y"]))
                gids.append(gid)
                split_names.append(splits[gid])

            X = X_all[idxs]
            y = np.array(ys)
            split_arr = np.array(split_names)
            train_m = split_arr == "train"
            test_m = split_arr == "test"
            target_ok = np.array([
                passes_target_gate(self.paths.fasta_dir / f"{g}.fna")[0]
                if (self.paths.fasta_dir / f"{g}.fna").exists() else False
                for g in gids
            ])

            metrics = evaluate_drug_model(model, X[test_m], y[test_m], target_ok[test_m])
            test_resist = int(y[test_m].sum())
            test_susc = int((1 - y[test_m]).sum())
            train_resist = int(y[train_m].sum())

            issues = metric_quality_issues(
                n_test=int(test_m.sum()),
                test_resistant=test_resist,
                test_susceptible=test_susc,
                n_train=int(train_m.sum()),
                train_resistant=train_resist,
                recall_resistant=metrics.get("recall_resistant"),
            )
            passes = test_resist >= 1 and test_susc >= 1 and int(test_m.sum()) >= 5
            if metrics.get("recall_resistant") == 0.0 and test_resist > 0:
                passes = False

            drug_reports.append(
                {
                    "antibiotic": drug,
                    "training_status": "trained",
                    "passes_eval": passes,
                    "metrics": {
                        "balanced_accuracy_called": metrics.get("balanced_accuracy_called"),
                        "f1_called": metrics.get("f1_called"),
                        "recall_resistant": metrics.get("recall_resistant"),
                        "recall_susceptible": metrics.get("recall_susceptible"),
                        "brier": metrics.get("brier"),
                        "auroc": metrics.get("auroc"),
                        "pr_auc": metrics.get("pr_auc"),
                        "no_call_rate": metrics.get("no_call_rate"),
                        "n_train": int(train_m.sum()),
                        "n_test": int(test_m.sum()),
                        "test_resistant": test_resist,
                        "test_susceptible": test_susc,
                    },
                    "quality_status": "pass" if passes and not issues else ("warn" if issues else "pass"),
                    "failure_reasons": issues if issues else [],
                    "pass_detail": (
                        "Test split includes both resistant and susceptible genomes with adequate size."
                        if passes
                        else "Evaluation criteria not met — see failure_reasons."
                    ),
                }
            )

        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": "random_forest + isotonic/sigmoid calibration",
            "cohort": {
                "n_genomes_with_features": len(genome_ids),
                "n_genomes_labeled_total": int(labels.genome_id.nunique()),
                "failure_reasons": self._cohort_issues(len(genome_ids)),
            },
            "drugs": drug_reports,
        }

    def _cohort_issues(self, n_featured: int) -> list[str]:
        issues: list[str] = []
        if n_featured < 100:
            issues.append(
                f"Only {n_featured} genomes have AMRFinder features (target ~3000). "
                "Metrics are interim, not submission-ready."
            )
        return issues

    def write_report(self, out_path: Path) -> dict:
        report = self.build_report()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n")
        return report
