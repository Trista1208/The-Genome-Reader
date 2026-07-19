from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class GateResult:
    pass_gate: bool
    status: str
    reason: str


class TargetGate:
    def __init__(self, config: dict):
        self.config = config

    @classmethod
    def from_yaml(cls, path: str | Path):
        with Path(path).open(encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle) or {})

    def evaluate(self, antibiotic: str, species: str, present_features: set[str]) -> GateResult:
        rule = self.config.get("antibiotics", {}).get(antibiotic)
        if not rule:
            return GateResult(False, "unsupported", f"No target-gate rule configured for {antibiotic}")
        if species not in rule.get("supported_species", []):
            return GateResult(False, "unsupported", f"{species} is not supported for {antibiotic}")
        if rule.get("core_target_present_in_supported_species", False):
            return GateResult(True, "target_present", "Molecular target is a documented core target in supported E. coli")
        target_features = set(rule.get("target_presence_features", []))
        if target_features and present_features.intersection(target_features):
            return GateResult(True, "target_present", "Configured molecular-target feature detected")
        return GateResult(False, "not_applicable", "Required molecular-target evidence was not detected")
