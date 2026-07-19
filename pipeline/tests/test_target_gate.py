"""Synthetic-data tests for the target-locus callability gate.

Fixtures build a tiny world in tmp_path: a donor genome whose TSV confirms
gyrA/parC/parE locus coordinates (three 2 kb random loci inside one contig),
plus query genomes that do/don't carry the loci and do/don't pass QC.
"""

import numpy as np
import pytest

from pipeline import nocall, target_gate as G

TSV_HEADER = "\t".join([
    "Protein id", "Contig id", "Start", "Stop", "Strand", "Element symbol",
    "Element name", "Scope", "Type", "Subtype", "Class", "Subclass", "Method",
    "Target length", "Reference sequence length", "% Coverage of reference",
    "% Identity to reference", "Alignment length",
    "Closest reference accession", "Closest reference name", "HMM accession",
    "HMM description",
])

RNG = np.random.RandomState(7)
LOCI = ("gyrA", "parC", "parE")
LOCUS_LEN = 2000
# locus start positions (1-based) inside the donor contig
LOCUS_STARTS = {"gyrA": 1001, "parC": 4001, "parE": 7001}
DONOR_CONTIG_LEN = 10000


def rand_seq(n, rng=RNG):
    return "".join(rng.choice(list("ACGT"), n))


# locus sequences are fixed once so every test shares the same reference
LOCUS_SEQ = {l: rand_seq(LOCUS_LEN) for l in LOCI}
FILLER = rand_seq(DONOR_CONTIG_LEN)


def donor_contig():
    seq = list(FILLER)
    for l, start in LOCUS_STARTS.items():
        seq[start - 1:start - 1 + LOCUS_LEN] = LOCUS_SEQ[l]
    return "".join(seq)


def write_fna(path, contigs: dict[str, str]):
    with open(path, "w") as fh:
        for name, seq in contigs.items():
            fh.write(f">{name}\n")
            for i in range(0, len(seq), 70):
                fh.write(seq[i:i + 70] + "\n")


def tsv_rows(rows):
    """rows: list of (contig, start, stop, symbol[, tag]) -> TSV text.

    tag is appended to the Element name (e.g. " [WILDTYPE]", " [UNKNOWN]");
    untagged rows are curated resistance mutations.
    """
    out = [TSV_HEADER]
    for row in rows:
        contig, start, stop, symbol = row[:4]
        tag = row[4] if len(row) > 4 else ""
        locus = symbol.split("_")[0]
        out.append("\t".join([
            "NA", contig, str(start), str(stop), "+", symbol,
            f"Synthetic {locus}{tag}", "core", "AMR", "POINT", "QUINOLONE",
            "QUINOLONE", "POINTX", str(LOCUS_LEN), str(LOCUS_LEN),
            "100.00", "99.00", str(LOCUS_LEN), "WP_1", locus, "NA", "NA",
        ]))
    return "\n".join(out) + "\n"


@pytest.fixture
def world(tmp_path):
    """tsv_dir/fna_dir with a donor carrying all three loci."""
    tsv_dir, fna_dir = tmp_path / "tsv", tmp_path / "fna"
    tsv_dir.mkdir()
    fna_dir.mkdir()
    donor = "genome.donor"
    write_fna(fna_dir / f"{donor}.fna", {"ctg1": donor_contig()})
    rows = [("ctg1", LOCUS_STARTS[l], LOCUS_STARTS[l] + LOCUS_LEN - 1,
             f"{l}_X1X") for l in LOCI]
    (tsv_dir / f"{donor}.tsv").write_text(tsv_rows(rows))
    gate = G.Gate(tsv_dir, fna_dir, donor=donor)
    return {"gate": gate, "tsv_dir": tsv_dir, "fna_dir": fna_dir,
            "donor": donor}


def add_genome(world, gid, contigs=None, tsv=None):
    if contigs is not None:
        write_fna(world["fna_dir"] / f"{gid}.fna", contigs)
    if tsv is not None:
        (world["tsv_dir"] / f"{gid}.tsv").write_text(tsv)


INTACT = {"ctgA": donor_contig()}  # all three loci present, one contig


# ---------------------------------------------------------------- locus gate
def test_locus_mutation_hit_is_callable(world):
    gid = "genome.mut"
    add_genome(world, gid, contigs=INTACT,
               tsv=tsv_rows([("ctgA", LOCUS_STARTS["gyrA"],
                              LOCUS_STARTS["gyrA"] + LOCUS_LEN - 1,
                              "gyrA_S83L")]))
    s = world["gate"].gate_status(gid, "ciprofloxacin")
    assert s["status"] == "pass"
    assert "gyrA_S83L" in s["detail"]


def test_locus_missing_makes_not_callable(world):
    gid = "genome.noparE"
    contigs = {"ctgA": rand_seq(DONOR_CONTIG_LEN)}  # no gate locus present
    add_genome(world, gid, contigs=contigs, tsv=tsv_rows([]))
    s = world["gate"].gate_status(gid, "ciprofloxacin")
    assert s["status"] == "not_callable"
    assert s["detail"].startswith(G.NO_CALL_REASON)
    assert "gyrA" in s["detail"]


def test_locus_wt_intact_via_kmers(world):
    gid = "genome.wt"
    add_genome(world, gid, contigs=INTACT, tsv=tsv_rows([]))
    s = world["gate"].gate_status(gid, "ciprofloxacin")
    assert s["status"] == "pass"
    assert "WT-intact" in s["detail"]


