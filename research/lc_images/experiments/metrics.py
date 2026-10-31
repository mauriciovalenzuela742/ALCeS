"""Metricas del protocolo comun: exactitud balanceada, F1 macro y confusion, global y por bin."""
from __future__ import annotations

import numpy as np
import pandas as pd


def balanced_accuracy(y: np.ndarray, pred: np.ndarray) -> float:
    classes = np.unique(y)
    return float(np.mean([np.mean(pred[y == c] == c) for c in classes]))


def macro_f1(y: np.ndarray, pred: np.ndarray) -> float:
    f1 = []
    for c in np.unique(y):
        tp = np.sum((pred == c) & (y == c))
        p = tp / max(np.sum(pred == c), 1)
        r = tp / max(np.sum(y == c), 1)
        f1.append(2 * p * r / (p + r) if p + r > 0 else 0.0)
    return float(np.mean(f1))


def confusion(y: np.ndarray, pred: np.ndarray) -> pd.DataFrame:
    """Matriz normalizada por fila (verdadera); columnas = predicha."""
    cm = pd.crosstab(pd.Series(y, name="true"), pd.Series(pred, name="pred"))
    return cm.div(cm.sum(axis=1), axis=0)


def by_bin(y: np.ndarray, pred: np.ndarray, bins: np.ndarray, order: list[str]) -> list[dict]:
    """Metricas por bin (p. ej. noches con deteccion). Un bin con una sola clase solo da recall."""
    out = []
    for b in order:
        m = bins == b
        if not m.any():
            continue
        out.append({"bin": b, "n": int(m.sum()), "n_classes": int(len(np.unique(y[m]))),
                    "balanced_accuracy": balanced_accuracy(y[m], pred[m]),
                    "macro_f1": macro_f1(y[m], pred[m])})
    return out
