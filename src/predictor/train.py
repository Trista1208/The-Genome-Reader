from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    recall_score,
    roc_auc_score,
)
from sklearn.neighbors import NearestNeighbors

from src.common import SUPPORTED_ANTIBIOTICS, write_json
from src.genome_reader.encoding import load_feature_bundle
from src.predictor.calibration import ProbabilityCalibrator, choose_ambiguity_band
from src.predictor.model import DrugModel
from src.splitting.check_group_integrity import (
    assert_group_integrity,
    assert_label_integrity,
    load_genomes,
)


def _align_labels(labels: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    indexed_samples = samples.reset_index(names="feature_row")
    joined = labels.merge(
        indexed_samples[["genome_id", "feature_row", "split", "genetic_group"]],
        on="genome_id",
        how="inner",
        suffixes=("", "_features"),
        validate="many_to_one",
    )
    mismatch = (joined["split"] != joined["split_features"]) | (
        joined["genetic_group"] != joined["genetic_group_features"]
    )
    if mismatch.any():
        raise ValueError("Feature samples do not preserve label split/genetic_group assignments")
    return joined


def _binary_metrics(y: np.ndarray, probability: np.ndarray) -> dict:
    prediction = probability >= 0.5
    result = {
        "n": int(len(y)),
        "resistant": int(y.sum()),
        "susceptible": int((1 - y).sum()),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "resistant_recall": float(recall_score(y, prediction, pos_label=1, zero_division=0)),
        "susceptible_recall": float(recall_score(y, prediction, pos_label=0, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "brier": float(brier_score_loss(y, probability)),
    }
    if np.unique(y).size == 2:
        result["auroc"] = float(roc_auc_score(y, probability))
        result["pr_auc"] = float(average_precision_score(y, probability))
    return result


def _selective_metrics(y: np.ndarray, prediction: dict) -> dict:
    called = ~prediction["no_call"]
    result = {
        "coverage": float(called.mean()),
        "no_call_rate": float(prediction["no_call"].mean()),
        "ood_rate": float(prediction["ood"].mean()),
        "ambiguous_rate": float(prediction["ambiguous"].mean()),
        "called_n": int(called.sum()),
    }
    if called.sum() and np.unique(y[called]).size == 2:
        result["called_balanced_accuracy"] = float(
            balanced_accuracy_score(y[called], prediction["resistant_probability"][called] >= 0.5)
        )
    return result


def _group_metrics(frame: pd.DataFrame, probabilities: np.ndarray, minimum_group_size: int = 5) -> dict:
    output = {}
    for group, indices in frame.groupby("genetic_group", observed=True).indices.items():
        positions = np.asarray(indices)
        if len(positions) < minimum_group_size:
            continue
        y = frame.iloc[positions]["target_resistant"].to_numpy(dtype=int)
        output[str(group)] = _binary_metrics(y, probabilities[positions])
    return output


def train_drug(
    antibiotic: str,
    frame: pd.DataFrame,
    matrix,
    feature_names: list[str],
    c_value: float,
    calibration_method: str,
    minimum_coverage: float,
    seed: int,
) -> tuple[DrugModel, dict]:
    subsets = {name: data.reset_index(drop=True) for name, data in frame.groupby("split", observed=True)}
    missing = {"train", "calibration", "test"} - set(subsets)
    if missing:
        raise ValueError(f"{antibiotic} is missing splits: {sorted(missing)}")
    selected = {}
    for split, data in subsets.items():
        rows = data["feature_row"].to_numpy(dtype=int)
        selected[split] = (data, matrix[rows], data["target_resistant"].to_numpy(dtype=int))
        counts = np.bincount(selected[split][2], minlength=2)
        minimum = 10 if split == "train" else 5
        if counts.min() < minimum:
            raise ValueError(f"{antibiotic} {split} has insufficient class support: {counts.tolist()}")

    train_frame, x_train, y_train = selected["train"]
    cal_frame, x_cal, y_cal = selected["calibration"]
    test_frame, x_test, y_test = selected["test"]

    classifier = LogisticRegression(
        C=c_value,
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=seed,
    ).fit(x_train, y_train)
    calibrator = ProbabilityCalibrator(calibration_method).fit(classifier.decision_function(x_cal), y_cal)

    novelty_model = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=2).fit(x_train)
    train_neighbor_distances = novelty_model.kneighbors(x_train, n_neighbors=2, return_distance=True)[0][:, 1]
    novelty_threshold = float(np.quantile(train_neighbor_distances, 0.99))
    cal_novelty = novelty_model.kneighbors(x_cal, n_neighbors=1, return_distance=True)[0][:, 0]
    cal_probability = calibrator.predict(classifier.decision_function(x_cal))
    low, high, threshold_metrics = choose_ambiguity_band(
        cal_probability, y_cal, cal_novelty > novelty_threshold, minimum_coverage
    )

    model = DrugModel(
        antibiotic=antibiotic,
        classifier=classifier,
        calibrator=calibrator,
        novelty_model=novelty_model,
        novelty_threshold=novelty_threshold,
        no_call_low=low,
        no_call_high=high,
        feature_names=feature_names,
    )
    test_prediction = model.predict(x_test)
    metrics = {
        "antibiotic": antibiotic,
        "class_counts": {
            split: {
                "n": int(len(y)),
                "resistant": int(y.sum()),
                "susceptible": int((1 - y).sum()),
            }
            for split, (_frame, _x, y) in selected.items()
        },
        "calibration_method": calibrator.fitted_method,
        "novelty_threshold": novelty_threshold,
        "no_call_band": [low, high],
        "calibration_threshold_selection": threshold_metrics,
        "test": {
            **_binary_metrics(y_test, test_prediction["resistant_probability"]),
            **_selective_metrics(y_test, test_prediction),
        },
        "test_by_genetic_group": _group_metrics(test_frame, test_prediction["resistant_probability"]),
    }
    return model, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train calibrated per-antibiotic baseline models.")
    parser.add_argument("--features", required=True, help="Feature-bundle directory")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--genomes", required=True)
    parser.add_argument("--output", default="models")
    parser.add_argument("--antibiotics", nargs="+", default=list(SUPPORTED_ANTIBIOTICS))
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--calibration", choices=["auto", "platt", "isotonic"], default="auto")
    parser.add_argument("--minimum-coverage", type=float, default=0.70)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()

    genomes = load_genomes(args.genomes)
    assert_group_integrity(genomes)
    labels = assert_label_integrity(args.labels, genomes)
    matrix, samples, feature_names, feature_metadata = load_feature_bundle(args.features)
    joined = _align_labels(labels, samples)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    all_metrics = {}
    for antibiotic in args.antibiotics:
        frame = joined.loc[joined["antibiotic"] == antibiotic].copy()
        if frame.empty:
            raise ValueError(f"No labels found for {antibiotic}")
        model, metrics = train_drug(
            antibiotic, frame, matrix, feature_names, args.c, args.calibration,
            args.minimum_coverage, args.seed,
        )
        joblib.dump(model, output / f"{antibiotic.replace('/', '_')}.joblib")
        all_metrics[antibiotic] = metrics
        print(
            f"{antibiotic}: test balanced accuracy={metrics['test']['balanced_accuracy']:.3f}, "
            f"coverage={metrics['test']['coverage']:.3f}"
        )

    write_json(
        output / "training_report.json",
        {
            "model_version": "0.1.0",
            "seed": args.seed,
            "feature_metadata": feature_metadata,
            "antibiotics": all_metrics,
            "safety": "Research only; confirm every prediction with standard laboratory testing.",
        },
    )


if __name__ == "__main__":
    main()