def test_locus_unverified_without_fasta(world):
    gid = "genome.nofna"
    add_genome(world, gid, tsv=tsv_rows([]))  # TSV exists, FASTA missing
    s = world["gate"].gate_status(gid, "ciprofloxacin")
    assert s["status"] == "not_callable"
    assert "FASTA missing" in s["detail"]


def test_mutall_wt_row_counts_as_screened(world, tmp_path):
    mut_dir = tmp_path / "mutall"
    mut_dir.mkdir()
    gid = "genome.mutall"
    # FASTA without loci, empty batch TSV, but a --mutation_all TSV whose
    # [WILDTYPE] rows prove all three loci were screened
    add_genome(world, gid, contigs={"ctgA": rand_seq(DONOR_CONTIG_LEN)},
               tsv=tsv_rows([]))
    wt_rows = [("ctgA", 1, LOCUS_LEN, f"{l}_W10W", " [WILDTYPE]") for l in LOCI]
    (mut_dir / f"{gid}.tsv").write_text(tsv_rows(wt_rows))
    gate = G.Gate(world["tsv_dir"], world["fna_dir"], mut_dir,
                  donor=world["donor"])
    s = gate.gate_status(gid, "ciprofloxacin")
    assert s["status"] == "pass"
    assert "screened WT" in s["detail"]


def test_mutall_absent_locus_is_authoritative_not_called(world, tmp_path):
    mut_dir = tmp_path / "mutall"
    mut_dir.mkdir()
    gid = "genome.mutallgap"
    # genome HAS intact loci (k-mer check would pass), and the mutall TSV
    # confirms gyrA/parC — but parE has NO row: the authoritative screen did
    # not call it, so the k-mer fallback must NOT rescue it
    add_genome(world, gid, contigs=INTACT, tsv=tsv_rows([]))
    rows = [("ctgA", 1, LOCUS_LEN, "gyrA_W10W", " [WILDTYPE]"),
            ("ctgA", 1, LOCUS_LEN, "parC_W10W", " [WILDTYPE]")]
    (mut_dir / f"{gid}.tsv").write_text(tsv_rows(rows))
    gate = G.Gate(world["tsv_dir"], world["fna_dir"], mut_dir,
                  donor=world["donor"])
    s = gate.gate_status(gid, "ciprofloxacin")
    assert s["status"] == "not_callable"
    assert "parE" in s["detail"]
    assert "--mutation_all" in s["detail"]


# ------------------------------------------------------------------- QC gate
def test_qc_pass_is_absence_of_evidence(world):
    gid = "genome.qcok"
    add_genome(world, gid, contigs={"ctg1": rand_seq(5_000_000)})
    s = world["gate"].gate_status(gid, "gentamicin")
    assert s["status"] == "absence_of_evidence"
    assert "absence-of-evidence" in s["detail"]


def test_qc_fail_length_is_not_callable(world):
    gid = "genome.tooshort"
    add_genome(world, gid, contigs={"ctg1": rand_seq(2_000_000)})
    s = world["gate"].gate_status(gid, "ampicillin")
    assert s["status"] == "not_callable"
    assert "assembly QC fail" in s["detail"]
    assert "Mb" in s["detail"]


def test_qc_fail_too_many_contigs(world):
    gid = "genome.fragmented"
    contigs = {f"ctg{i}": rand_seq(7500) for i in range(600)}   # 4.5 Mb, 600
    add_genome(world, gid, contigs=contigs)
    s = world["gate"].gate_status(gid, "cefotaxime")
    assert s["status"] == "not_callable"
    assert "contigs" in s["detail"]


def test_qc_missing_fasta_is_not_callable(world):
    s = world["gate"].gate_status("genome.ghost", "trimethoprim/sulfamethoxazole")
    assert s["status"] == "not_callable"
    assert "FASTA missing" in s["detail"]


# -------------------------------------------------------------- flip logic
@pytest.fixture
def det_bands():
    """Same deterministic bands as test_nocall: q_S=0.20, q_R=0.19."""
    p = np.concatenate([np.linspace(0.01, 0.20, 20), np.linspace(0.80, 0.99, 20)])
    y = np.array([0] * 20 + [1] * 20)
    return nocall.fit_conformal_bands(p, y)


def test_override_flips_only_not_callable_s_calls(det_bands):
    p = np.array([0.05, 0.10, 0.15, 0.90, 0.50])
    base = np.array([False, False, False, False, True])  # last already no-call
    statuses = ["pass", "not_callable", "absence_of_evidence",
                "not_callable", "not_callable"]
    new_mask, n = G.apply_gate_override(p, det_bands, base, statuses)
    # 0.05 pass -> stays called; 0.10 not_callable -> FLIPPED;
    # 0.15 absence_of_evidence -> stands; 0.90 R-call -> untouched even when
    # not_callable; 0.50 already no-call -> not counted as a flip
    assert new_mask.tolist() == [False, True, False, False, True]
    assert n == 1


def test_override_zero_flips_preserves_mask(det_bands):
    p = np.array([0.05, 0.95, 0.50])
    base = np.array([False, False, True])
    statuses = ["pass", "pass", "absence_of_evidence"]
    new_mask, n = G.apply_gate_override(p, det_bands, base, statuses)
    assert n == 0
    assert new_mask.tolist() == base.tolist()
