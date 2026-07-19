"""Evaluation harness for Genome Firewall (CONTRACT.md: reports/).

Per drug, per split: balanced accuracy, recall per class (Resistant /
Susceptible), F1, AUROC, PR-AUC, Brier score, no-call rate,
accuracy-after-no-call, risk-coverage curve data, reliability-diagram data +
PNG. Per-group breakdown (seen clusters vs heldout_group). CIs are
bootstrap-over-groups (clusters resampled, not rows) because rows within an
ANI cluster are not independent.

Entry point: ``evaluate_all(probabilities, labels, splits, nocall_mask)``
-> dict, and writes reports/metrics.json + reports/reliability_{drug}.png.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)

EVAL_SPLITS = ("train", "calibration", "test", "heldout_group")
SEEN_SPLITS = ("train", "calibration", "test")


# --------------------------------------------------------------------------
# core metrics
# --------------------------------------------------------------------------

def binary_metrics(y_true, y_prob, threshold: float = 0.5) -> dict:
    """The CONTRACT metric suite for one (sub)sample. NaN where undefined."""
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    pred = (p >= threshold).astype(int)
    out = {
        "n": int(len(y)),
        "n_resistant": int((y == 1).sum()),
        "n_susceptible": int((y == 0).sum()),
        "balanced_accuracy": math.nan,
        "recall_resistant": math.nan,
        "recall_susceptible": math.nan,
        "f1": math.nan,
        "auroc": math.nan,
        "pr_auc": math.nan,
        "brier": math.nan,
    }
    if len(y) == 0:
        return out
    out["brier"] = float(brier_score_loss(y, p))
    n_r, n_s = int((y == 1).sum()), int((y == 0).sum())
    if n_r:
        out["recall_resistant"] = float(((pred == 1) & (y == 1)).sum() / n_r)
    if n_s:
        out["recall_susceptible"] = float(((pred == 0) & (y == 0)).sum() / n_s)
    if n_r and n_s:
        out["balanced_accuracy"] = float(balanced_accuracy_score(y, pred))
        out["f1"] = float(f1_score(y, pred))
        out["auroc"] = float(roc_auc_score(y, p))
        out["pr_auc"] = float(average_precision_score(y, p))
    return out


def apply_nocall_metrics(y_true, y_prob, nocall_mask, threshold: float = 0.5) -> dict:
    """No-call rate + accuracy-after-no-call (plain accuracy on called)."""
    y = np.asarray(y_true, dtype=float)
    pred = (np.asarray(y_prob, dtype=float) >= threshold).astype(int)
    mask = np.asarray(nocall_mask, dtype=bool)
    rate = float(mask.mean()) if len(mask) else math.nan
    called = ~mask
    acc_after = (
        float((pred[called] == y[called]).mean()) if called.any() else math.nan
    )
    return {
        "no_call_rate": rate,
        "n_called": int(called.sum()),
        "accuracy_after_no_call": acc_after,
    }


def risk_coverage(y_true, y_prob, nocall_mask=None, threshold: float = 0.5,
                  n_points: int = 20) -> dict:
    """Risk-coverage curve over CALLED genomes, confidence = max(p, 1-p).

    Returns parallel lists: coverage fraction, accuracy, balanced accuracy.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    if nocall_mask is not None:
        keep = ~np.asarray(nocall_mask, dtype=bool)
        y, p = y[keep], p[keep]
    conf = np.maximum(p, 1.0 - p)
    pred = (p >= threshold).astype(int)
    order = np.argsort(-conf, kind="stable")
    y, pred = y[order], pred[order]
    n = len(y)
    coverages, accs, bals = [], [], []
    for frac in np.linspace(1.0, max(1.0 / n, 0.05), n_points) if n else []:
        k = max(1, int(round(frac * n)))
        ys, ps_ = y[:k], pred[:k]
        coverages.append(k / n)
        accs.append(float((ys == ps_).mean()))
        bals.append(
            float(balanced_accuracy_score(ys, ps_))
            if len(np.unique(ys)) == 2 else math.nan
        )
    return {"coverage": coverages, "accuracy": accs, "balanced_accuracy": bals}


def reliability_data(y_true, y_prob, n_bins: int = 10) -> dict:
    """Equal-width-bin reliability diagram data."""
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    mean_pred, frac_pos, count = [], [], []
    for b in range(n_bins):
        sel = bins == b
        count.append(int(sel.sum()))
        mean_pred.append(float(p[sel].mean()) if sel.any() else math.nan)
        frac_pos.append(float(y[sel].mean()) if sel.any() else math.nan)
    return {
        "bin_edges": [float(e) for e in edges],
        "mean_predicted": mean_pred,
        "fraction_positive": frac_pos,
        "count": count,
    }


