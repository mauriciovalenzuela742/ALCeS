"""NMF fotometrico exploratorio de SNII de CSP-I (solo forma, sin distancias).

Uso:
    python explore_csp_snii_phot.py [--kmax 5] [--out out/csp_snii_phot]

Entrada: assemble/out/csp_snii/photometry.csv (correr antes assemble/build_csp_snii.py).

Matriz V: una fila por SN, una celda por (banda, bin de fase en reposo desde la explosion).
Cada celda es la media ponderada del flujo f_nu (AB, corregido por la Via Lactea) en el bin;
celdas sin datos tienen peso 0, porque el NMF admite datos faltantes y no hace falta
interpolar. Cada SN se divide por su flujo medio en V entre NORM_WINDOW dias (plateau), asi
que W describe forma y color, no luminosidad: la luminosidad necesita distancias (pregunta 4
al profesor) y queda fuera.

Es exploratorio: sirve para ver cuantas componentes soportan los datos y que forma tienen, no
para producir un template para SNANA.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wnmf  # noqa: E402

PHOT = os.path.join(HERE, "..", "assemble", "out", "csp_snii", "photometry.csv")
BANDS = ["u", "B", "g", "V", "r", "i"]
PHASE_EDGES = np.arange(0.0, 144.0 + 1e-9, 4.0)  # 36 bins de 4 dias
NORM_BAND, NORM_WINDOW = "V", (20.0, 60.0)
ERR_FLOOR_MAG = 0.03  # piso de calibracion, en cuadratura
MIN_CELLS = 30  # celdas con dato por SN
MIN_OBJ = 10  # SNe con dato por celda: con menos, la columna de H queda mal restringida


def build_matrix(ph):
    ph = ph[ph["in_sample"] & ph["mag_ab"].notna() & ph["band"].isin(BANDS)].copy()
    ph = ph[(ph["phase_rest"] >= PHASE_EDGES[0]) & (ph["phase_rest"] < PHASE_EDGES[-1])]
    err_mag = np.hypot(ph["mag_err"], ERR_FLOOR_MAG)
    ph["ivar"] = 1.0 / (ph["fnu_ujy"] * err_mag * np.log(10) / 2.5) ** 2
    ph["pbin"] = np.digitize(ph["phase_rest"], PHASE_EDGES) - 1

    nb = len(PHASE_EDGES) - 1
    cells = [(b, i) for b in BANDS for i in range(nb)]
    col = {c: j for j, c in enumerate(cells)}
    sns = sorted(ph["sn"].unique())
    V = np.zeros((len(sns), len(cells)))
    Wt = np.zeros_like(V)
    norm = {}
    for r, sn in enumerate(sns):
        d = ph[ph["sn"] == sn]
        w = d[(d["band"] == NORM_BAND) & d["phase_rest"].between(*NORM_WINDOW)]
        if len(w) < 2:
            continue
        f0 = np.average(w["fnu_ujy"], weights=w["ivar"])
        norm[sn] = f0
        for (b, i), g in d.groupby(["band", "pbin"]):
            j = col[(b, i)]
            iv = g["ivar"].to_numpy() * f0 ** 2
            V[r, j] = np.average(g["fnu_ujy"] / f0, weights=iv)
            Wt[r, j] = iv.sum()
    keep = np.array([sn in norm and (Wt[r] > 0).sum() >= MIN_CELLS for r, sn in enumerate(sns)])
    V, Wt = V[keep], Wt[keep]
    good = (Wt > 0).sum(0) >= MIN_OBJ
    return V[:, good], Wt[:, good], [s for s, k in zip(sns, keep) if k], [c for c, g in zip(cells, good) if g]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kmax", type=int, default=5)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--alphas", type=float, nargs="+", default=[0.0, 1e-3, 1e-2, 1e-1])
    ap.add_argument("--out", default=os.path.join(HERE, "out", "csp_snii_phot"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    V, Wt, sns, cells = build_matrix(pd.read_csv(PHOT, dtype={"sn": str}))
    cover = (Wt > 0).mean()
    print(f"matriz: {V.shape[0]} SNe x {V.shape[1]} celdas; cobertura {cover:.0%}")

    # alpha en unidades de la mediana de los pesos: alpha = a * median(w) equivale a sumar
    # unas `a` celdas tipicas que empujan cada coeficiente hacia 0.
    wmed = float(np.median(Wt[Wt > 0]))
    cv = {}
    for a in args.alphas:
        for k in range(1, args.kmax + 1):
            mean, folds, med = wnmf.cv_score(V, Wt, k, frac=0.1, n_folds=args.folds, n_iter=300,
                                             alpha=a * wmed)
            cv[(a, k)] = (mean, float(np.std(folds)), med)
            print(f"a={a:g} k={k}: chi2 por celda oculta: media {mean:.1f} +- {np.std(folds):.1f}, "
                  f"mediana {med:.1f}", flush=True)

    # Eleccion: menor media; con empate dentro del ruido entre pliegues, el k mas chico.
    best_a, best = min(cv, key=lambda ak: cv[ak][0])
    for k in range(1, best):
        if cv[(best_a, k)][0] - cv[(best_a, best)][0] <= cv[(best_a, best)][1]:
            best = k
            break
    W, H, hist = wnmf.fit(V, Wt, best, n_iter=1000, tol=1e-8, alpha=best_a * wmed)
    chi2_red = wnmf.chi2(V, Wt, W, H) / max((Wt > 0).sum() - best * (V.shape[0] + V.shape[1]), 1)
    print(f"elegido: a={best_a:g}, k={best}; chi2 reducido del ajuste = {chi2_red:.2f}; "
          f"iteraciones = {len(hist) - 1}")

    np.savez_compressed(os.path.join(args.out, "nmf.npz"), V=V, weights=Wt, W=W, H=H,
                        sns=np.array(sns), bands=np.array(BANDS), phase_edges=PHASE_EDGES)
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump({"n_sne": len(sns), "n_cells": len(cells), "coverage": cover,
                   "cv": [{"a": a, "k": k, "mean": v[0], "std": v[1], "median": v[2]}
                          for (a, k), v in cv.items()],
                   "a": best_a, "k": best, "chi2_red": chi2_red}, f, indent=1)
    plot(H, W, cells, args.out)
    return 0


def plot(H, W, cells, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    k = H.shape[0]
    mid = 0.5 * (PHASE_EDGES[:-1] + PHASE_EDGES[1:])
    fig, axes = plt.subplots(1, k, figsize=(4 * k, 3.2), squeeze=False)
    for c in range(k):
        ax = axes[0, c]
        for b in BANDS:
            idx = [j for j, (cb, _) in enumerate(cells) if cb == b]
            ax.plot([mid[cells[j][1]] for j in idx], H[c, idx], ".-", label=b)
        ax.set_title(f"componente {c + 1}")
        ax.set_xlabel("dias desde la explosion (reposo)")
    axes[0, 0].set_ylabel("flujo relativo (norma 1)")
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "components.png"), dpi=120)

    if k >= 2:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.scatter(W[:, 0], W[:, 1], s=12)
        ax.set_xlabel("W1")
        ax.set_ylabel("W2")
        fig.tight_layout()
        fig.savefig(os.path.join(out, "coefficients.png"), dpi=120)


if __name__ == "__main__":
    sys.exit(main())
