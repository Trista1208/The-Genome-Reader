from __future__ import annotations

import numpy as np
from scipy import sparse


def oversample_minority(
    X: sparse.csr_matrix,
    y: np.ndarray,
    *,
    random_state: int = 42,
) -> tuple[sparse.csr_matrix, np.ndarray]:
    """Upsample resistant (y=1) rows in training only to reduce majority-class bias."""
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(pos) == 0 or len(neg) == 0 or len(pos) >= len(neg):
        return X, y

    rng = np.random.default_rng(random_state)
    extra = rng.choice(pos, size=len(neg) - len(pos), replace=True)
    idx = np.concatenate([np.arange(len(y)), extra])
    return X[idx], y[idx]
