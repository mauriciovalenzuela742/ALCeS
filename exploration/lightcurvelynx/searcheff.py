"""
Post-proceso de eficiencia de deteccion real de SNANA, aplicado sobre la
fotometria cruda (flux/fluxerr) que produce LightCurveLynx -- reemplaza el
escalon duro (SNR>5 -> 1.0) que trae LightCurveLynx nativo
(astro_utils/obs_utils.py::phot_eff_function) por la curva real de la
campana (Kessler et al. 2019 / PLAsTiCC), y aplica la misma logica de
trigger multi-epoca que usa snlc_sim.exe.

Fuentes (NLHPC, ver campaigns/full_v5.3.yaml -> searcheff_pipeline_file/
searcheff_pipeline_logic_file):
    /home/mvalenzuela/run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT
    /home/mvalenzuela/run_SNANA/LSST_PIPELINE_LOGIC.DAT

PHOTFLAG_DETECT=4096 (SNANA) -- mismo valor que usa pipeline/postproc/qc.py
para filtrar detecciones reales, asi los dos lados de la comparacion usan
exactamente la misma definicion.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

PHOTFLAG_DETECT = 4096
PHOTFLAG_NONDET = 0


def parse_searcheff_pipeline(path: str | Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Parsea LSST_SEARCHEFF_PIPELINE.DAT -> {banda: (snr_grid, eff_grid)}."""
    path = Path(path)
    curves: dict[str, list[tuple[float, float]]] = {}
    current_band = None
    for line in path.read_text().splitlines():
        line = line.strip()
        m = re.match(r"^FILTER:\s*(\S+)", line)
        if m:
            current_band = m.group(1)
            curves.setdefault(current_band, [])
            continue
        m = re.match(r"^ABS\(SNR\):\s*([\d.]+)\s+([\d.]+)", line)
        if m and current_band is not None:
            curves[current_band].append((float(m.group(1)), float(m.group(2))))
    return {
        band: (np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
        for band, pts in curves.items()
        if pts
    }


def parse_pipeline_logic(path: str | Path) -> int:
    """Parsea LSST_PIPELINE_LOGIC.DAT -> numero minimo de epocas detectadas
    requeridas (ignora la lista de filtros -- el .DAT real dice
    "2 u+g+r+i+z+Y", es decir 2 epocas en CUALQUIER combinacion de esas
    bandas, no 2 por banda)."""
    text = Path(path).read_text()
    m = re.search(r"^LSST:\s*(\d+)\s", text, re.MULTILINE)
    if not m:
        raise ValueError(f"no se encontro la linea 'LSST: <N> ...' en {path}")
    return int(m.group(1))


def apply_detection_efficiency(
    phot_df: pd.DataFrame,
    band_curves: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    band_col: str = "FLT",
    flux_col: str = "FLUXCAL",
    fluxerr_col: str = "FLUXCALERR",
    seed: int | None = None,
) -> pd.Series:
    """Por cada observacion: SNR=flux/fluxerr, interpola eficiencia de la
    banda correspondiente, sortea Monte Carlo si se detecta. Devuelve una
    Series booleana alineada con phot_df.index."""
    rng = np.random.default_rng(seed)
    snr = (phot_df[flux_col] / phot_df[fluxerr_col]).abs().to_numpy()
    bands = phot_df[band_col].astype(str).to_numpy()

    eff = np.zeros(len(phot_df))
    for band, (snr_grid, eff_grid) in band_curves.items():
        mask = bands == band
        if mask.any():
            eff[mask] = np.interp(snr[mask], snr_grid, eff_grid, left=0.0, right=eff_grid[-1])

    missing = set(np.unique(bands)) - set(band_curves)
    if missing:
        print(f"  ! bandas sin curva SEARCHEFF, eficiencia=0: {sorted(missing)}")

    draw = rng.uniform(size=len(phot_df))
    return pd.Series(draw < eff, index=phot_df.index)


def apply_pipeline_trigger(
    phot_df: pd.DataFrame,
    detected_mask: pd.Series,
    *,
    snid_col: str = "SNID",
    min_epochs: int = 2,
) -> pd.DataFrame:
    """Agrega la columna PHOTFLAG (4096 si esa epoca fue detectada, 0 si
    no) y, ademas, devuelve solo phot_df -- el trigger a nivel de objeto
    (>= min_epochs detectadas) se calcula aparte en el caller sobre el
    resultado, igual que SNANA marca el objeto completo como "encontrado"
    sin alterar el PHOTFLAG de cada epoca individual."""
    out = phot_df.copy()
    out["PHOTFLAG"] = np.where(detected_mask, PHOTFLAG_DETECT, PHOTFLAG_NONDET)
    return out


def object_level_detected(phot_df_with_flag: pd.DataFrame, *, snid_col: str = "SNID",
                           min_epochs: int = 2) -> set:
    """SNID de los objetos que superan el trigger (>= min_epochs con
    PHOTFLAG_DETECT, en cualquier combinacion de filtros)."""
    counts = phot_df_with_flag[phot_df_with_flag["PHOTFLAG"] == PHOTFLAG_DETECT].groupby(snid_col).size()
    return set(counts[counts >= min_epochs].index)


if __name__ == "__main__":
    curves = parse_searcheff_pipeline(
        "/home/mvalenzuela/run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT"
    )
    print("bandas parseadas:", sorted(curves.keys()))
    for band, (snr, eff) in curves.items():
        print(f"  {band}: {len(snr)} puntos, SNR [{snr.min():.1f},{snr.max():.1f}], "
              f"eff en SNR=5.0 -> {np.interp(5.0, snr, eff):.3f}")
    min_epochs = parse_pipeline_logic("/home/mvalenzuela/run_SNANA/LSST_PIPELINE_LOGIC.DAT")
    print("min_epochs trigger:", min_epochs)
