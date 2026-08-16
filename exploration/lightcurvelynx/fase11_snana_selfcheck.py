"""
fase11_snana_selfcheck.py -- Fase 11 (Paso 1, barato): busca evidencia de un
artefacto de interpolacion en la grilla LOGZBIN de SIMSED usando SOLO el
.DUMP real de SNANA (PEAKMAG_r, ZCMB, MU, "SELECTION: NONE" -- ver Fase 7),
de una corrida con GENRANGE_REDSHIFT angosto (3-5 celdas de grilla) y
NGENTOT_LC grande, para muestrear esa ventana con densidad suficiente.
No necesita evaluar LightCurveLynx en absoluto todavia -- si esto sale
plano (sin patron vs frac), Fase 11 se descarta barato aqui mismo, sin
construir la comparacion completa contra LCL.

Metodo:
- `PEAKMAG_r - MU` remueve el termino de distancia (MU, columna real del
  .DUMP, calculada por cosmologia -- suave, sin relacion con la
  interpolacion de grilla).
- Se ajusta un polinomio de bajo orden (grado 2) en log10(z) sobre ESE
  residuo, agrupando TODOS los objetos de la ventana (no hace falta que se
  repita el mismo template SIMSED a distintos z -- el ruido objeto-a-objeto
  de parametros SIMSED/stretch/color independientes del redshift no sesga
  el ajuste de la tendencia suave, solo agrega varianza) -- esto remueve
  cualquier tendencia suave real (K-correction) que sobreviva dentro de la
  ventana angosta.
- El residuo de ESE ajuste se cuadricula por posicion fraccional dentro de
  una celda de la grilla LOGZBIN real de la clase (frac=0 en un nodo exacto,
  frac=0.5 en el punto medio entre nodos) -- si la interpolacion lineal de
  SNANA tiene sesgo sistematico entre nodos, deberia aparecer como un
  patron periodico (pico cerca de frac=0.5, minimo cerca de frac=0/1); si
  no, los residuos deberian verse planos/sin patron vs frac.

Uso:
    python3 fase11_snana_selfcheck.py SNIa-91bg
    python3 fase11_snana_selfcheck.py SLSN-I-MOSFIT
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_brightness import read_snana_dump  # noqa: E402

HERE = Path(__file__).resolve().parent
LOGDIR = HERE / "fase11_simsed_zgrid"

CLASS_CONFIGS = {
    "SNIa-91bg": dict(
        dump_path=LOGDIR / "Fase11_zgrid_SNIa91bg_DDF.DUMP",
        z_anchor=0.011,
        logzbin=0.02,
    ),
    "SLSN-I-MOSFIT": dict(
        dump_path=LOGDIR / "Fase11_zgrid_SLSNIMOSFIT_DDF.DUMP",
        z_anchor=0.02,
        logzbin=0.1,
    ),
}


def main(class_key: str) -> None:
    cfg = CLASS_CONFIGS[class_key]
    df = read_snana_dump(cfg["dump_path"])
    print(f"[{class_key}] {len(df)} filas en el .DUMP (poblacion COMPLETA generada, "
          f"'SELECTION: NONE')")

    valid = (
        (df["PEAKMAG_r"] > -8) & (df["PEAKMAG_r"] < 90) & np.isfinite(df["PEAKMAG_r"])
        & np.isfinite(df["MU"]) & (df["MU"] > 0) & np.isfinite(df["ZCMB"]) & (df["ZCMB"] > 0)
    )
    df = df.loc[valid].copy()
    print(f"[{class_key}] {len(df)} filas validas (PEAKMAG_r/MU/ZCMB finitos), "
          f"z en [{df['ZCMB'].min():.5f}, {df['ZCMB'].max():.5f}]")

    y = (df["PEAKMAG_r"] - df["MU"]).to_numpy()
    x = np.log10(df["ZCMB"].to_numpy())

    coeffs = np.polyfit(x, y, 2)
    trend = np.polyval(coeffs, x)
    residual = y - trend
    print(f"[{class_key}] tendencia suave global ajustada (grado 2 en log10(z)); "
          f"std del residuo: {residual.std():.4f} mag")

    log10z_anchor = np.log10(cfg["z_anchor"])
    frac = ((x - log10z_anchor) / cfg["logzbin"]) % 1.0

    out = pd.DataFrame({"zcmb": df["ZCMB"].to_numpy(), "frac": frac, "residual": residual})
    bins = np.linspace(0, 1, 11)
    out["frac_bin"] = pd.cut(out["frac"], bins, include_lowest=True)
    summary = out.groupby("frac_bin", observed=True)["residual"].agg(["mean", "sem", "count"])
    print(f"\n[{class_key}] residuo(frac) por bin (mag, PEAKMAG_r - MU - tendencia suave):")
    print(summary.to_string(float_format=lambda v: f"{v:.4f}"))

    near_node = (out["frac"] < 0.1) | (out["frac"] > 0.9)
    near_mid = (out["frac"] > 0.4) & (out["frac"] < 0.6)
    m_node = out.loc[near_node, "residual"]
    m_mid = out.loc[near_mid, "residual"]
    print(f"\n[{class_key}] cerca de nodo (|frac-0|<0.1, N={len(m_node)}): "
          f"media={m_node.mean():.4f} +- sem={m_node.sem():.4f}")
    print(f"[{class_key}] cerca de punto medio (frac~0.5, N={len(m_mid)}): "
          f"media={m_mid.mean():.4f} +- sem={m_mid.sem():.4f}")
    print(f"[{class_key}] diferencia punto-medio menos nodo: "
          f"{m_mid.mean() - m_node.mean():.4f} mag")

    out_csv = HERE / f"fase11_snana_selfcheck_{class_key.replace(' ', '_').replace('/', '_')}.csv"
    out.to_csv(out_csv, index=False)
    print(f"\n[{class_key}] CSV completo ({len(out)} filas): {out_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CLASS_CONFIGS:
        print(f"uso: python3 fase11_snana_selfcheck.py <clase>  (clases: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    main(sys.argv[1])
