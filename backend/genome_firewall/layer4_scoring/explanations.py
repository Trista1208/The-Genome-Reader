from __future__ import annotations

TARGET_GATE_MESSAGES = {
    "complete_ecoli_assembly": "Assembly passes quality gate; essential E. coli drug targets assumed present.",
    "assembly_too_short": (
        "Assembly is shorter than 4 Mb. Essential drug targets may be missing — "
        "prediction withheld (no-call)."
    ),
    "overfragmented_assembly": (
        "Assembly has more than 800 contigs. Target presence cannot be trusted — "
        "prediction withheld (no-call)."
    ),
    "fasta_not_provided": (
        "FASTA file was not provided; target gate was skipped. "
        "Supply FASTA for a defensible target check."
    ),
    "missing_fasta": "FASTA file missing for this genome; target gate failed.",
}

NO_CALL_MESSAGES = {
    "missing_drug_target": "Drug target gate failed — see target_gate_reason.",
    "uncertain_probability_band": (
        "Calibrated probability falls in the uncertain band; returning no-call instead of "
        "forcing fail/work."
    ),
    "model_not_trained": "No trained model for this antibiotic in the current cohort.",
    "insufficient_training_data": "Model was not trained due to insufficient labeled data.",
}


def format_known_markers(hits: list[dict[str, str]]) -> list[str]:
    markers: list[str] = []
    for h in hits:
        symbol = (h.get("element_symbol") or "").strip()
        name = (h.get("element_name") or "").strip()
        cls = (h.get("class") or "").strip()
        if not symbol and not name:
            continue
        label = symbol or name
        if name and symbol and name.lower() != symbol.lower():
            label = f"{symbol} ({name})"
        if cls:
            label = f"{label} [{cls}]"
        markers.append(label)
    return markers


def resistance_markers(hits: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for h in hits:
        typ = (h.get("type") or "").upper()
        cls = (h.get("class") or "").strip()
        if typ in {"AMR", "POINT", "STRESS"} or cls:
            out.extend(format_known_markers([h]))
    return out


def explain_target_gate(reason_code: str) -> str:
    return TARGET_GATE_MESSAGES.get(reason_code, f"Target gate code: {reason_code}")


def explain_no_call(reason_code: str | None, *, prob_fail: float, band: tuple[float, float]) -> list[str]:
    if not reason_code:
        return []
    reasons: list[str] = []
    if reason_code == "uncertain_probability_band":
        lo, hi = band
        reasons.append(
            NO_CALL_MESSAGES["uncertain_probability_band"]
            + f" P(fail)={prob_fail:.3f}, band=[{lo:.2f}, {hi:.2f}]."
        )
    elif reason_code == "missing_drug_target":
        reasons.append(NO_CALL_MESSAGES["missing_drug_target"])
    elif reason_code in NO_CALL_MESSAGES:
        reasons.append(NO_CALL_MESSAGES[reason_code])
    else:
        reasons.append(f"No-call reason: {reason_code}")
    return reasons


def explain_prediction(
    prediction: str,
    *,
    prob_fail: float,
    prob_work: float,
    evidence_category: str,
    known_markers: list[str],
    supporting_features: list[str],
    target_ok: bool,
    target_reason: str,
    no_call_reason: str | None,
    band: tuple[float, float],
) -> str:
    if prediction == "no_call":
        parts = explain_no_call(no_call_reason, prob_fail=prob_fail, band=band)
        if not target_ok:
            parts.insert(0, explain_target_gate(target_reason))
        return " ".join(parts) if parts else "Insufficient evidence for a fail/work call."

    if prediction == "likely_to_fail":
        if evidence_category == "known_resistance_marker" and known_markers:
            genes = ", ".join(known_markers[:3])
            return (
                f"Likely to fail: known resistance signal(s) detected ({genes}). "
                f"Calibrated P(fail)={prob_fail:.1%}."
            )
        if supporting_features:
            feats = ", ".join(supporting_features[:3])
            return (
                f"Likely to fail: model associates AMR features ({feats}) with resistance. "
                f"Calibrated P(fail)={prob_fail:.1%} (statistical association)."
            )
        return f"Likely to fail: calibrated P(fail)={prob_fail:.1%}."

    if known_markers:
        return (
            f"Likely to work: no resistance prediction above threshold; AMR hits present but "
            f"model P(fail)={prob_fail:.1%}. Confirm with lab testing."
        )
    return (
        f"Likely to work: no known resistance markers driving failure; "
        f"calibrated P(work)={prob_work:.1%}."
    )


def metric_quality_issues(
    *,
    n_test: int,
    test_resistant: int,
    test_susceptible: int,
    n_train: int,
    train_resistant: int,
    recall_resistant: float | None,
) -> list[str]:
    issues: list[str] = []
    if n_test < 10:
        issues.append(f"Test set is very small (n={n_test}); metrics are unstable.")
    if test_resistant == 0:
        issues.append(
            "Test split has zero lab-resistant genomes — resistant recall and AUROC "
            "cannot be measured (reported accuracy may look misleadingly high)."
        )
    if test_susceptible == 0:
        issues.append("Test split has zero lab-susceptible genomes — susceptible recall cannot be measured.")
    if train_resistant < 5:
        issues.append(
            f"Only {train_resistant} resistant training examples — model may not generalize to resistance."
        )
    if recall_resistant == 0.0 and test_resistant > 0:
        issues.append("Model recall on resistant test cases is 0% — failing to detect resistance.")
    return issues


def training_skip_reason(
    drug: str,
    *,
    n_labeled: int,
    n_resistant: int,
    n_susceptible: int,
    n_with_features: int,
) -> tuple[str, str] | None:
    if n_with_features == 0:
        return (
            "no_amrfinder_features",
            f"No genomes with AMRFinder output are labeled for {drug}. Run feature pipeline first.",
        )
    if n_resistant == 0:
        return (
            "single_class_all_susceptible",
            f"All {n_susceptible} annotated genomes are lab-susceptible — cannot train a "
            f"resistant-vs-susceptible classifier for {drug}.",
        )
    if n_susceptible == 0:
        return (
            "single_class_all_resistant",
            f"All {n_resistant} annotated genomes are lab-resistant — cannot train for {drug}.",
        )
    if n_labeled < 15:
        return (
            "insufficient_labeled_genomes",
            f"Only {n_labeled} genomes with features and labels for {drug} (need ≥15).",
        )
    if n_resistant < 3:
        return (
            "insufficient_resistant_examples",
            f"Only {n_resistant} lab-resistant genomes for {drug} (need ≥3 for stable training).",
        )
    return None
