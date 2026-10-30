"""Fin del plateau de las SNII de CSP-I, medido en la curva de luz en V.

Uso:
    python fit_plateau_end.py

Entrada: out/csp_snii/photometry.csv y sample.csv (correr antes build_csp_snii.py).
Salida: out/csp_snii/plateau_end.csv.

Modelo de Olivares et al. (2010, ec. 4) sin la gaussiana del maximo temprano, ajustado solo a
fase >= MIN_PHASE:

    m(t) = -a0 / (1 + exp((t - t_PT) / w0)) + p0 (t - t_PT) + m0

t_PT es el centro de la caida desde el plateau a la cola (en dias en reposo desde la
explosion), w0 su ancho y p0 la pendiente de la cola. Hace falta ver la caida: si la curva
termina antes, solo se reporta una cota inferior (t_PT > ultima fase observada).

Sirve para alinear las curvas por el fin del plateau en el NMF sin depender de los OPTd
publicados (Anderson+14), que existen solo para 66 de las 122 SNe.
"""
import argparse
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

HERE = os.path.dirname(os.path.abspath(__file__))
CSP = os.path.join(HERE, "out", "csp_snii")
MIN_PHASE = 25.0  # deja fuera el maximo temprano
ERR_FLOOR_MAG = 0.03
MIN_BEFORE, MIN_AFTER = 3, 2  # puntos en el plateau (t < t_PT - w0) y despues de t_PT
MAX_TPT_ERR = 10.0  # dias
# Cotas fisicas: caida de 0.5-6 mag en 1-15 dias, cola de 0 a 0.04 mag/dia.
BOUNDS = ([10.0, 0.5, 1.0, 0.0, 25.0], [30.0, 6.0, 15.0, 0.04, 250.0])


def olivares(t, m0, a0, w0, p0, t_pt):
    x = np.clip((t - t_pt) / w0, -50, 50)
    return -a0 / (1.0 + np.exp(x)) + p0 * (t - t_pt) + m0


def _best_fit(t, m, e, fixed=None):
    """Mejor ajuste sobre una grilla de t_PT iniciales. `fixed` = (a0, w0) los deja fijos."""
    free = [0, 3, 4] if fixed else [0, 1, 2, 3, 4]
    lo, hi = np.array(BOUNDS[0])[free], np.array(BOUNDS[1])[free]

    def model(tt, *q):
        full = [q[0], *(fixed or q[1:3]), q[-2], q[-1]]
        return olivares(tt, *full)

    best = None
    for t0 in np.arange(max(40.0, t.min()), min(200.0, t.max()) + 1e-9, 5.0):
        m_init = m[t <= t0].mean() if np.any(t <= t0) else m.min()
        q0 = np.clip(np.array([m_init, 2.0, 3.0, 0.01, t0])[free], lo + 1e-6, hi - 1e-6)
        try:
            q, cov = curve_fit(model, t, m, p0=q0, sigma=e, absolute_sigma=True,
                               bounds=(lo, hi), maxfev=5000)
        except (RuntimeError, ValueError):
            continue
        c2 = float(np.sum(((m - model(t, *q)) / e) ** 2))
        if best is None or c2 < best[0]:
            best = (c2, q, cov)
    if best is None:
        return None
    c2, q, cov = best
    p = np.array([q[0], *(fixed or q[1:3]), q[-2], q[-1]])
    return c2, p, float(np.sqrt(cov[-1, -1])), len(q)


