"""Particiones train/test estratificadas por clase: aleatoria por objeto o agrupada por template."""
from __future__ import annotations

import numpy as np


def random_split(y: np.ndarray, test_frac: float, seed: int) -> np.ndarray:
    """Mascara de test: test_frac de los objetos de cada clase, al azar."""
    rng = np.random.default_rng(seed)
    test = np.zeros(len(y), dtype=bool)
    for c in np.unique(y):
        idx = np.flatnonzero(y == c)
        n_test = int(round(test_frac * len(idx)))
        if 0 < n_test < len(idx):
            test[rng.choice(idx, n_test, replace=False)] = True
    return test


def grouped_split(y: np.ndarray, groups: np.ndarray, test_frac: float, seed: int) -> np.ndarray:
    """Mascara de test con grupos enteros: ningun grupo queda a ambos lados.

    Por clase, los grupos se barajan y se pasan a test hasta llegar a test_frac de los objetos
    de esa clase (al menos un grupo en test y uno en train). Una clase con un solo grupo queda
    entera en train: no se puede evaluar sin fuga, y `untestable_classes` la reporta.
    """
    rng = np.random.default_rng(seed)
    test = np.zeros(len(y), dtype=bool)
    for c in np.unique(y):
        idx = np.flatnonzero(y == c)
        g, counts = np.unique(groups[idx], return_counts=True)
        if len(g) < 2:
            continue
        order = rng.permutation(len(g))
        target, n = test_frac * len(idx), 0
        chosen = []
        for k in order[:-1]:  # deja al menos un grupo en train
            if n >= target:
                break
            chosen.append(g[k])
            n += counts[k]
        test[idx[np.isin(groups[idx], chosen)]] = True
    return test


def untestable_classes(y: np.ndarray, test: np.ndarray) -> list[str]:
    return sorted(str(c) for c in np.unique(y) if not test[y == c].any() or test[y == c].all())


def shared_groups(groups: np.ndarray, test: np.ndarray) -> float:
    """Fraccion de objetos de test cuyo grupo tambien aparece en train (fuga potencial)."""
    if not test.any():
        return float("nan")
    return float(np.isin(groups[test], groups[~test]).mean())
