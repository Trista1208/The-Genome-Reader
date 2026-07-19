from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

from src.predictor.calibration import ProbabilityCalibrator


@dataclass
class DrugModel:
    antibiotic: str
    classifier: LogisticRegression
    calibrator: ProbabilityCalibrator
    novelty_model: NearestNeighbors
    novelty_threshold: float
    no_call_low: float
    no_call_high: float
    feature_names: list[str]

    def predict(self, matrix: sparse.csr_matrix) -> dict[str, np.ndarray]:
        matrix = matrix.tocsr()
        raw_scores = self.classifier.decision_function(matrix)
        resistant_probability = self.calibrator.predict(raw_scores)
        novelty_distance = self.novelty_model.kneighbors(matrix, n_neighbors=1, return_distance=True)[0][:, 0]
        ood = novelty_distance > self.novelty_threshold
        ambiguous = (resistant_probability >= self.no_call_low) & (
            resistant_probability <= self.no_call_high
        )
        no_call = ood | ambiguous
        resistant = resistant_probability >= 0.5
        verdict = np.where(no_call, "no-call", np.where(resistant, "likely to fail", "likely to work"))
        confidence = np.where(no_call, np.nan, np.maximum(resistant_probability, 1 - resistant_probability))
        return {
            "raw_score": raw_scores,
            "resistant_probability": resistant_probability,
            "novelty_distance": novelty_distance,
            "ood": ood,
            "ambiguous": ambiguous,
            "no_call": no_call,
            "verdict": verdict,
            "confidence": confidence,
        }

    def supporting_features(self, row: sparse.csr_matrix, limit: int = 8) -> list[dict]:
        active = row.indices
        coefficients = self.classifier.coef_[0, active]
        ranked = sorted(zip(active, coefficients), key=lambda item: abs(item[1]), reverse=True)
        return [
            {"feature": self.feature_names[index], "coefficient": float(coefficient)}
            for index, coefficient in ranked[:limit]
        ]
