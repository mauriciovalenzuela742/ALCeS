"""
build_wfd_mwebv_grid.py -- Fase 17 (WFD): construye una tabla real de E(B-V)
(SFD98, via el servicio REST IRSA Dust Extinction de NASA/IPAC, mismo
servicio y misma columna -- refPixelValueSFD -- usados para los 6 campos
DDF en Fase 0) sobre una grilla gruesa de posiciones reales del footprint
WFD (no hay campos fijos en WFD como en DDF, asi que no se puede usar un
diccionario de 6 valores -- se construye una tabla reusable en su lugar).

No consulta por objeto individual (miles de consultas HTTP serian lentas y
podrian saturar el servicio) -- en cambio, agrupa las posiciones reales del
OpSim WFD en una grilla de 8 grados DIRECTAMENTE EN SQL (un DISTINCT sin
agrupar sobre fieldRA/fieldDec no sirve -- 1,015,331 combinaciones unicas
solo para WFD, por el dithering real de LSST, casi ningun pointing se
repite exacto), consulta UNA VEZ por celda con al menos una observacion
real, y guarda el resultado. Los scripts run_*_poc.py usan esta tabla con
nearest-neighbor (separacion angular) para asignar E(B-V) a cada objeto
simulado segun su RA/DEC exacto.

Uso (una sola vez, resultado se versiona en el repo):
    python3 build_wfd_mwebv_grid.py
"""
from __future__ import annotations

import re
import sqlite3
import time
import urllib.request
from pathlib import Path

import pandas as pd
# Fase 74: REPO_ROOT resuelto por local_env.py (portabilidad).
from local_env import REPO_ROOT

HERE = Path(__file__).resolve().parent
OPSIM_DB = REPO_ROOT / "data/opsim/baseline_v5.3.1_10yrs.db"
GRID_DEG = 8.0
OUT_CSV = HERE / "wfd_mwebv_grid.csv"


def query_irsa_ebv_sfd(ra: float, dec: float, retries: int = 2) -> float | None:
    url = f"https://irsa.ipac.caltech.edu/cgi-bin/DUST/nph-dust?locstr={ra:.4f}+{dec:.4f}+equ+j2000"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            m = re.search(r"<refPixelValueSFD>\s*([\d.]+)\s*\(mag\)", text)
            if m:
                return float(m.group(1))
        except Exception as e:
            print(f"  intento {attempt+1} fallo para ({ra:.2f},{dec:.2f}): {e}", flush=True)
            time.sleep(1)
    return None


def main():
    con = sqlite3.connect(str(OPSIM_DB))
    # agrupa directamente en SQL (evita traer >1M filas de fieldRA/fieldDec
    # unicas -- casi cada pointing tiene una posicion ligeramente distinta
    # por el dithering real de LSST, asi que un DISTINCT sin agrupar no
    # reduce casi nada) -- confirmado: 1,015,331 combinaciones unicas de
    # (fieldRA,fieldDec) solo para WFD.
    query = f"""
        SELECT
            ROUND(fieldRA / {GRID_DEG}) AS ra_bin,
            ROUND(fieldDec / {GRID_DEG}) AS dec_bin,
            AVG(fieldRA) AS fieldRA,
            AVG(fieldDec) AS fieldDec,
            COUNT(*) AS n
        FROM observations
        WHERE target_name NOT LIKE '%ddf_%'
        GROUP BY ra_bin, dec_bin
    """
    t0 = time.time()
    centers = pd.read_sql_query(query, con)
    print(f"[{time.time()-t0:.1f}s] {len(centers)} celdas de grilla ({GRID_DEG} deg) "
          f"con observaciones WFD reales", flush=True)

    rows = []
    for i, row in centers.iterrows():
        ra, dec = float(row["fieldRA"]), float(row["fieldDec"])
        ebv = query_irsa_ebv_sfd(ra, dec)
        if ebv is not None:
            rows.append({"ra": ra, "dec": dec, "ebv_sfd": ebv})
        if i % 20 == 0:
            print(f"  [{time.time()-t0:.1f}s] {i+1}/{len(centers)} consultado", flush=True)
        time.sleep(0.2)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"[{time.time()-t0:.1f}s] tabla guardada: {OUT_CSV} ({len(out)} puntos)", flush=True)
    print(out["ebv_sfd"].describe())


if __name__ == "__main__":
    main()
