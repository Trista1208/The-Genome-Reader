"""train_baseline.py — first end-to-end per-drug baseline for Genome Firewall.

Per drug: elastic-net logistic regression (saga, l1_ratio=0.5,
class_weight='balanced', standardized features) on the AMRFinderPlus feature
matrix, restricted to genomes in features ∩ labels ∩ splits. Platt
calibration on the CALIBRATION split only (pipeline.calibrate), asymmetric
split-conformal no-call bands + ANI-distance hard override (pipeline.nocall,
defaults), then the full CONTRACT evaluation seen vs heldout_group
(pipeline.metrics.evaluate_all -> reports/metrics.json + reliability PNGs).

Also computes the random-split-vs-grouped gap for --gap-drug: the same model
trained on a stratified random row-wise 80/20 split vs the grouped protocol
(demo statistic for why split discipline matters).

Usage (from repo root):
  pipeline/.venv/bin/python -m pipeline.train_baseline \
    --features features/feature_matrix.csv \
    --labels data/clean/labels_clean_ecoli.csv \
    --splits splits/splits.json --edges splits/skani_edges.tsv \
    --out-reports reports --out-models models
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pipeline import calibrate, metrics, nocall, splits as splits_mod

DRUGS = [
    "ciprofloxacin",
    "gentamicin",
    "ampicillin",
    "trimethoprim/sulfamethoxazole",
    "cefotaxime",
]


def safe_name(drug: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", drug)


def make_model(seed: int = 0) -> Pipeline:
    """StandardScaler + elastic-net LR. Dense is fine at this size."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            penalty="elasticnet", solver="saga", l1_ratio=0.5, C=1.0,
            class_weight="balanced", max_iter=10000, tol=1e-4,
            random_state=seed,
        )),
    ])


def fit_with_convergence_check(model: Pipeline, X, y, drug: str) -> Pipeline:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(X, y)
    for w in caught:
        if issubclass(w.category, ConvergenceWarning):
            print(f"  WARNING [{drug}]: saga did not converge at max_iter="
                  f"{model.named_steps['lr'].max_iter}", file=sys.stderr)
    return model


def nearest_train_distances(edges: pd.DataFrame, train_genomes: set[str],
                            genomes: list[str]) -> dict[str, float]:
    """100 - max skani ANI to the nearest *other* training genome.

    Genomes with no edge to any training genome get 100.0 (beyond skani's
    reporting cutoff => far); self edges (ANI 100, from --diagonal) excluded.
    """
    e = edges[edges["ref"] != edges["query"]]
    in_train_r = e["ref"].isin(train_genomes)
    in_train_q = e["query"].isin(train_genomes)
    cand = pd.concat([
        e[in_train_r][["query", "ani"]].rename(columns={"query": "g"}),
        e[in_train_q][["ref", "ani"]].rename(columns={"ref": "g"}),
    ])
    mx = cand.groupby("g")["ani"].max()
    return {g: 100.0 - float(mx.get(g, 0.0)) for g in genomes}


def block_metrics(y, p) -> dict:
    m = metrics.binary_metrics(np.asarray(y), np.asarray(p))
    return {k: m[k] for k in
            ("n", "n_resistant", "n_susceptible", "balanced_accuracy",
             "recall_resistant", "recall_susceptible", "auroc", "pr_auc", "brier")}


