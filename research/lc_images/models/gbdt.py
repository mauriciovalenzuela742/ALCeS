"""GBDT opcional (sklearn HistGradientBoosting). sklearn no esta en el venv del simulador:
se usa solo desde el venv aparte de research/lc_images (ver README, Entorno)."""
from __future__ import annotations

import numpy as np


def available() -> bool:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return False
    return True


class GBDT:
    def __init__(self, seed: int = 0):
        from sklearn.ensemble import HistGradientBoostingClassifier
        # class_weight balanceado: misma idea que el voto ponderado del kNN.
        self.model = HistGradientBoostingClassifier(class_weight="balanced", random_state=seed)

    def fit(self, x: np.ndarray, y: np.ndarray) -> "GBDT":
        self.model.fit(x, y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.model.predict(x)
