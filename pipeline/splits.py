"""Two-tier split builder for Genome Firewall (CONTRACT.md: splits/splits.json).

Fine tier:  skani ``triangle -E`` edge list -> single-linkage connected components
            at ANI >= 99.5% AND aligned fraction >= 80% -> ``cluster_id``.
            Fine clusters NEVER cross train/calibration/test/heldout_group.
Coarse tier: leave-top-N-clades-out. The N largest fine clusters (by member
            count) become ``heldout_group``; the rest receive
            train/calibration/test with StratifiedGroupKFold semantics by
            cluster (labels stratified per drug where a label is available).
            ``coarse_clade_id`` currently equals ``cluster_id`` — with only an
            ANI graph (no phylogeny) the fine cluster is the coarsest grouping
            we can defend; the file format already carries the column so a
            phylogeny/MLST-based remap can drop in without schema changes.

Also: cross-split leakage audit (max ANI train<->heldout must be < 99.5%)
and a resistant-class cassette-sharing audit over a feature matrix.

skani runs in Docker (staphb/skani, pinned tag); a local binary can be used
via --skani-bin or the SKANI_BIN env var instead (documented in PIPELINE.md).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

SKANI_IMAGE = "staphb/skani:0.3.2"  # tag verified on Docker Hub 2026-07-19
SKANI_PLATFORM = "linux/amd64"      # host is Apple Silicon; image is x86_64
DEFAULT_ANI_THRESHOLD = 99.5
DEFAULT_AF_THRESHOLD = 80.0
DEFAULT_N_HELDOUT = 5
SPLIT_NAMES = ("train", "calibration", "test", "heldout_group")


# --------------------------------------------------------------------------
# skani runner
# --------------------------------------------------------------------------

def run_skani_triangle(
    genomes_dir: str | Path,
    out_tsv: str | Path,
    image: str = SKANI_IMAGE,
    threads: int = 4,
    pattern: str = "*.fna",
    skani_bin: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> Path:
    """Run ``skani triangle -E`` over every ``pattern`` file in ``genomes_dir``.

    Writes the sparse edge list to ``out_tsv`` and returns its path.
    Docker is the default; set ``skani_bin`` (or env ``SKANI_BIN``) to a local
    skani binary to bypass Docker. The output dir doubles as the list-file
    mount, so it must be writable.
    """
    genomes_dir = Path(genomes_dir).resolve()
    fastas = sorted(genomes_dir.glob(pattern))
    if not fastas:
        raise FileNotFoundError(f"no {pattern!r} files in {genomes_dir}")
    out_tsv = Path(out_tsv).resolve()
    out_tsv.parent.mkdir(parents=True, exist_ok=True)

    skani_bin = skani_bin or os.environ.get("SKANI_BIN")
    if skani_bin is None:
        _ensure_docker_image(image)
        list_host = out_tsv.parent / "skani_genomes.list"
        list_host.write_text("".join(f"/genomes/{f.name}\n" for f in fastas))
        cmd = [
            "docker", "run", "--rm", "--platform", SKANI_PLATFORM,
            "-v", f"{genomes_dir}:/genomes:ro",
            "-v", f"{out_tsv.parent}:/out",
            image,
            "skani", "triangle", "-E", "-t", str(threads),
            "--diagonal",
            "-l", f"/out/{list_host.name}",
            "-o", f"/out/{out_tsv.name}",
            *extra_args,
        ]
    else:
        if shutil.which(skani_bin) is None and not Path(skani_bin).exists():
            raise FileNotFoundError(
                f"skani binary not found: {skani_bin}. Install skani "
                f"(e.g. `cargo install skani` or a conda-less prebuilt) and "
                f"point SKANI_BIN at it, or use Docker."
            )
        list_host = out_tsv.parent / "skani_genomes.list"
        list_host.write_text("".join(f"{f}\n" for f in fastas))
        cmd = [
            skani_bin, "triangle", "-E", "-t", str(threads), "--diagonal",
            "-l", str(list_host), "-o", str(out_tsv), *extra_args,
        ]
    subprocess.run(cmd, check=True)
    if not out_tsv.exists():
        raise RuntimeError(f"skani did not produce {out_tsv}; stderr above")
    return out_tsv


def _ensure_docker_image(image: str) -> None:
    """Fail fast with a clear message if the pinned image is missing locally."""
    inspect = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if inspect.returncode == 0:
        return
    pull = subprocess.run(["docker", "pull", "--platform", SKANI_PLATFORM, image])
    if pull.returncode != 0:
        raise RuntimeError(
            f"docker image {image} not available locally and pull failed. "
            f"Check the tag on Docker Hub (staphb/skani) or use --skani-bin."
        )


def parse_skani_edges(edge_path: str | Path) -> pd.DataFrame:
    """Parse a ``skani triangle -E`` / ``skani dist`` edge list.

    Returns columns: ref, query, ani, af_ref, af_query (genome ids are file
    stems, matching data/genomes/{genome_id}.fna).
    """
    df = pd.read_csv(edge_path, sep="\t")
    cols = {c.lower(): c for c in df.columns}

    def _find(*keys: str) -> str:
        for key in keys:
            for low, orig in cols.items():
                if key in low:
                    return orig
        raise KeyError(f"none of {keys} in skani header {list(df.columns)}")

    out = pd.DataFrame({
        "ref": df[_find("ref_file")].map(lambda p: Path(str(p)).stem),
        "query": df[_find("query_file")].map(lambda p: Path(str(p)).stem),
        "ani": pd.to_numeric(df[_find("ani")]),
        "af_ref": pd.to_numeric(df[_find("align_fraction_ref")]),
        "af_query": pd.to_numeric(df[_find("align_fraction_query")]),
    })
    return out


# --------------------------------------------------------------------------
# Fine tier: single-linkage clusters
# --------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)  # deterministic root


def build_clusters(
    edges: pd.DataFrame,
    genome_ids=None,
    ani_threshold: float = DEFAULT_ANI_THRESHOLD,
    af_threshold: float = DEFAULT_AF_THRESHOLD,
) -> dict[str, int]:
    """Single-linkage connected components over edges passing BOTH thresholds.

    ``genome_ids`` should be the full genome set so isolated genomes become
    singleton clusters; if omitted, only genomes appearing in ``edges`` are
    clustered. AF gate uses min(af_ref, af_query) (both directions >= 80%).
    Returns {genome_id: cluster_id} with ids assigned in sorted-genome order
    for determinism.
    """
    if genome_ids is None:
        genome_ids = sorted(set(edges["ref"]) | set(edges["query"]))
    uf = _UnionFind(genome_ids)
    keep = edges[
        (edges["ani"] >= ani_threshold)
        & (edges[["af_ref", "af_query"]].min(axis=1) >= af_threshold)
    ]
    for row in keep.itertuples(index=False):
        if row.ref != row.query:
            uf.union(row.ref, row.query)
    roots = {}
    clusters = {}
    next_id = 0
    for g in sorted(genome_ids):
        r = uf.find(g)
        if r not in roots:
            roots[r] = next_id
            next_id += 1
        clusters[g] = roots[r]
    return clusters


# --------------------------------------------------------------------------
# Coarse tier: leave-top-N-clades-out + stratified group assignment
# --------------------------------------------------------------------------

def _greedy_assign(cluster_sizes: pd.Series, fracs: dict[str, float],
                   seed: int) -> dict[int, str]:
    """Fallback: assign whole clusters to splits by size-deficit greedy."""
    rng = np.random.RandomState(seed)
    order = list(cluster_sizes.index)
    rng.shuffle(order)
    total = cluster_sizes.sum()
    current = {name: 0 for name in fracs}
    assignment = {}
    for cid in sorted(order, key=lambda c: (-cluster_sizes[c], c)):
        deficits = {
            name: (frac * total - current[name]) / frac
            for name, frac in fracs.items()
        }
        # deterministic tie-break via seeded jitter
        best = max(fracs, key=lambda n: (deficits[n], rng.random()))
        assignment[cid] = best
        current[best] += cluster_sizes[cid]
    return assignment


def _stratified_group_assign(
    cluster_sizes: pd.Series,
    strata: pd.Series,           # genome_id -> label (may have NaN)
    clusters: dict[str, int],
    fracs: dict[str, float],     # e.g. {"train": .70, "calibration": .15, "test": .15}
    seed: int,
) -> dict[int, str]:
    """StratifiedGroupKFold-style assignment of clusters to split names.

    Labeled genomes are folded with StratifiedGroupKFold (groups = cluster);
    clusters with no labeled member fall back to greedy size balancing.
    Falls back to greedy entirely when there are too few groups/labels.
    """
    from sklearn.model_selection import StratifiedGroupKFold

    # Sorted smallest-first so names[-1] is the largest split ("train"),
    # which the peel loop below treats as the remainder (takes all leftover
    # folds). A plain list(fracs) puts "test" last, which made the TEST
    # split consume every fold and left train with ~0 genomes.
    names = sorted(fracs, key=lambda n: fracs[n])
    labeled = strata.dropna()
    cl_of = pd.Series(clusters)
    labeled_clusters = cl_of[cl_of.index.isin(labeled.index)]
    n_labeled_clusters = labeled_clusters.nunique()
    min_frac = min(fracs.values())
    # need at least ~1/min_frac groups AND >=2 samples per class to stratify
    n_splits = max(2, round(1.0 / min_frac))
    can_stratify = (
        n_labeled_clusters >= n_splits
        and labeled.nunique() == 2
        and labeled.value_counts().min() >= n_splits
    )
    if not can_stratify:
        return _greedy_assign(cluster_sizes, fracs, seed)

    # Assign every labeled cluster to a fold, stratified by the cluster's
    # majority label (one label per cluster keeps groups intact).
    cl_label = (
        pd.DataFrame({"cid": labeled_clusters, "y": labeled})
        .groupby("cid")["y"].agg(lambda s: int(round(s.mean())))
    )
    cids = cl_label.index.to_numpy()
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                random_state=seed)
    fold_of = {}
    dummy_X = np.zeros((len(cids), 1))
    for fold, (_, test_idx) in enumerate(sgkf.split(dummy_X, cl_label.to_numpy(), groups=cids)):
        for cid in cids[test_idx]:
            fold_of[int(cid)] = fold

    # Map folds -> split names by matching cumulative fractions, largest
    # clusters first into 'train' territory. Fold sizes in genomes:
    fold_sizes = {f: 0 for f in range(n_splits)}
    for cid, f in fold_of.items():
        fold_sizes[f] += cluster_sizes.get(cid, 0)
    total = sum(fold_sizes.values())
    assignment: dict[int, str] = {}
    remaining = dict(fracs)
    remaining_clusters = dict(cluster_sizes)
    # greedily peel splits from smallest fraction to largest
    for name in sorted(names, key=lambda n: fracs[n]):
        target = fracs[name] * total
        chosen, acc = [], 0
        for f in sorted(fold_sizes, key=lambda f: fold_sizes[f]):
            if acc < target or name == names[-1]:
                chosen.append(f)
                acc += fold_sizes.pop(f)
                if acc >= target and name != names[-1]:
                    break
        for cid, f in fold_of.items():
            if f in chosen:
                assignment[cid] = name
        for cid in [c for c, f in fold_of.items() if f in chosen]:
            remaining_clusters.pop(cid, None)
        if name == names[-1]:
            break
    # any leftover labeled cluster (shouldn't happen) -> train
    for cid in remaining_clusters:
        if cid not in assignment:
            assignment[cid] = "train"
    # unlabeled clusters: greedy into existing assignment
    unlabeled = [c for c in cluster_sizes.index if c not in assignment]
    if unlabeled:
        rng = np.random.RandomState(seed + 1)
        current = {n: sum(cluster_sizes[c] for c, s in assignment.items() if s == n)
                   for n in names}
        for cid in sorted(unlabeled, key=lambda c: (-cluster_sizes[c], c)):
            best = max(names, key=lambda n: (fracs[n] * total - current[n], rng.random()))
            assignment[cid] = best
            current[best] += cluster_sizes[cid]
    return assignment


def assign_splits(
    clusters: dict[str, int],
    labels=None,
    n_heldout: int = DEFAULT_N_HELDOUT,
    fracs: dict[str, float] | None = None,
    seed: int = 0,
) -> dict[str, dict]:
    """Build the splits.json mapping per CONTRACT.md.

    - The ``n_heldout`` largest clusters become ``heldout_group``.
    - Remaining clusters get train/calibration/test by cluster.
    - ``labels``: optional pd.Series/dict genome_id -> 0/1 for ONE drug (the
      caller's primary drug) used for stratification where possible.
    Returns {genome_id: {"cluster_id", "coarse_clade_id", "split"}}.
    """
    fracs = fracs or {"train": 0.70, "calibration": 0.15, "test": 0.15}
    assert set(fracs) == {"train", "calibration", "test"}
    if labels is not None and not isinstance(labels, pd.Series):
        labels = pd.Series(labels, dtype="float64")

    cluster_sizes = pd.Series(clusters).value_counts().sort_index()
    heldout = set(
        cluster_sizes.sort_values(ascending=False)
        .head(n_heldout).index.tolist()
    )
    rest = cluster_sizes[~cluster_sizes.index.isin(heldout)]
    inner = _stratified_group_assign(
        rest, labels if labels is not None else pd.Series(dtype="float64"),
        clusters, fracs, seed,
    )
    splits = {}
    for g, cid in clusters.items():
        split = "heldout_group" if cid in heldout else inner[cid]
        splits[g] = {
            "cluster_id": int(cid),
            "coarse_clade_id": int(cid),  # see module docstring
            "split": split,
        }
    return splits


def save_splits(splits: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(splits, indent=1, sort_keys=True) + "\n")
    return path


def load_splits(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


# --------------------------------------------------------------------------
# Audits
# --------------------------------------------------------------------------

def audit_cross_split_leakage(
    splits: dict,
    edges: pd.DataFrame | None,
    ani_threshold: float = DEFAULT_ANI_THRESHOLD,
    af_threshold: float = DEFAULT_AF_THRESHOLD,
) -> dict:
    """Leakage audit: cluster integrity + max cross-split ANI.

    Checks (1) no cluster_id spans more than one split, (2) no edge with
    ANI >= threshold AND AF >= threshold connects different splits, and
    reports max ANI between train and heldout_group (must be < 99.5%).
    """
    split_of = {g: v["split"] for g, v in splits.items()}
    cl_of = {g: v["cluster_id"] for g, v in splits.items()}
    cl_splits: dict[int, set] = {}
    for g, cid in cl_of.items():
        cl_splits.setdefault(cid, set()).add(split_of[g])
    crossing_clusters = sorted(c for c, s in cl_splits.items() if len(s) > 1)

    result = {
        "n_genomes": len(splits),
        "n_clusters": len(cl_splits),
        "crossing_clusters": crossing_clusters,
        "max_ani_train_vs_heldout": None,
        "max_ani_across_splits": None,
        "violating_edges": [],
        "pass": len(crossing_clusters) == 0,
    }
    if edges is None or len(edges) == 0:
        return result

    e = edges[
        edges["ref"].isin(split_of) & edges["query"].isin(split_of)
        & (edges["ref"] != edges["query"])
    ].copy()
    if len(e) == 0:
        return result
    e["split_ref"] = e["ref"].map(split_of)
    e["split_query"] = e["query"].map(split_of)
    cross = e[e["split_ref"] != e["split_query"]]
    if len(cross):
        result["max_ani_across_splits"] = float(cross["ani"].max())
    th = cross[
        (cross["ani"] >= ani_threshold)
        & (cross[["af_ref", "af_query"]].min(axis=1) >= af_threshold)
    ]
    result["violating_edges"] = [
        {"ref": r.ref, "query": r.query, "ani": float(r.ani),
         "split_ref": r.split_ref, "split_query": r.split_query}
        for r in th.itertuples(index=False)
    ]
    train_heldout = cross[
        cross[["split_ref", "split_query"]].apply(
            lambda r: {r["split_ref"], r["split_query"]} == {"train", "heldout_group"},
            axis=1,
        )
    ]
    if len(train_heldout):
        result["max_ani_train_vs_heldout"] = float(train_heldout["ani"].max())
        if result["max_ani_train_vs_heldout"] >= ani_threshold:
            result["pass"] = False
    if result["violating_edges"]:
        result["pass"] = False
    return result


def audit_cassette_sharing(
    feature_matrix: pd.DataFrame,
    labels,
    splits: dict,
    splits_to_compare: tuple[str, str] = ("train", "heldout_group"),
) -> dict:
    """Resistant-class feature overlap between splits (plasmid-cassette audit).

    Plasmid-borne AMR cassettes cross ANI boundaries, so ANI-clean splits can
    still leak: if the exact resistance elements of resistant train genomes
    also appear in resistant heldout genomes, heldout is not mechanism-novel.
    ``feature_matrix``: genome_id x binary AMR element DataFrame (CONTRACT
    features/feature_matrix.csv). ``labels``: genome_id -> 0/1 for one drug.
    Returns present-feature sets, intersection/union sizes, and Jaccard.
    """
    labels = pd.Series(labels)
    split_of = pd.Series({g: v["split"] for g, v in splits.items()})
    fm = feature_matrix.copy()
    fm.index = fm.index.astype(str)

    def r_features(split_name: str) -> set[str]:
        genomes = split_of[split_of == split_name].index
        r_genomes = labels[(labels == 1) & labels.index.isin(genomes)].index
        sub = fm.loc[fm.index.isin(r_genomes)]
        if len(sub) == 0:
            return set()
        return set(sub.columns[(sub.sum(axis=0) > 0)])

    a_name, b_name = splits_to_compare
    a, b = r_features(a_name), r_features(b_name)
    inter = a & b
    union = a | b
    return {
        "drug_label_resistant_features": {
            a_name: sorted(a),
            b_name: sorted(b),
        },
        "n_shared": len(inter),
        "n_union": len(union),
        "jaccard": (len(inter) / len(union)) if union else None,
        "shared_features": sorted(inter),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edges", help="existing skani -E edge list (skip skani run)")
    ap.add_argument("--genomes-dir", help="dir of .fna; runs skani if --edges absent")
    ap.add_argument("--labels", help="CSV genome_id,label (0/1) for stratification")
    ap.add_argument("--out", default="splits/splits.json")
    ap.add_argument("--edges-out", default=None,
                    help="where to write the skani edge list (default: alongside --out)")
    ap.add_argument("--n-heldout", type=int, default=DEFAULT_N_HELDOUT)
    ap.add_argument("--ani", type=float, default=DEFAULT_ANI_THRESHOLD)
    ap.add_argument("--af", type=float, default=DEFAULT_AF_THRESHOLD)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skani-bin", default=None)
    ap.add_argument("--config", help="optional YAML with any of the above keys")
    args = ap.parse_args(argv)

    if args.config:
        import yaml
        cfg = yaml.safe_load(Path(args.config).read_text()) or {}
        for k, v in cfg.items():
            if hasattr(args, k.replace("-", "_")):
                setattr(args, k.replace("-", "_"), v)

    if args.edges:
        edge_path = Path(args.edges)
    else:
        if not args.genomes_dir:
            ap.error("need --edges or --genomes-dir")
        edge_path = Path(args.edges_out or Path(args.out).parent / "skani_edges.tsv")
        run_skani_triangle(args.genomes_dir, edge_path,
                           threads=args.threads, skani_bin=args.skani_bin)

    edges = parse_skani_edges(edge_path)
    if args.genomes_dir:
        genome_ids = sorted(p.stem for p in Path(args.genomes_dir).glob("*.fna"))
    else:
        genome_ids = sorted(set(edges["ref"]) | set(edges["query"]))
    clusters = build_clusters(edges, genome_ids, args.ani, args.af)
    labels = None
    if args.labels:
        # genome_id MUST stay string: ids like "562.100000" would otherwise be
        # parsed as float64 and collapse (562.100000 -> 562.1), corrupting the
        # genome_id->label join and creating duplicate index labels.
        ldf = pd.read_csv(args.labels, dtype={"genome_id": str})
        labels = pd.Series(ldf["label"].values, index=ldf["genome_id"].astype(str))
    splits = assign_splits(clusters, labels, args.n_heldout, seed=args.seed)
    save_splits(splits, args.out)
    audit = audit_cross_split_leakage(splits, edges, args.ani, args.af)
    print(json.dumps({"out": str(args.out), "audit": audit}, indent=1))
    if not audit["pass"]:
        raise SystemExit("LEAKAGE AUDIT FAILED — see above")


if __name__ == "__main__":
    main()
