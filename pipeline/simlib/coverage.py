"""
coverage.py — Reporte de cobertura por banda (entregable de validacion).

Resume el SIMLIB generado para contrastarlo contra las metricas oficiales de
MAF (usdf-maf.slac.stanford.edu) antes de gastar computo simulando:

    por banda:  N visitas, m5 mediana, ZPT mediana, PSF mediana, SKYSIG mediana,
                cadencia mediana (gap entre visitas consecutivas dentro de un campo)
    global:     N total, N campos, rango de MJD, duracion en anhos

Es puro pandas/numpy: no depende de healpy ni de opsimsummary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_BANDS = ["u", "g", "r", "i", "z", "Y"]


def _median(a) -> float | None:
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    return float(np.median(a)) if a.size else None


def _median_cadence(sub: pd.DataFrame, mjd_col: str, field_col: str | None) -> float | None:
    """Mediana de los gaps entre visitas consecutivas.

    Si hay columna de campo, calcula el gap dentro de cada campo y promedia con
    mediana global (evita mezclar campos separados en el cielo).
    """
    if field_col and field_col in sub.columns:
        gaps = []
        for _, g in sub.groupby(field_col):
            mj = np.sort(g[mjd_col].to_numpy())
            d = np.diff(mj)
            gaps.extend(d[d > 0].tolist())
        return _median(gaps) if gaps else None
    mj = np.sort(sub[mjd_col].to_numpy())
    d = np.diff(mj)
    d = d[d > 0]
    return _median(d) if d.size else None


def coverage_report(
    fobs: pd.DataFrame,
    *,
    band_col: str = "BAND",
    mjd_col: str = "expMJD",
    m5_col: str = "m5",
    zpt_col: str = "ZPT",
    psf_col: str = "PSF",
    skysig_col: str = "SKYSIG",
    field_col: str | None = "field_id",
    n_fields: int | None = None,
    bands: list[str] | None = None,
) -> dict:
    """Construye el reporte de cobertura como dict serializable."""
    bands = bands or _BANDS
    total = len(fobs)
    mjd_min = float(fobs[mjd_col].min()) if total else None
    mjd_max = float(fobs[mjd_col].max()) if total else None

    per_band = []
    for b in bands:
        sub = fobs[fobs[band_col] == b]
        if sub.empty:
            per_band.append({"band": b, "n": 0})
            continue
        per_band.append({
            "band": b,
            "n": int(len(sub)),
            "frac": round(len(sub) / total, 4) if total else 0.0,
            "m5_median": _median(sub[m5_col]) if m5_col in sub else None,
            "zpt_median": _median(sub[zpt_col]) if zpt_col in sub else None,
            "psf_median": _median(sub[psf_col]) if psf_col in sub else None,
            "skysig_median": _median(sub[skysig_col]) if skysig_col in sub else None,
            "cadence_median_days": _median_cadence(sub, mjd_col, field_col),
        })

    return {
        "n_obs": total,
        "n_fields": int(n_fields) if n_fields is not None
                    else (int(fobs[field_col].nunique()) if field_col in fobs else None),
        "mjd_min": mjd_min,
        "mjd_max": mjd_max,
        "duration_years": round((mjd_max - mjd_min) / 365.25, 3) if total else None,
        "bands": per_band,
    }


def coverage_to_frame(report: dict) -> pd.DataFrame:
    """La tabla por banda como DataFrame (para guardar a CSV)."""
    return pd.DataFrame(report["bands"])
