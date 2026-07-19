from src.predictor.target_gate import TargetGate


def test_core_target_rule_passes_supported_species():
    gate = TargetGate({"antibiotics": {"drug": {
        "supported_species": ["Escherichia coli"],
        "core_target_present_in_supported_species": True,
    }}})
    assert gate.evaluate("drug", "Escherichia coli", set()).pass_gate
    assert not gate.evaluate("drug", "Klebsiella pneumoniae", set()).pass_gate
