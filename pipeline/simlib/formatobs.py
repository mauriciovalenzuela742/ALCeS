"""
formatobs.py — Calculo de cantidades SNANA a partir de columnas OpSim.

Reimplementa formatObs del notebook (arxiv:1905.02887), puro numpy:

    sigma_PSF = seeingFwhmEff / (2 sqrt(2 ln2))
    PSF[pix]  = sigma_PSF / pixsize
    A         = 4 pi sigma_PSF^2                        (noise-equivalent area)
    ZPT       = 2 m5 - m_sky + 2.5 log10(25 A)
                            + 2.5 log10(1 + 10^{-0.4 (m5-m_sky)} / A)
    SKYSIG    = sqrt( 10^{-0.4 (m_sky - ZPT)} * pixsize^2 )

donde  m5 = fiveSigmaDepth,  m_sky = skyBrightness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# columnas OpSim requeridas
REQUIRED_COLS = ("observationStartMJD", "band", "seeingFwhmEff",
                 "fiveSigmaDepth", "skyBrightness")


def format_obs(obs: pd.DataFrame, pixsize: float = 0.2) -> pd.DataFrame:
    """Devuelve un DataFrame con expMJD, ObsID, BAND, SKYSIG, PSF, ZPT, m5.

    `m5` (= fiveSigmaDepth) se conserva para el reporte de cobertura / MAF.
    La banda 'y' se normaliza a 'Y' (convencion SNANA / tus SIMLIB).
    """
    missing = [c for c in REQUIRED_COLS if c not in obs.columns]
    if missing:
        raise KeyError(f"format_obs: faltan columnas OpSim {missing}")

    sig_psf = obs["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    psf = sig_psf / pixsize
    noise_area = 4 * np.pi * sig_psf ** 2

    m5 = obs["fiveSigmaDepth"].to_numpy()
    msky = obs["skyBrightness"].to_numpy()
    dmag = m5 - msky

    zpt = (2 * m5 - msky
           + 2.5 * np.log10(25 * noise_area)
           + 2.5 * np.log10(1 + 10 ** (-0.4 * dmag) / noise_area))
    skysig = np.sqrt(10 ** (-0.4 * (msky - zpt)) * pixsize ** 2)

    # ObsID: usa observationId si esta (columna o indice), si no un rango
    if "observationId" in obs.columns:
        obsid = obs["observationId"].to_numpy()
    elif obs.index.name == "observationId":
        obsid = obs.index.to_numpy()
    else:
        obsid = np.arange(len(obs))

    band = obs["band"].astype(str).map(lambda x: "Y" if x == "y" else x).to_numpy()

    return pd.DataFrame({
        "expMJD": obs["observationStartMJD"].to_numpy(),
        "ObsID": obsid,
        "BAND": band,
        "SKYSIG": skysig,
        "PSF": psf,
        "ZPT": zpt,
        "m5": m5,
    })
