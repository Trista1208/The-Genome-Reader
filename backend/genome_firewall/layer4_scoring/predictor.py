from __future__ import annotations

from genome_firewall.layer3_model.random_forest import CalibratedRandomForest
from genome_firewall.layer4_scoring.explanations import (
    explain_no_call,
    explain_prediction,
    explain_target_gate,
    resistance_markers,
)
from genome_firewall.schemas.prediction import DrugScore, EvidenceCategory, PredictionLabel


def decide_prediction(
    prob_fail: float,
    *,
    no_call_low: float,
    no_call_high: float,
    target_ok: bool,
) -> tuple[PredictionLabel, float, float, str | None]:
    prob_work = 1.0 - prob_fail
    if not target_ok:
        return "no_call", prob_fail, prob_work, "missing_drug_target"
    if no_call_low <= prob_fail <= no_call_high:
        return "no_call", prob_fail, prob_work, "uncertain_probability_band"
    if prob_fail >= 0.5:
        return "likely_to_fail", prob_fail, prob_work, None
    return "likely_to_work", prob_fail, prob_work, None


def confidence_score(prediction: PredictionLabel, prob_fail: float, prob_work: float) -> float:
    if prediction == "likely_to_fail":
        return prob_fail
    if prediction == "likely_to_work":
        return prob_work
    return max(prob_fail, prob_work)


def evidence_category(
    prediction: PredictionLabel,
    prob_fail: float,
    amr_hits: list[dict[str, str]],
    supporting_features: list[str],
) -> EvidenceCategory:
    if prediction == "no_call":
        return "insufficient_or_conflicting_evidence"

    known = resistance_markers(amr_hits)
    if prediction == "likely_to_fail" and known:
        return "known_resistance_marker"
    if prediction == "likely_to_work" and prob_fail < 0.35 and not known:
        return "no_known_resistance_signal"
    if supporting_features:
        return "statistical_association"
    if prediction == "likely_to_work":
        return "no_known_resistance_signal"
    return "statistical_association"


def score_drug(
    antibiotic: str,
    model: CalibratedRandomForest,
    x,
    *,
    target_ok: bool,
    target_reason: str,
    amr_hits: list[dict[str, str]],
    supporting_features: list[str] | None = None,
) -> DrugScore:
    prob_fail = float(model.calibrated_probability_fail(x)[0])
    prob_work = 1.0 - prob_fail
    band = (model.config.no_call_low, model.config.no_call_high)
    prediction, pf, pw, no_call_reason = decide_prediction(
        prob_fail,
        no_call_low=model.config.no_call_low,
        no_call_high=model.config.no_call_high,
        target_ok=target_ok,
    )
    support = supporting_features or []
    known = resistance_markers(amr_hits)
    evidence = evidence_category(prediction, pf, amr_hits, support)
    failure_reasons: list[str] = []
    if not target_ok:
        failure_reasons.append(explain_target_gate(target_reason))
    failure_reasons.extend(explain_no_call(no_call_reason, prob_fail=pf, band=band))

    decision_reason = explain_prediction(
        prediction,
        prob_fail=pf,
        prob_work=pw,
        evidence_category=evidence,
        known_markers=known,
        supporting_features=support,
        target_ok=target_ok,
        target_reason=target_reason,
        no_call_reason=no_call_reason,
        band=band,
    )

    return DrugScore(
        antibiotic=antibiotic,
        prediction=prediction,
        probability_fail=round(pf, 4),
        probability_work=round(pw, 4),
        confidence_score=round(confidence_score(prediction, pf, pw), 4),
        evidence_category=evidence,
        decision_reason=decision_reason,
        passes_actionable_call=prediction in {"likely_to_fail", "likely_to_work"},
        failure_reasons=[r for r in failure_reasons if r],
        supporting_features=support,
        known_resistance_markers=known,
        target_gate_passed=target_ok,
        target_gate_reason=target_reason,
        target_gate_explanation=explain_target_gate(target_reason),
        no_call_reason=no_call_reason,
        model_algorithm="random_forest",
        calibration_method=model.calibration_method,
        model_available=True,
    )


def unscored_drug(antibiotic: str, *, skip_code: str, skip_detail: str) -> DrugScore:
    return DrugScore(
        antibiotic=antibiotic,
        prediction="no_call",
        probability_fail=0.0,
        probability_work=0.0,
        confidence_score=0.0,
        evidence_category="insufficient_or_conflicting_evidence",
        decision_reason=skip_detail,
        passes_actionable_call=False,
        failure_reasons=[skip_detail],
        no_call_reason=skip_code,
        model_available=False,
    )
