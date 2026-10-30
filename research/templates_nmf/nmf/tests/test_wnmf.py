"""Tests del NMF con pesos sobre datos sinteticos.

    python -m pytest research/templates_nmf/nmf/tests -q
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import wnmf  # noqa: E402


def synthetic(n=40, m=60, k=3, noise=0.0, missing=0.0, seed=1, width=0.12):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, m)
    # Componentes suaves y positivas, como espectros o curvas de luz.
    H = np.vstack([np.exp(-0.5 * ((x - c) / width) ** 2) for c in np.linspace(0.2, 0.8, k)])
    W = rng.uniform(0.2, 2.0, (n, k))
    V0 = W @ H
    sigma = np.full_like(V0, noise if noise else 1.0)
    V = V0 + (rng.normal(0, noise, V0.shape) if noise else 0.0)
    wts = 1.0 / sigma ** 2
    if missing:
        wts[rng.random(V0.shape) < missing] = 0.0
    return V, wts, V0, W, H


def test_recupera_datos_exactos():
    V, wts, V0, _, _ = synthetic()
    W, H, hist = wnmf.fit(V, wts, 3, n_iter=500, tol=1e-12)
    assert np.allclose(W @ H, V0, atol=1e-3 * V0.max())
    assert (W >= 0).all() and (H >= 0).all()


def test_chi2_no_sube():
    V, wts, *_ = synthetic(noise=0.05, missing=0.3)
    _, _, hist = wnmf.fit(V, wts, 3, n_iter=60, tol=0)
    assert np.all(np.diff(hist) <= 1e-9 * hist[:-1])


def test_datos_faltantes_se_reconstruyen():
    V, wts, V0, _, _ = synthetic(missing=0.4)
    W, H, _ = wnmf.fit(V, wts, 3, n_iter=500, tol=1e-12)
    hidden = wts == 0
    assert np.abs((W @ H)[hidden] - V0[hidden]).max() < 0.02 * V0.max()


def test_admite_valores_negativos():
    V, wts, V0, _, _ = synthetic(noise=0.05, width=0.05)
    assert (V < 0).sum() > 50  # el ruido deja flujo negativo cerca de cero
    W, H, _ = wnmf.fit(V, wts, 3, n_iter=300)
    assert (W >= 0).all() and (H >= 0).all()
    # chi2 reducido ~ 1 cuando el modelo es correcto.
    dof = V.size - 3 * (V.shape[0] + V.shape[1])
    assert wnmf.chi2(V, wts, W, H) / dof == pytest.approx(1.0, abs=0.15)


def test_pesos_cero_ignoran_basura():
    V, wts, V0, _, _ = synthetic()
    V = V.copy()
    V[0, :5] = np.nan
    V[1, 10] = 1e6
    wts = wts.copy()
    wts[0, :5] = 0.0
    wts[1, 10] = 0.0
    W, H, _ = wnmf.fit(V, wts, 3, n_iter=500, tol=1e-12)
    assert abs((W @ H)[1, 10] - V0[1, 10]) < 0.02 * V0.max()


def test_nan_con_peso_es_error():
    V, wts, *_ = synthetic()
    V = V.copy()
    V[0, 0] = np.nan
    with pytest.raises(ValueError):
        wnmf.fit(V, wts, 3)


def test_componentes_normalizadas():
    V, wts, *_ = synthetic()
    _, H, _ = wnmf.fit(V, wts, 3, n_iter=50)
    assert np.allclose(np.linalg.norm(H, axis=1), 1.0)


def test_transform_de_objetos_nuevos():
    V, wts, V0, _, _ = synthetic(n=50)
    W, H, _ = wnmf.fit(V[:40], wts[:40], 3, n_iter=500, tol=1e-12)
    Wn = wnmf.transform(V[40:], wts[40:], H)
    assert np.allclose(Wn @ H, V0[40:], atol=1e-2 * V0.max())


def test_ridge_no_sube_y_evita_extrapolar():
    # Un objeto observado solo en la primera mitad de la rejilla.
    V, wts, V0, _, _ = synthetic(noise=0.05, width=0.05)
    wts = wts.copy()
    wts[0, 30:] = 0.0
    alpha = 1e-3 * np.median(wts[wts > 0])
    W, H, hist = wnmf.fit(V, wts, 3, n_iter=100, tol=0, alpha=alpha)
    assert np.all(np.diff(hist) <= 1e-9 * hist[:-1])
    assert np.allclose(np.linalg.norm(H, axis=1), 1.0)
    assert np.abs((W @ H)[0, 30:] - V0[0, 30:]).max() < 0.5 * V0.max()


def test_cv_elige_el_k_verdadero():
    V, wts, *_ = synthetic(noise=0.03, k=3)
    s = {k: wnmf.cv_score(V, wts, k, n_folds=3, n_iter=150)[0] for k in (1, 2, 3)}
    assert s[3] < s[2] < s[1]
    assert s[3] == pytest.approx(1.0, abs=0.3)  # chi2 por celda ~ 1 en celdas ocultas
