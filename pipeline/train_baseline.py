"""train_baseline.py — first end-to-end per-drug baseline for Genome Firewall.

Per drug: elastic-net logistic regression (saga, l1_ratio=0.5,
class_weight='balanced', standardized features) on the AMRFinderPlus feature
matrix, restricted to genomes in features ∩ labels ∩ splits. Platt
calibration on the CALIBRATION split only (pipeline.calibrate), asymmetric
split-conformal no-call bands + ANI-distance hard override (pipeline.nocall,
defaults), then the full CONTRACT evaluation seen vs heldout_group
(pipeline.metrics.evaluate_all -> reports/metrics.json + reliability PNGs).

Calibration-starvation fallback: Platt on a near-empty positive class is
degenerate (v1 run: gentamicin had 1 R in calibration; the sigmoid collapsed
all probabilities below 0.5 -> R-recall exactly 0 despite AUROC ~0.92-1.0).
When the calibration split holds fewer than --min-cal-r resistant genomes,
Platt is skipped and a calibration-free operating point is used instead:
out-of-fold probabilities from GroupKFold (groups = ANI cluster) over the
train split, threshold tau* = argmax balanced accuracy, applied as a fixed
logit shift mapping tau* -> 0.5 (rank-preserving; probabilities are then
NOT calibrated, only re-centered — documented in artifacts/summary).
Conformal no-call bands are still fitted on the calibration split with the
shifted probabilities (the shift is a fixed, train-only transform).

Target-locus callability gate (pipeline.target_gate): a "likely to work"
call may never rest solely on "no resistance marker found". Post-hoc, per
drug: curated point-mutation loci (ciprofloxacin: gyrA/parC/parE) must be
callable (AMRFinderPlus row at the locus, or the locus k-mer-verified in
the assembly); drugs without curated loci get an assembly-QC gate and are
labeled absence-of-evidence. Non-callable flips "likely to work" to
no-call ("target locus not callable"); flips are counted per drug
(train_summary.json "gate_flips") and per-genome statuses go to
demo/data/gate_status.json. Deterministic layer; probabilities unchanged.

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
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import (
    GroupKFold,
    cross_val_predict,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pipeline import calibrate, metrics, nocall, splits as splits_mod, target_gate

DRUGS = [
    "ciprofloxacin",
    "gentamicin",
    "ampicillin",
    "trimethoprim/sulfamethoxazole",
    "cefotaxime",
]

DEFAULT_MIN_CAL_R = 5  # below this many R in calibration, Platt is degenerate


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


class ShiftedProba:
    """Calibration-free operating point: fixed logit shift mapping tau* -> 0.5.

    Wraps a fitted estimator; predict_proba returns sigmoid(logit(p) -
    logit(tau*)). Rank-preserving, so AUROC/PR-AUC are unaffected; Brier is
    NOT calibrated by construction (documented wherever this is used).
    """

    def __init__(self, model, tau: float):
        self.model = model
        self.tau = float(tau)

    def predict_proba(self, X) -> np.ndarray:
        p = np.clip(self.model.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
        z = np.log(p / (1 - p)) - np.log(self.tau / (1 - self.tau))
        p1 = 1.0 / (1.0 + np.exp(-z))
        return np.column_stack([1.0 - p1, p1])


def grouped_cv_threshold(model, X_tr, y_tr, groups_tr, seed: int,
                         n_splits: int = 5) -> float:
    """tau* = argmax_t balanced_accuracy over grouped out-of-fold probs."""
    n_splits = max(2, min(n_splits, len(set(groups_tr))))
    cv = GroupKFold(n_splits=n_splits)
    oof = cross_val_predict(make_model(seed), X_tr, y_tr, groups=groups_tr,
                            cv=cv, method="predict_proba")[:, 1]
    grid = np.unique(np.quantile(oof, np.linspace(0.01, 0.99, 99)))
    yv = np.asarray(y_tr)
    best_tau, best_ba = 0.5, -1.0
    for t in grid:
        ba = balanced_accuracy_score(yv, (oof >= t).astype(int))
        if ba > best_ba:
            best_ba, best_tau = ba, float(t)
    print(f"  grouped-CV fallback: tau*={best_tau:.4f} "
          f"(OOF bal_acc={best_ba:.3f}, {n_splits} folds)", file=sys.stderr)
    return best_tau


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
    ap.add_argument("--min-cal-r", type=int, default=DEFAULT_MIN_CAL_R,
                    help="min R genomes in calibration for Platt; below this, "
                         "use the grouped-CV threshold fallback")
    ap.add_argument("--out-reports", default="reports")
    ap.add_argument("--out-models", default="models")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-gate", action="store_true",
                    help="disable the target-locus callability gate")
    ap.add_argument("--gate-tsv-dir", default="features/amrfinder")
    ap.add_argument("--gate-fna-dir", default="data/genomes")
    ap.add_argument("--gate-mutall-dir", default="features/amrfinder_mutall",
                    help="optional --mutation_all TSVs (used if dir exists)")
    ap.add_argument("--gate-demo-out", default="demo/data/gate_status.json",
                    help="gate panel JSON for the demo; '' skips writing")
    args = ap.parse_args(argv)
    drugs = args.drugs.split(",")

    fm = pd.read_csv(args.features, dtype={"genome_id": str}, index_col="genome_id")
    labels_all = pd.read_csv(args.labels, dtype={"genome_id": str})
    splits = splits_mod.load_splits(args.splits)
    edges = splits_mod.parse_skani_edges(args.edges)
    split_of = pd.Series({g: v["split"] for g, v in splits.items()})
    cluster_of = {g: v["cluster_id"] for g, v in splits.items()}
    train_genomes = {g for g, v in splits.items() if v["split"] == "train"}
    cl_sizes = pd.Series(cluster_of).value_counts()
    print(f"features: {fm.shape[0]} genomes x {fm.shape[1]} cols; "
          f"splits: {len(splits)} genomes "
          f"({split_of.value_counts().to_dict()})", file=sys.stderr)
    print(f"top clusters (id:size): {cl_sizes.head(8).to_dict()}", file=sys.stderr)

    probabilities, labels_eval, masks = {}, {}, {}
    summary_rows = []
    gap_result = None
    gate = None
    if not args.no_gate:
        gate = target_gate.Gate(args.gate_tsv_dir, args.gate_fna_dir,
                                args.gate_mutall_dir)
    gate_report: dict[str, dict[str, dict]] = {}
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
        cl_s = pd.Series(cluster_of)
        r_top = {int(c): int(y[cl_s[y.index] == c].sum())
                 for c in cl_sizes.head(3).index}
        print(f"\n== {drug}: n={len(y)} (R={int(y.sum())}) per-split n={counts} "
              f"R={r_counts} | R in top-3 clusters={r_top}", file=sys.stderr)
        if (sp == "calibration").sum() == 0 or y[sp == "calibration"].nunique() < 2:
            print(f"  SKIP {drug}: calibration split missing or single-class",
                  file=sys.stderr)
            continue

        X_tr, y_tr = X[sp == "train"], y[sp == "train"]
        X_cal, y_cal = X[sp == "calibration"], y[sp == "calibration"]
        model = fit_with_convergence_check(make_model(args.seed), X_tr, y_tr, drug)

        if int(y_cal.sum()) >= args.min_cal_r:
            cal_method, tau = "platt", None
            cal = calibrate.platt_calibrate(model, X_cal, y_cal)
        else:
            cal_method = "grouped_cv_threshold"
            tau = grouped_cv_threshold(
                model, X_tr, y_tr, [cluster_of[g] for g in X_tr.index], args.seed)
            cal = ShiftedProba(model, tau)
            print(f"  FALLBACK [{drug}]: only {int(y_cal.sum())} R in calibration "
                  f"-> grouped-CV threshold (no Platt); probabilities are "
                  f"re-centered, not calibrated", file=sys.stderr)

        p_cal = cal.predict_proba(X_cal)[:, 1]
        bands = nocall.fit_conformal_bands(p_cal, y_cal.values)
        dist = nearest_train_distances(edges, train_genomes, genomes)
        d_cal = np.array([dist[g] for g in X_cal.index])
        bands.dist_threshold = nocall.fit_distance_threshold(d_cal)

        p_all = cal.predict_proba(X)[:, 1]
        d_all = np.array([dist[g] for g in genomes])
        mask = nocall.apply_nocall(p_all, bands, d_all)

        # target-locus callability gate: post-hoc override on "likely to
        # work" calls only (synthesis v2 change 4; never a silent pass).
        n_gate_flips = 0
        if gate is not None:
            statuses = {g: gate.gate_status(g, drug) for g in genomes}
            mask, n_gate_flips = target_gate.apply_gate_override(
                p_all, bands, mask, [statuses[g]["status"] for g in genomes])
            gate_report[drug] = statuses
            st_counts = pd.Series([s["status"] for s in statuses.values()]
                                  ).value_counts().to_dict()
            print(f"  gate [{drug}]: {n_gate_flips} 'likely to work' call(s) "
                  f"flipped to no-call ({target_gate.NO_CALL_REASON}); "
                  f"statuses={st_counts}", file=sys.stderr)

        probabilities[drug] = dict(zip(genomes, p_all))
        labels_eval[drug] = dict(zip(genomes, y.values.astype(float)))
        masks[drug] = dict(zip(genomes, mask.astype(bool)))

        mdir = Path(args.out_models) / safe_name(drug)
        mdir.mkdir(parents=True, exist_ok=True)
        with open(mdir / "baseline.pkl", "wb") as fh:
            pickle.dump({"model": model, "calibrated": cal,
                         "bands": bands.to_dict(), "drug": drug,
                         "calibration_method": cal_method, "tau": tau,
                         "n_train": len(y_tr), "n_cal": len(y_cal)}, fh)
        bands.save(mdir / "nocall_bands.json")
        n_selected = int((model.named_steps["lr"].coef_[0] != 0).sum())
        print(f"  band=[{bands.band[0]:.3f},{bands.band[1]:.3f}] "
              f"dist_thr={bands.dist_threshold:.2f} selected={n_selected}/"
              f"{X.shape[1]} features cal={cal_method}", file=sys.stderr)
        summary_rows.append({"drug": drug, "n": len(y), "n_R": int(y.sum()),
                             **{f"n_{k}": v for k, v in counts.items()},
                             **{f"nR_{k}": v for k, v in r_counts.items()},
                             "calibration_method": cal_method, "tau": tau,
                             "n_features_selected": n_selected,
                             "gate_flips": n_gate_flips})

    if not probabilities:
        print("no drugs evaluated", file=sys.stderr)
        return 1

    results = metrics.evaluate_all(
        probabilities, labels_eval, splits, masks, out_dir=args.out_reports)
    (Path(args.out_reports) / "train_summary.json").write_text(
        json.dumps(summary_rows, indent=1) + "\n")

    if gate is not None and args.gate_demo_out:
        target_gate.write_gate_json(gate_report, args.gate_demo_out)
        print(f"gate status -> {args.gate_demo_out} "
              f"({len(gate_report)} drugs)", file=sys.stderr)

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