def random_vs_grouped_gap(drug: str, X, y, splits_of, seed: int = 0) -> dict:
    """Same model, random row-wise 80/20 split vs grouped splits (uncalibrated).

    Compares out-of-sample metrics on the random 20% against the grouped
    `test` and `heldout_group` genomes (grouped model also uncalibrated, so
    the only difference is the splitting discipline).
    """
    # random protocol
    idx_tr, idx_te = train_test_split(
        np.arange(len(y)), test_size=0.2, random_state=seed, stratify=y)
    rnd = fit_with_convergence_check(
        make_model(seed), X.iloc[idx_tr], y.iloc[idx_tr], f"{drug}/random")
    p_rnd = rnd.predict_proba(X.iloc[idx_te])[:, 1]
    out = {"random_80_20": block_metrics(y.iloc[idx_te], p_rnd)}

    # grouped protocol (same model class, grouped train split)
    split_names = splits_of[y.index]
    tr = split_names == "train"
    grp = fit_with_convergence_check(
        make_model(seed), X[tr], y[tr], f"{drug}/grouped")
    for name, mask in (("grouped_test", split_names == "test"),
                       ("grouped_heldout_group", split_names == "heldout_group")):
        if mask.sum():
            out[name] = block_metrics(y[mask], grp.predict_proba(X[mask])[:, 1])
    for key in ("grouped_test", "grouped_heldout_group"):
        if key in out:
            out[f"gap_random_minus_{key}"] = {
                m: (out["random_80_20"][m] - out[key][m])
                for m in ("balanced_accuracy", "auroc")
                if not (np.isnan(out["random_80_20"][m]) or np.isnan(out[key][m]))
            }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--features", default="features/feature_matrix.csv")
    ap.add_argument("--labels", default="data/clean/labels_clean_ecoli.csv")
    ap.add_argument("--splits", default="splits/splits.json")
    ap.add_argument("--edges", default="splits/skani_edges.tsv")
    ap.add_argument("--drugs", default=",".join(DRUGS))
    ap.add_argument("--gap-drug", default="ciprofloxacin")
    ap.add_argument("--out-reports", default="reports")
    ap.add_argument("--out-models", default="models")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    drugs = args.drugs.split(",")

    fm = pd.read_csv(args.features, dtype={"genome_id": str}, index_col="genome_id")
    labels_all = pd.read_csv(args.labels, dtype={"genome_id": str})
    splits = splits_mod.load_splits(args.splits)
    edges = splits_mod.parse_skani_edges(args.edges)
    split_of = pd.Series({g: v["split"] for g, v in splits.items()})
    train_genomes = {g for g, v in splits.items() if v["split"] == "train"}
    print(f"features: {fm.shape[0]} genomes x {fm.shape[1]} cols; "
          f"splits: {len(splits)} genomes "
          f"({split_of.value_counts().to_dict()})", file=sys.stderr)

    probabilities, labels_eval, masks = {}, {}, {}
    summary_rows = []
    gap_result = None
    for drug in drugs:
        lab = labels_all[labels_all["antibiotic"] == drug]
        y = pd.Series(lab["label"].astype(int).values,
                      index=lab["genome_id"].values)
        y = y[~y.index.duplicated(keep="first")]
        genomes = sorted(set(y.index) & set(fm.index) & set(splits.keys()))
        y = y[genomes]
        X = fm.loc[genomes]
        sp = split_of[genomes]
        counts = {s: int((sp == s).sum()) for s in
                  ("train", "calibration", "test", "heldout_group")}
        r_counts = {s: int(((sp == s) & (y == 1)).sum()) for s in counts}
        print(f"\n== {drug}: n={len(y)} (R={int(y.sum())}) per-split n={counts} "
              f"R={r_counts}", file=sys.stderr)
        if (sp == "calibration").sum() == 0 or y[sp == "calibration"].nunique() < 2:
            print(f"  SKIP {drug}: calibration split missing or single-class",
                  file=sys.stderr)
            continue

        X_tr, y_tr = X[sp == "train"], y[sp == "train"]
        X_cal, y_cal = X[sp == "calibration"], y[sp == "calibration"]
        model = fit_with_convergence_check(make_model(args.seed), X_tr, y_tr, drug)
        cal = calibrate.platt_calibrate(model, X_cal, y_cal)

        p_cal = cal.predict_proba(X_cal)[:, 1]
        bands = nocall.fit_conformal_bands(p_cal, y_cal.values)
        dist = nearest_train_distances(edges, train_genomes, genomes)
        d_cal = np.array([dist[g] for g in X_cal.index])
        bands.dist_threshold = nocall.fit_distance_threshold(d_cal)

        p_all = cal.predict_proba(X)[:, 1]
        d_all = np.array([dist[g] for g in genomes])
        mask = nocall.apply_nocall(p_all, bands, d_all)

        probabilities[drug] = dict(zip(genomes, p_all))
        labels_eval[drug] = dict(zip(genomes, y.values.astype(float)))
        masks[drug] = dict(zip(genomes, mask.astype(bool)))

        mdir = Path(args.out_models) / safe_name(drug)
        mdir.mkdir(parents=True, exist_ok=True)
        with open(mdir / "baseline.pkl", "wb") as fh:
            pickle.dump({"model": model, "calibrated": cal,
                         "bands": bands.to_dict(), "drug": drug,
                         "n_train": len(y_tr), "n_cal": len(y_cal)}, fh)
        bands.save(mdir / "nocall_bands.json")
        n_selected = int((model.named_steps["lr"].coef_[0] != 0).sum())
        print(f"  band=[{bands.band[0]:.3f},{bands.band[1]:.3f}] "
              f"dist_thr={bands.dist_threshold:.2f} selected={n_selected}/"
              f"{X.shape[1]} features", file=sys.stderr)
        summary_rows.append({"drug": drug, "n": len(y), "n_R": int(y.sum()),
                             **{f"n_{k}": v for k, v in counts.items()},
                             "n_features_selected": n_selected})

    if not probabilities:
        print("no drugs evaluated", file=sys.stderr)
        return 1

    results = metrics.evaluate_all(
        probabilities, labels_eval, splits, masks, out_dir=args.out_reports)
    (Path(args.out_reports) / "train_summary.json").write_text(
        json.dumps(summary_rows, indent=1) + "\n")

    if args.gap_drug in drugs:
        lab = labels_all[labels_all["antibiotic"] == args.gap_drug]
        y = pd.Series(lab["label"].astype(int).values, index=lab["genome_id"].values)
        y = y[~y.index.duplicated(keep="first")]
        genomes = sorted(set(y.index) & set(fm.index) & set(splits.keys()))
        gap_result = random_vs_grouped_gap(
            args.gap_drug, fm.loc[genomes], y[genomes], split_of, args.seed)
        (Path(args.out_reports) / "random_vs_grouped.json").write_text(
            json.dumps({args.gap_drug: metrics._jsonable(gap_result)}, indent=1) + "\n")

    # compact stdout table: seen vs heldout_group
    cols = ["drug", "group", "n", "n_R", "bal_acc", "rec_R", "rec_S",
            "auroc", "pr_auc", "brier", "nocall", "acc_after_nc"]
    print("\t".join(cols))
    for drug, res in results.items():
        for group in ("seen", "heldout_group"):
            g = res.get("groups", {}).get(group)
            if not g:
                continue
            row = [drug, group, g["n"], g["n_resistant"],
                   g["balanced_accuracy"], g["recall_resistant"],
                   g["recall_susceptible"], g["auroc"], g["pr_auc"],
                   g["brier"], g.get("no_call_rate"),
                   g.get("accuracy_after_no_call")]
            print("\t".join("NA" if v is None else
                            (f"{v:.3f}" if isinstance(v, float) else str(v))
                            for v in row))
    if gap_result:
        print("\nrandom-vs-grouped gap:", json.dumps(metrics._jsonable(gap_result), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
