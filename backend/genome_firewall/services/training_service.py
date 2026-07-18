from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse

from genome_firewall.config import DEFAULT_MODEL, DEFAULT_PATHS, ModelConfig, Paths
from genome_firewall.layer1_ingestion.cohort import load_drug_targets, load_labels, load_split
from genome_firewall.layer2_features.matrix import load_feature_store
from genome_firewall.layer3_model.random_forest import train_calibrated_random_forest
from genome_firewall.layer3_model.target_gate import passes_target_gate
from genome_firewall.layer5_evaluation.metrics import evaluate_drug_model


class TrainingService:
    def __init__(
        self,
        paths: Paths = DEFAULT_PATHS,
        model_config: ModelConfig = DEFAULT_MODEL,
    ) -> None:
        self.paths = paths
        self.model_config = model_config

    def train_all(self) -> dict[str, dict]:
        labels = load_labels(self.paths.labels)
        splits = load_split(self.paths.splits_dir / "genome_split.tsv")
        genome_ids, X_all, catalog = load_feature_store(self.paths.features_dir)
        gid_to_row = {g: i for i, g in enumerate(genome_ids)}
        feature_names = catalog["feature_id"].tolist()
        drug_targets = load_drug_targets(self.paths.drug_targets)

        self.paths.models_dir.mkdir(parents=True, exist_ok=True)
        metrics_all: dict[str, dict] = {}
        trained_drugs: set[str] = set()

        for drug in sorted(labels["antibiotic"].unique()):
            rows, ys, gids, split_names = [], [], [], []
            for _, row in labels[labels["antibiotic"] == drug].iterrows():
                gid = row["genome_id"]
                if gid not in gid_to_row or gid not in splits:
                    continue
                rows.append(gid_to_row[gid])
                ys.append(int(row["y"]))
                gids.append(gid)
                split_names.append(splits[gid])

            y = np.array(ys)
            n_resist = int(y.sum())
            n_susc = int(len(y) - n_resist)
            if len(set(ys)) < 2:
                print(f"[skip] {drug}: only one class (R={n_resist}, S={n_susc})")
                continue
            if n_resist < self.model_config.min_train_per_class:
                print(
                    f"[skip] {drug}: too few resistant examples for stable training "
                    f"(R={n_resist}, need >={self.model_config.min_train_per_class})"
                )
                continue
            if len(rows) < 15:
                print(f"[skip] {drug}: insufficient labeled genomes ({len(rows)})")
                continue

            X = X_all[rows]
            split_arr = np.array(split_names)
            train_m = split_arr == "train"
            cal_m = split_arr == "calibration"
            test_m = split_arr == "test"

            if train_m.sum() < 8:
                print(f"[skip] {drug}: train split too small ({train_m.sum()})")
                continue
            train_resist = int(y[train_m].sum())
            train_susc = int((1 - y[train_m]).sum())
            if train_resist < self.model_config.min_train_per_class:
                print(
                    f"[skip] {drug}: too few resistant in train split "
                    f"(R={train_resist}, need >={self.model_config.min_train_per_class})"
                )
                continue
            if train_susc < self.model_config.min_train_per_class:
                print(f"[skip] {drug}: too few susceptible in train split (S={train_susc})")
                continue
            if cal_m.sum() < 3:
                cal_m = train_m
            if test_m.sum() < 3:
                test_m = cal_m

            test_resist = int(y[test_m].sum())
            test_susc = int((1 - y[test_m]).sum())
            if test_resist < self.model_config.min_test_per_class:
                print(
                    f"[warn] {drug}: test split has only {test_resist} resistant "
                    f"(S={test_susc}) — metrics may not reflect resistant recall"
                )

            model = train_calibrated_random_forest(
                X[train_m],
                y[train_m],
                X[cal_m],
                y[cal_m],
                feature_names,
                self.model_config,
            )

            target_ok = np.array(
                [
                    passes_target_gate(self.paths.fasta_dir / f"{gid}.fna")[0]
                    if (self.paths.fasta_dir / f"{gid}.fna").exists()
                    else False
                    for gid in gids
                ]
            )
            drug_metrics = evaluate_drug_model(model, X[test_m], y[test_m], target_ok[test_m])
            drug_metrics.update(
                {
                    "n_train": int(train_m.sum()),
                    "n_calibration": int(cal_m.sum()),
                    "n_test": int(test_m.sum()),
                    "test_resistant": test_resist,
                    "test_susceptible": test_susc,
                    "train_resistant": int(y[train_m].sum()),
                    "train_susceptible": int((1 - y[train_m]).sum()),
                    "calibration_method_used": model.calibration_method,
                }
            )
            metrics_all[drug] = drug_metrics

            bundle = model.to_bundle()
            bundle["drug"] = drug
            bundle["target_genes"] = drug_targets.get(drug, [])
            bundle["metrics"] = drug_metrics
            bundle["n_features"] = len(feature_names)
            out = self.paths.models_dir / f"{drug.replace('/', '_')}_model.joblib"
            joblib.dump(bundle, out)
            trained_drugs.add(drug)
            bal = drug_metrics.get("balanced_accuracy_called")
            bal_s = f"{bal:.3f}" if bal is not None else "n/a"
            print(
                f"[ok] {drug}: bal_acc={bal_s} "
                f"rec_R={drug_metrics.get('recall_resistant')} "
                f"test_R/S={test_resist}/{test_susc}"
            )

        for path in self.paths.models_dir.glob("*_model.joblib"):
            bundle = joblib.load(path)
            if bundle.get("drug") not in trained_drugs:
                path.unlink()

        summary = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": self.model_config.algorithm,
            "calibration_method": self.model_config.calibration_method,
            "no_call_band": [self.model_config.no_call_low, self.model_config.no_call_high],
            "small_data_optimizations": [
                "regularized RF (max_depth=12, min_samples_leaf=5)",
                "minority oversampling on train split",
                "sigmoid calibration when cal n < 25",
                "wider no-call band (0.35-0.65)",
            ],
            "drugs": metrics_all,
        }
        summary_path = self.paths.models_dir / "metrics.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        return metrics_all
