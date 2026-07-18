from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PredictionLabel = Literal["likely_to_fail", "likely_to_work", "no_call"]
EvidenceCategory = Literal[
    "known_resistance_marker",
    "statistical_association",
    "no_known_resistance_signal",
    "insufficient_or_conflicting_evidence",
]


@dataclass
class DrugScore:
    antibiotic: str
    prediction: PredictionLabel
    probability_fail: float
    probability_work: float
    confidence_score: float
    evidence_category: EvidenceCategory
    decision_reason: str
    passes_actionable_call: bool
    failure_reasons: list[str] = field(default_factory=list)
    supporting_features: list[str] = field(default_factory=list)
    known_resistance_markers: list[str] = field(default_factory=list)
    target_gate_passed: bool = True
    target_gate_reason: str = "complete_ecoli_assembly"
    target_gate_explanation: str = ""
    no_call_reason: str | None = None
    model_algorithm: str = "random_forest"
    calibration_method: str = "isotonic"
    model_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenomeReport:
    genome_id: str
    species: str
    drugs: list[DrugScore]
    disclaimer: str = (
        "Research prototype. Confirm all predictions with standard laboratory testing."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "species": self.species,
            "disclaimer": self.disclaimer,
            "drugs": [d.to_dict() for d in self.drugs],
        }
