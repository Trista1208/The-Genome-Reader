import numpy as np
import pandas as pd
from scipy import sparse

from src.predictor.train import train_drug


def test_per_drug_training_smoke():
    rng = np.random.default_rng(7)
    rows, matrices = [], []
    row_index = 0
    for split, count in {"train": 60, "calibration": 30, "test": 30}.items():
        for i in range(count):
            y = i % 2
            signal = y if rng.random() > 0.1 else 1 - y
            matrices.append([signal, int(rng.random() > 0.7), int(rng.random() > 0.8)])
            rows.append({
                "feature_row": row_index,
                "target_resistant": y,
                "split": split,
                "genetic_group": f"{split}_g{i // 3}",
            })
            row_index += 1
    model, metrics = train_drug(
        "ampicillin", pd.DataFrame(rows), sparse.csr_matrix(np.asarray(matrices)),
        ["gene::signal", "gene::a", "gene::b"],
        c_value=1.0, calibration_method="platt", minimum_coverage=0.5, seed=7,
    )
    assert len(model.predict(sparse.csr_matrix(np.asarray(matrices[:2])))["verdict"]) == 2
    assert metrics["test"]["n"] == 30
