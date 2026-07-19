from __future__ import annotations

from src.common import SAFETY_NOTICE


def evidence_tier(supporting_features: list[dict]) -> tuple[str, str]:
    positive = [item for item in supporting_features if item["coefficient"] > 0]
    known = [
        item for item in positive
        if item["feature"].startswith("gene::") or item["feature"].startswith("mutation::")
    ]
    if known:
        return "A", "Known AMRFinderPlus resistance gene or mutation detected"
    if positive:
        return "B", "Statistical association only; no curated causal mechanism established"
    return "C", "No detected feature contributed positive resistance evidence"


def build_report(
    genome_id: str,
    species: str,
    antibiotic: str,
    gate,
    prediction: dict | None,
    supporting_features: list[dict],
) -> dict:
    if not gate.pass_gate:
        return {
            "genome_id": genome_id,
            "species": species,
            "antibiotic": antibiotic,
            "verdict": gate.status,
            "confidence": None,
            "resistant_probability": None,
            "evidence_tier": None,
            "evidence_summary": gate.reason,
            "supporting_features": [],
            "safety_notice": SAFETY_NOTICE,
        }
    tier, summary = evidence_tier(supporting_features)
    no_call_reason = None
    if bool(prediction["ood"][0]):
        no_call_reason = "Input feature profile is outside the training distribution"
    elif bool(prediction["ambiguous"][0]):
        no_call_reason = "Calibrated probability is inside the drug-specific ambiguity band"
    return {
        "genome_id": genome_id,
        "species": species,
        "antibiotic": antibiotic,
        "verdict": str(prediction["verdict"][0]),
        "confidence": None if bool(prediction["no_call"][0]) else float(prediction["confidence"][0]),
        "resistant_probability": float(prediction["resistant_probability"][0]),
        "evidence_tier": tier,
        "evidence_summary": summary,
        "no_call_reason": no_call_reason,
        "supporting_features": supporting_features,
        "safety_notice": SAFETY_NOTICE,
    }
