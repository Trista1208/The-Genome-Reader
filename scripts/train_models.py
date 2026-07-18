#!/usr/bin/env python3
"""Train calibrated Random Forest models (Module 02 backend)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from genome_firewall.config import ModelConfig  # noqa: E402
from genome_firewall.services.training_service import TrainingService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--max-depth", type=int, default=24)
    parser.add_argument("--no-call-low", type=float, default=0.40)
    parser.add_argument("--no-call-high", type=float, default=0.60)
    args = parser.parse_args()

    cfg = ModelConfig(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        no_call_low=args.no_call_low,
        no_call_high=args.no_call_high,
    )
    TrainingService(model_config=cfg).train_all()


if __name__ == "__main__":
    main()
