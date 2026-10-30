"""NMF con pesos y datos faltantes: V ~ W H con W, H >= 0.

Minimiza chi2 = sum_ij w_ij (V_ij - (W H)_ij)^2, con w_ij = 1/sigma_ij^2 y w_ij = 0 en celdas
sin dato. Es el mismo objetivo que Blanton & Roweis (2007) y Zhu (2016), pero se resuelve por
minimos cuadrados alternados con NNLS exacto (scipy.optimize.nnls) en lugar de reglas
multiplicativas:

- cada subproblema (una fila de W, o una columna de H) es un NNLS exacto, asi que chi2 nunca
  sube entre iteraciones;
- V puede tener valores negativos (flujo con ruido cerca de cero), que las reglas
  multiplicativas no admiten.

Opcion `alpha` (ridge): suma alpha * (||W||^2 + ||H||^2) al objetivo. Evita que un objeto con
huecos en la rejilla tome un coeficiente enorme en una componente casi nula donde el objeto
tiene datos, lo que da predicciones absurdas en sus celdas sin dato. Se penalizan W y H a la
vez porque penalizar solo W no restringe nada: bastaria escalar W hacia abajo y H hacia arriba.
Con alpha = 0 (por defecto) es el NMF sin regularizar.

Convencion: V tiene forma (objetos, celdas). Las filas de H (componentes) se normalizan a norma
unitaria y la escala pasa a W, para que W sea comparable entre corridas.
"""
import numpy as np
from scipy.optimize import nnls


def _check(V, weights):
    V = np.asarray(V, dtype=float)
    Wt = np.asarray(weights, dtype=float)
    if V.shape != Wt.shape:
        raise ValueError(f"V {V.shape} y weights {Wt.shape} no coinciden")
    if np.any(Wt < 0) or not np.all(np.isfinite(Wt)):
        raise ValueError("weights debe ser finito y >= 0")
    bad = ~np.isfinite(V)
    if np.any(bad & (Wt > 0)):
        raise ValueError("V no finito en celdas con peso > 0")
    return np.where(bad, 0.0, V), Wt


def _wnnls(A, b, w, alpha=0.0):
    """argmin_{x>=0} sum w (b - A x)^2 + alpha ||x||^2."""
    keep = w > 0
    if not np.any(keep):
        return np.zeros(A.shape[1])
    s = np.sqrt(w[keep])
    A2, b2 = A[keep] * s[:, None], b[keep] * s
    if alpha > 0:
        k = A.shape[1]
        A2 = np.vstack([A2, np.sqrt(alpha) * np.eye(k)])
        b2 = np.concatenate([b2, np.zeros(k)])
    x, _ = nnls(A2, b2, maxiter=50 * A.shape[1])
    return x


def chi2(V, weights, W, H):
    V, Wt = _check(V, weights)
    return float(np.sum(Wt * (V - W @ H) ** 2))


def objective(V, weights, W, H, alpha=0.0):
    return chi2(V, weights, W, H) + alpha * float(np.sum(W ** 2) + np.sum(H ** 2))


def _normalize(W, H):
    n = np.linalg.norm(H, axis=1)
    n[n == 0] = 1.0
    return W * n, H / n[:, None]


def transform(V, weights, H, alpha=0.0):
    """Coeficientes W >= 0 de objetos nuevos con componentes H fijas."""
    V, Wt = _check(V, weights)
    return np.vstack([_wnnls(H.T, V[i], Wt[i], alpha) for i in range(V.shape[0])])


def fit(V, weights, k, n_iter=200, tol=1e-6, seed=0, H0=None, W0=None, alpha=0.0):
    """Ajusta W (objetos x k) y H (k x celdas).

    Para cuando la mejora relativa del objetivo es menor que `tol`. Devuelve (W, H, historial
    del objetivo; con alpha = 0 es chi2). Con alpha > 0, H se normaliza solo al final (la
    penalizacion fija la escala entre W y H durante el ajuste); W @ H no cambia.
    """
    V, Wt = _check(V, weights)
    n, m = V.shape
    rng = np.random.default_rng(seed)
    scale = np.sqrt(max(np.average(np.clip(V, 0, None), weights=Wt + 1e-300), 1e-12) / k)
    H = rng.uniform(0, 1, (k, m)) if H0 is None else np.array(H0, dtype=float)
    W = rng.uniform(0, 1, (n, k)) * scale if W0 is None else np.array(W0, dtype=float)
    W, H = _normalize(W, H)
    hist = [objective(V, Wt, W, H, alpha)]
    for _ in range(n_iter):
        W = np.vstack([_wnnls(H.T, V[i], Wt[i], alpha) for i in range(n)])
        H = np.vstack([_wnnls(W, V[:, j], Wt[:, j], alpha) for j in range(m)]).T
        if alpha == 0:
            W, H = _normalize(W, H)
        hist.append(objective(V, Wt, W, H, alpha))
        if hist[-2] > 0 and (hist[-2] - hist[-1]) <= tol * hist[-2]:
            break
    W, H = _normalize(W, H)
    return W, H, np.array(hist)


def cv_score(V, weights, k, frac=0.1, n_folds=5, seed=0, **fit_kw):
    """Validacion cruzada por celdas: oculta `frac` de las celdas con dato, ajusta con el resto y
    mide chi2 por celda en las ocultas. Devuelve (media, lista por pliegue, mediana por celda);
    la mediana muestra el error tipico aunque un pliegue tenga una extrapolacion catastrofica."""
    V, Wt = _check(V, weights)
    rng = np.random.default_rng(seed)
    obs = np.argwhere(Wt > 0)
    scores, all_r = [], []
    for f in range(n_folds):
        pick = obs[rng.random(len(obs)) < frac]
        held = np.zeros_like(Wt, dtype=bool)
        held[pick[:, 0], pick[:, 1]] = True
        W, H, _ = fit(V, np.where(held, 0.0, Wt), k, seed=seed + f, **fit_kw)
        r = Wt[held] * (V[held] - (W @ H)[held]) ** 2
        scores.append(float(r.mean()))
        all_r.append(r)
    return float(np.mean(scores)), scores, float(np.median(np.concatenate(all_r)))
