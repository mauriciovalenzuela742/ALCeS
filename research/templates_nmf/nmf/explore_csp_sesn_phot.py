"""NMF fotometrico exploratorio de las SN despojadas de CSP-I (solo forma, sin distancias).

Uso:
    python explore_csp_sesn_phot.py [--kmax 5] [--alphas 0.1 0.3] [--exclude 2005bf]

Entrada: assemble/out/csp_sesn/photometry.csv (correr antes assemble/build_csp_sesn.py).

Igual que explore_csp_snii_phot.py, pero con la fase desde T(B)max y una ventana mas corta:
las despojadas evolucionan rapido y la fotometria de CSP-I llega a ~+80 dias. Cada SN se
divide por su flujo medio en V cerca del maximo (NORM_WINDOW), asi que el NMF ve forma y color.
Se ajusta un NMF conjunto (IIb, Ib, Ic, Ic-BL): por subtipo hay 10 SNe o menos. Al final se
compara W por subtipo, para ver si las componentes separan los subtipos.
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

PHOT = os.path.join(HERE, "..", "assemble", "out", "csp_sesn", "photometry.csv")
BANDS = ["u", "B", "g", "V", "r", "i"]
PHASE_EDGES = np.arange(-20.0, 80.0 + 1e-9, 4.0)  # 25 bins de 4 dias
NORM_BAND, NORM_WINDOW = "V", (-5.0, 15.0)
ERR_FLOOR_MAG = 0.03
MIN_CELLS = 20  # celdas con dato por SN
MIN_OBJ = 8  # SNe con dato por celda (hay 34 en total)


def build_matrix(ph, exclude=()):
    ph = ph[ph["mag_ab"].notna() & ph["band"].isin(BANDS) & ~ph["sn"].isin(exclude)].copy()
    ph = ph[(ph["phase_rest"] >= PHASE_EDGES[0]) & (ph["phase_rest"] < PHASE_EDGES[-1])]
    err_mag = np.hypot(ph["mag_err"].fillna(0.1), ERR_FLOOR_MAG)
    ph["ivar"] = 1.0 / (ph["fnu_ujy"] * err_mag * np.log(10) / 2.5) ** 2
    ph["pbin"] = np.digitize(ph["phase_rest"], PHASE_EDGES) - 1

    nb = len(PHASE_EDGES) - 1
    cells = [(b, i) for b in BANDS for i in range(nb)]
    col = {c: j for j, c in enumerate(cells)}
    sns = sorted(ph["sn"].unique())
    types = ph.groupby("sn")["type"].first()
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
    sns = [s for s, k in zip(sns, keep) if k]
    good = (Wt > 0).sum(0) >= MIN_OBJ
    return V[:, good], Wt[:, good], sns, [types[s] for s in sns], [c for c, g in zip(cells, good) if g]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kmax", type=int, default=5)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--alphas", type=float, nargs="+", default=[0.1, 0.3])
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="SNe a dejar fuera (p. ej. 2005bf, Ib peculiar de doble maximo)")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "csp_sesn_phot"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    V, Wt, sns, types, cells = build_matrix(pd.read_csv(PHOT, dtype={"sn": str}), args.exclude)
    cover = (Wt > 0).mean()
    print(f"matriz: {V.shape[0]} SNe x {V.shape[1]} celdas; cobertura {cover:.0%}; "
          f"tipos {pd.Series(types).value_counts().to_dict()}")

    wmed = float(np.median(Wt[Wt > 0]))
    cv = {}
    for a in args.alphas:
        for k in range(1, args.kmax + 1):
            mean, folds, med = wnmf.cv_score(V, Wt, k, frac=0.1, n_folds=args.folds, n_iter=300,
                                             alpha=a * wmed)
            cv[(a, k)] = (mean, float(np.std(folds)), med)
            print(f"a={a:g} k={k}: chi2 por celda oculta: media {mean:.1f} +- {np.std(folds):.1f}, "
                  f"mediana {med:.1f}", flush=True)

    # Misma regla que en SNII: menor media; con empate dentro del ruido, el k mas chico.
    best_a, best = min(cv, key=lambda ak: cv[ak][0])
    for k in range(1, best):
        if cv[(best_a, k)][0] - cv[(best_a, best)][0] <= cv[(best_a, best)][1]:
            best = k
            break
    W, H, hist = wnmf.fit(V, Wt, best, n_iter=1000, tol=1e-8, alpha=best_a * wmed)
    chi2_red = wnmf.chi2(V, Wt, W, H) / max((Wt > 0).sum() - best * (V.shape[0] + V.shape[1]), 1)
    print(f"elegido: a={best_a:g}, k={best}; chi2 reducido del ajuste = {chi2_red:.2f}")

    # Fraccion de cada componente por SN (W normalizado por fila), promediada por subtipo.
    frac = W / np.maximum(W.sum(1, keepdims=True), 1e-300)
    by_type = pd.DataFrame(frac, columns=[f"c{i + 1}" for i in range(best)]).assign(type=types)
    print("fraccion media de cada componente por subtipo:")
    print(by_type.groupby("type").mean().round(2).to_string())

    np.savez_compressed(os.path.join(args.out, "nmf.npz"), V=V, weights=Wt, W=W, H=H,
                        sns=np.array(sns), types=np.array(types), bands=np.array(BANDS),
                        phase_edges=PHASE_EDGES)
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump({"n_sne": len(sns), "n_cells": len(cells), "coverage": cover,
                   "cv": [{"a": a, "k": k, "mean": v[0], "std": v[1], "median": v[2]}
                          for (a, k), v in cv.items()],
                   "exclude": args.exclude, "a": best_a, "k": best, "chi2_red": chi2_red,
                   "frac_by_type": by_type.groupby("type").mean().to_dict()}, f, indent=1)
    plot(H, cells, args.out)
    return 0


def plot(H, cells, out):
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
        ax.set_xlabel("dias desde T(B)max (reposo)")
    axes[0, 0].set_ylabel("flujo relativo (norma 1)")
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "components.png"), dpi=120)


if __name__ == "__main__":
    sys.exit(main())