def plot_reliability(rel_by_group: dict[str, dict], path: str | Path,
                     title: str = "") -> Path:
    """PNG reliability diagram; one series per group (e.g. test, heldout)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for name, rel in rel_by_group.items():
        mp = np.array(rel["mean_predicted"], dtype=float)
        fp = np.array(rel["fraction_positive"], dtype=float)
        ok = ~np.isnan(mp)
        if ok.any():
            ax.plot(mp[ok], fp[ok], "o-", label=f"{name} (n={sum(rel['count'])})")
    ax.set_xlabel("mean predicted P(resistant)")
    ax.set_ylabel("observed fraction resistant")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(title or "reliability")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# bootstrap-over-groups CIs
# --------------------------------------------------------------------------

def bootstrap_group_ci(
    y_true,
    y_prob,
    groups,
    metric: str = "balanced_accuracy",
    n_boot: int = 1000,
    seed: int = 0,
    threshold: float = 0.5,
) -> list[float] | None:
    """Percentile CI resampling CLUSTERS with replacement, not rows.

    Resamples containing only one class are skipped (metric undefined).
    Returns [lo, hi] at 95%, or None when a CI is not computable.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    g = np.asarray(groups)
    uniq = np.unique(g)
    if len(uniq) < 2 or len(np.unique(y)) < 2:
        return None

    def _metric(yy, pp):
        pred = (pp >= threshold).astype(int)
        if metric == "balanced_accuracy":
            return balanced_accuracy_score(yy, pred)
        if metric == "auroc":
            return roc_auc_score(yy, pp)
        if metric == "brier":
            return brier_score_loss(yy, pp)
        raise ValueError(metric)

    rng = np.random.RandomState(seed)
    stats = []
    members = {u: np.where(g == u)[0] for u in uniq}
    for _ in range(n_boot):
        draw = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[u] for u in draw])
        if len(np.unique(y[idx])) < 2:
            continue
        stats.append(_metric(y[idx], p[idx]))
    if len(stats) < 20:
        return None
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return [float(lo), float(hi)]


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def _as_frame(obj, value_name: str) -> pd.DataFrame:
    """Normalize probabilities/labels/nocall to a genome x drug DataFrame."""
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, pd.Series):
        return obj.to_frame(name=value_name)
    if isinstance(obj, dict):
        if obj and all(isinstance(v, dict) for v in obj.values()):
            return pd.DataFrame(obj)  # {drug: {genome: value}}
        return pd.Series(obj, dtype="float64").to_frame(name=value_name)
    raise TypeError(f"unsupported probabilities/labels type: {type(obj)}")


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.floating, np.integer)):
        return _jsonable(obj.item())
    return obj


def _subset_frame(probs: pd.Series, labels: pd.Series, nocall, splits: dict) -> pd.DataFrame:
    df = pd.DataFrame({"p": probs, "y": labels})
    if nocall is not None:
        df["nocall"] = nocall.astype(bool)
    split_tbl = pd.DataFrame(splits).T  # genome -> {cluster_id, coarse_clade_id, split}
    df = df.join(split_tbl[["cluster_id", "split"]], how="left")
    df = df.dropna(subset=["p", "y"])
    return df


def evaluate_all(
    probabilities,
    labels,
    splits,
    nocall_mask=None,
    out_dir: str | Path = "reports",
    threshold: float = 0.5,
    n_boot: int = 1000,
    seed: int = 0,
    n_bins: int = 10,
) -> dict:
    """Full CONTRACT evaluation. Writes metrics.json + reliability PNGs.

    ``probabilities`` / ``labels`` / ``nocall_mask``: genome->value mapping,
    {drug: {genome: value}} mapping, Series, or genome x drug DataFrame
    (labels NaN = unlabeled; nocall True = abstain).
    ``splits``: the splits.json mapping {genome_id: {cluster_id,
    coarse_clade_id, split}} (or a path to it).
    """
    if not isinstance(splits, dict):
        splits = json.loads(Path(splits).read_text())
    probs = _as_frame(probabilities, "drug")
    labs = _as_frame(labels, "drug")
    nc = _as_frame(nocall_mask, "drug") if nocall_mask is not None else None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for drug in probs.columns:
        if drug not in labs.columns:
            continue
        df = _subset_frame(
            probs[drug], labs[drug],
            nc[drug] if nc is not None and drug in nc.columns else None,
            splits,
        )
        mask = df["nocall"].to_numpy() if "nocall" in df else None
        drug_res: dict = {"n_labeled": int(len(df)), "splits": {}, "groups": {}}

        def _eval_block(sub: pd.DataFrame) -> dict:
            m = binary_metrics(sub["y"], sub["p"], threshold)
            if "nocall" in sub:
                m.update(apply_nocall_metrics(sub["y"], sub["p"], sub["nocall"], threshold))
            m["risk_coverage"] = risk_coverage(
                sub["y"], sub["p"],
                sub["nocall"] if "nocall" in sub else None, threshold,
            )
            m["reliability"] = reliability_data(sub["y"], sub["p"], n_bins)
            return m

        for split_name in EVAL_SPLITS:
            sub = df[df["split"] == split_name]
            if len(sub) == 0:
                continue
            block = _eval_block(sub)
            ci = bootstrap_group_ci(sub["y"], sub["p"], sub["cluster_id"],
                                    n_boot=n_boot, seed=seed, threshold=threshold)
            block["balanced_accuracy_ci95_over_clusters"] = ci
            drug_res["splits"][split_name] = block

        for group_name, members in (("seen", SEEN_SPLITS), ("heldout_group", ("heldout_group",))):
            sub = df[df["split"].isin(members)]
            if len(sub) == 0:
                continue
            block = _eval_block(sub)
            ci = bootstrap_group_ci(sub["y"], sub["p"], sub["cluster_id"],
                                    n_boot=n_boot, seed=seed, threshold=threshold)
            block["balanced_accuracy_ci95_over_clusters"] = ci
            drug_res["groups"][group_name] = block

        rel_groups = {
            name: blk["reliability"]
            for name, blk in (
                ("test", drug_res["splits"].get("test")),
                ("heldout_group", drug_res["splits"].get("heldout_group")),
            )
            if blk is not None
        }
        if rel_groups:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(drug))
            png = plot_reliability(rel_groups, out_dir / f"reliability_{safe}.png",
                                   title=f"{drug} — reliability")
            drug_res["reliability_png"] = str(png)
        results[str(drug)] = drug_res

    results = _jsonable(results)
    (out_dir / "metrics.json").write_text(json.dumps(results, indent=1) + "\n")
    return results