def fit_one(t, m, e, fixed=None, fixed_alt=()):
    """Ajusta una curva en V. Devuelve un dict con t_pt, su error y el estado:
    'ok', 'sin_caida', 'mal_medido', 'pocos_datos' o 'falla'.

    Con `fixed` = (a0, w0), la amplitud y el ancho de la caida quedan fijos: sirve cuando la
    curva muestra el inicio de la caida pero no la cola. Basta entonces con MIN_AFTER puntos
    dentro de la caida (t > t_PT - w0). `fixed_alt` son otros (a0, w0) plausibles; la
    dispersion de t_PT entre ellos entra en el error.
    """
    t, m, e = map(np.asarray, (t, m, e))
    out = {"t_pt": math.nan, "t_pt_err": math.nan, "w0": math.nan, "a0": math.nan,
           "p0": math.nan, "chi2_red": math.nan, "t_last": float(t.max()) if len(t) else math.nan}
    if len(t) < MIN_BEFORE + MIN_AFTER:
        return {**out, "status": "pocos_datos"}
    fit = _best_fit(t, m, e, fixed)
    if fit is None:
        return {**out, "status": "falla"}
    c2, p, err, npar = fit
    m0, a0, w0, p0, t_pt = p
    n_before = int(np.sum(t < t_pt - w0))
    n_after = int(np.sum(t > (t_pt - w0 if fixed else t_pt)))
    if fixed:
        alts = [_best_fit(t, m, e, f) for f in fixed_alt]
        spread = [abs(a[1][4] - t_pt) for a in alts if a is not None]
        err = max([err, *spread])
    else:
        # Con la cola poco muestreada, t_PT puede moverse libremente entre el ultimo punto
        # del plateau y el primero de la cola sin cambiar chi2, y la covarianza lo
        # subestima: el error es al menos la mitad de ese hueco.
        lo, hi = t[t <= t_pt], t[t > t_pt]
        gap = (hi.min() - lo.max()) / 2 if len(lo) and len(hi) else math.inf
        err = max(err, gap)
    res = {**out, "t_pt": float(t_pt), "t_pt_err": float(err), "w0": float(w0),
           "a0": float(a0), "p0": float(p0), "chi2_red": c2 / max(len(t) - npar, 1)}
    if n_before < MIN_BEFORE or n_after < MIN_AFTER:
        # Sin puntos a ambos lados la caida no esta medida; si la curva sigue en el plateau,
        # solo vale la cota t_PT > t_last.
        return {**res, "t_pt": math.nan, "t_pt_err": math.nan, "status": "sin_caida"}
    if not err <= MAX_TPT_ERR:
        return {**res, "status": "mal_medido"}
    return {**res, "status": "ok"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.parse_args(argv)
    ph = pd.read_csv(os.path.join(CSP, "photometry.csv"), dtype={"sn": str})
    sample = pd.read_csv(os.path.join(CSP, "sample.csv"), dtype={"sn": str})
    ph = ph[ph["in_sample"] & (ph["band"] == "V") & ph["mag_ab_mwcorr"].notna()
            & (ph["phase_rest"] >= MIN_PHASE)]
    curves = {sn: (d["phase_rest"].to_numpy(), d["mag_ab_mwcorr"].to_numpy(),
                   np.hypot(d["mag_err"].to_numpy(), ERR_FLOOR_MAG)) for sn, d in ph.groupby("sn")}

    # Pasada 1: todo libre. Pasada 2: a0 y w0 fijos en la mediana de los ajustes buenos de la
    # pasada 1 (con los percentiles 16 y 84 para el error), para curvas sin cola.
    rows = {sn: {"sn": sn, "n_v": len(c[0]), **fit_one(*c), "method": "libre"}
            for sn, c in curves.items()}
    good = pd.DataFrame([r for r in rows.values() if r["status"] == "ok"])
    if len(good) >= 5:
        med = (float(good["a0"].median()), float(good["w0"].median()))
        alt = [(float(good["a0"].quantile(q)), float(good["w0"].quantile(q))) for q in (0.16, 0.84)]
        print(f"pasada 2: a0 = {med[0]:.2f} mag, w0 = {med[1]:.2f} d (de {len(good)} ajustes libres)")
        for sn, r in rows.items():
            if r["status"] != "ok":
                r2 = fit_one(*curves[sn], fixed=med, fixed_alt=alt)
                if r2["status"] == "ok":
                    rows[sn] = {"sn": sn, "n_v": r["n_v"], **r2, "method": "a0_w0_fijos"}
    res = pd.DataFrame(list(rows.values())).merge(sample[["sn", "optd_a14_d", "z_helio"]], on="sn", how="left")
    res.to_csv(os.path.join(CSP, "plateau_end.csv"), index=False, float_format="%.4g")

    print(res.groupby(["status", "method"]).size().to_string())
    for meth in ("libre", "a0_w0_fijos"):
        ok = res[(res["status"] == "ok") & (res["method"] == meth) & res["optd_a14_d"].notna()]
        if len(ok):
            dlt = ok["t_pt"] - ok["optd_a14_d"]
            print(f"{meth}: t_PT - OPTd(A14) en {len(ok)} SNe: mediana {dlt.median():.1f} d, "
                  f"MAD {np.median(np.abs(dlt - dlt.median())):.1f} d")
    new = res[(res["status"] == "ok") & res["optd_a14_d"].isna()]
    print(f"con t_PT y sin OPTd publicado: {len(new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
