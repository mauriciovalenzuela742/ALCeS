"""
Fase 2 parte A1 -- compara numericamente, termino a termino, la derivacion
de ruido fotometrico de SNANA (pipeline.simlib.formatobs.format_obs(), ya
en produccion, Capa 1) contra la de LightCurveLynx
(lightcurvelynx.obstable.opsim.OpSim._derive_noise_columns()), sobre las
MISMAS filas crudas de OpSim (visitas DDF reales) -- para aislar cual
termino (sky, psf_footprint, zp) explica la brecha de eficiencia de
deteccion encontrada en Fase 1 (ver NOTES.md puntos 7 y 7b).

Conversion SNANA -> convencion LightCurveLynx (GAIN=1.0, confirmado en
Fase 1 contra el phot_df real de SNIa_DDF):
    sky_bg_e      = SKYSIG**2                  (sigma ADU->electrones -> media Poisson)
    psf_footprint = noise_area / pixsize**2    (arcsec^2 -> pixeles^2)
    zp            = mag2flux(ZPT)              (AB mag de 1 electron -> nJy/electron)

Uso (liviano, solo lee OpSim + calcula -- no simula curvas de luz, corre
en el login node sin problema, no dispara el guardia de SLURM):
    python3 compare_noise_formulas.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402

from lightcurvelynx.astro_utils.mag_flux import mag2flux  # noqa: E402
from lightcurvelynx.obstable.opsim import OpSim  # noqa: E402

OPSIM_DB = Path("/home/mvalenzuela/AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db")
PIXSIZE = 0.2  # arcsec/pixel, LSSTCam


def main():
    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    print(f"visitas DDF: {len(df_ddf):,}")

    # -- SNANA real (Capa 1, pipeline.simlib.formatobs, ya en produccion) --
    # el OpSim crudo ya trae 'band' como columna propia (ademas de 'filter'),
    # no hace falta renombrar nada.
    snana = format_obs(df_ddf, pixsize=PIXSIZE)
    sig_psf_arcsec = df_ddf["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    noise_area_arcsec2 = 4 * np.pi * sig_psf_arcsec ** 2

    snana_sky_bg_e = snana["SKYSIG"].to_numpy() ** 2
    snana_psf_footprint = noise_area_arcsec2 / PIXSIZE ** 2
    snana_zp = mag2flux(snana["ZPT"].to_numpy())

    # -- LightCurveLynx (misma OpSim real, sin overrides) --
    lcl = OpSim(df_ddf, zp_err_mag=0.005)
    t = lcl._table
    lcl_sky_bg_e = t["sky_bg_e"].to_numpy()
    lcl_psf_footprint = t["psf_footprint"].to_numpy()
    lcl_zp = t["zp"].to_numpy()

    print("\n=== comparacion termino a termino (SNANA real vs LightCurveLynx) ===")
    for name, snana_vals, lcl_vals in [
        ("sky_bg_e (electrones/pixel)", snana_sky_bg_e, lcl_sky_bg_e),
        ("psf_footprint (pixeles^2)", snana_psf_footprint, lcl_psf_footprint),
        ("zp (nJy/electron)", snana_zp, lcl_zp),
    ]:
        ratio = lcl_vals / snana_vals
        print(f"\n{name}:")
        print(f"  SNANA   mediana={np.median(snana_vals):.4g}  p10={np.percentile(snana_vals,10):.4g}  p90={np.percentile(snana_vals,90):.4g}")
        print(f"  LCL     mediana={np.median(lcl_vals):.4g}  p10={np.percentile(lcl_vals,10):.4g}  p90={np.percentile(lcl_vals,90):.4g}")
        print(f"  razon (LCL/SNANA) mediana={np.median(ratio):.4f}  p10={np.percentile(ratio,10):.4f}  p90={np.percentile(ratio,90):.4f}")

    # -- SNR predicho para una fuente de referencia fija, ambos sistemas --
    # (usa la formula de poisson_bandflux_std de LightCurveLynx con cada
    # conjunto de inputs, para traducir la comparacion de terminos a un
    # numero directamente comparable al SNR real medido en Fase 1)
    from lightcurvelynx.noise_models.noise_utils import poisson_bandflux_std

    ref_flux_njy = 100.0  # fuente de referencia arbitraria, misma para ambos
    exptime = df_ddf["visitExposureTime"].to_numpy()
    nexp = df_ddf["numExposures"].to_numpy()

    sigma_snana_inputs = poisson_bandflux_std(
        ref_flux_njy, total_exposure_time=exptime, exposure_count=nexp,
        psf_footprint=snana_psf_footprint, sky=snana_sky_bg_e, zp=snana_zp,
        readout_noise=8.8, dark_current=0.2, zp_err_mag=0.005,
    )
    sigma_lcl_inputs = poisson_bandflux_std(
        ref_flux_njy, total_exposure_time=exptime, exposure_count=nexp,
        psf_footprint=lcl_psf_footprint, sky=lcl_sky_bg_e, zp=lcl_zp,
        readout_noise=8.8, dark_current=0.2, zp_err_mag=0.005,
    )
    snr_snana = ref_flux_njy / sigma_snana_inputs
    snr_lcl = ref_flux_njy / sigma_lcl_inputs
    print(f"\n=== SNR de una fuente de referencia fija ({ref_flux_njy} nJy), mismo ruido de lectura/oscuro ===")
    print(f"  con inputs derivados de SNANA real:      mediana SNR={np.median(snr_snana):.3f}")
    print(f"  con inputs derivados de LightCurveLynx:  mediana SNR={np.median(snr_lcl):.3f}")
    print(f"  razon: {np.median(snr_lcl)/np.median(snr_snana):.3f}x")


if __name__ == "__main__":
    main()
