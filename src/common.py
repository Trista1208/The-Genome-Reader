from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_SPECIES = "Escherichia coli"
SUPPORTED_ANTIBIOTICS = ("ampicillin", "ciprofloxacin", "cefotaxime", "gentamicin")
SAFETY_NOTICE = (
    "Research prototype - confirm every result with standard laboratory testing "
    "before making any treatment decision."
)


def write_json(path: str | Path, payload: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
