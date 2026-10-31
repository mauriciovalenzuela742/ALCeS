"""kNN con voto ponderado por el inverso del tamano de clase (numpy puro).

Es el mismo clasificador que knn_loo_balanced_accuracy del diagnostico KN, pero con train y test
separados. Para E1 conviene: un kNN memoriza vecinos, asi que es el modelo mas sensible a que
el mismo template este en train y en test.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def prepare(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Estandariza con estadisticas SOLO de train (si no, el test filtra al escalado).

    NaN -> mediana de train + columna indicadora de faltante, como _prepare_matrix del
    diagnostico KN (la falta de un rasgo tambien es informacion).
    """
    xtr = train[cols].to_numpy(dtype=float)
    xte = test[cols].to_numpy(dtype=float)
    mtr, mte = ~np.isfinite(xtr), ~np.isfinite(xte)
    med = np.nanmedian(np.where(mtr, np.nan, xtr), axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    xtr, xte = np.where(mtr, med, xtr), np.where(mte, med, xte)
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    xtr, xte = (xtr - mu) / sd, (xte - mu) / sd
    keep = mtr.any(axis=0) & ~mtr.all(axis=0)
    if keep.any():
        xtr = np.hstack([xtr, mtr[:, keep].astype(float)])
        xte = np.hstack([xte, mte[:, keep].astype(float)])
    return xtr, xte


class KNN:
    def __init__(self, k: int = 5, chunk: int = 2000):
        self.k, self.chunk = k, chunk

    def fit(self, x: np.ndarray, y: np.ndarray) -> "KNN":
        self.x = x
        self.classes, self.y_idx = np.unique(y, return_inverse=True)
        self.w = 1.0 / np.bincount(self.y_idx)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        k = min(self.k, len(self.x))
        pred = np.empty(len(x), dtype=int)
        for a in range(0, len(x), self.chunk):
            d2 = ((x[a:a + self.chunk, None, :] - self.x[None, :, :]) ** 2).sum(-1)
            nn = np.argpartition(d2, k - 1, axis=1)[:, :k]
            for i, row in enumerate(nn):
                votes = np.bincount(self.y_idx[row], weights=self.w[self.y_idx[row]],
                                    minlength=len(self.classes))
                pred[a + i] = int(np.argmax(votes))
        return self.classes[pred]
