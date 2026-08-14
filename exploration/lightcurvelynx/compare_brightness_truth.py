"""
Fase 7 -- version corregida de compare_brightness.py: usa flux_perfect (el
flujo NO ruidoso que simulate_lightcurves() ya calcula internamente, ver
object_nested_dict["flux_perfect"] en lightcurvelynx/simulate.py) en vez del
minimo de FLUXCAL ruidoso -- SNANA PEAKMAG_r es una magnitud de pico
teorica/sin ruido, comparar contra el minimo de observaciones ruidosas de
LCL introduce un sesgo tipo Eddington (el minimo de N muestras ruidosas es
sistematicamente mas brillante que el pico real, mas fuerte a bajo SNR/alto
z) que podria fabricar por si solo el patron creciente con z que se vio en
la primera pasada.

Reconstruye el MISMO source_model real de SNIa-91bg SIMSED que
run_simsed_poc.py (mismos parametros, mismo H0=70, misma extincion MW) pero
captura flux_perfect en vez de descartarlo en el aplanado.

Uso (sbatch, no en login node -- carga 35 templates + simula 2000 objetos):
    python3 compare_brightness_truth.py
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.math_nodes.ra_dec_sampler import ObsTableRADECSampler
from lightcurvelynx.models.sed_template_model import SIMSEDModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
import sys

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx")
from snana_params import (
    build_dndz_powerlaw2_cdf, make_dndz_sampler, make_correlated_normal_weights,
    SizeAwareFunctionNode, ClippedExtinctionEffect,
)
from searcheff import parse_searcheff_pipeline  # noqa: F401 (unused here, kept for parity)

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402
from lightcurvelynx.astro_utils.mag_flux import mag2flux  # noqa: E402

HERE = Path("/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx")
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
PIXSIZE = 0.2
NGENTOT = 2000
SEED_BASE = 20260815
MW_RV = 3.1
DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
SIMSED_DIR = HERE / "simsed_91bg_local"
Z_MIN, Z_MAX = 0.011, 0.6


def snana_noise_columns(df_ddf):
    snana = format_obs(df_ddf, pixsize=PIXSIZE)
    sig_psf_arcsec = df_ddf["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    noise_area_arcsec2 = 4 * np.pi * sig_psf_arcsec ** 2
    out = df_ddf.copy()
    out["sky_bg_e"] = snana["SKYSIG"].to_numpy() ** 2
    out["psf_footprint"] = noise_area_arcsec2 / PIXSIZE ** 2
    out["zp"] = mag2flux(snana["ZPT"].to_numpy())
    return out


def main():
    t_start = time.time()
    seed_base = SEED_BASE

    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    df_ddf = snana_noise_columns(df_ddf)
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    print(f"[{time.time()-t_start:.1f}s] OpSim DDF: {len(df_ddf):,} obs")

    passband_group = PassbandGroup.from_preset(preset="LSST")
    print(f"[{time.time()-t_start:.1f}s] passbands cargados")

    file_names, _ = SIMSEDModel._read_simsed_info_file(SIMSED_DIR)
    sed_info_text = (SIMSED_DIR / "SED.INFO").read_text()
    param_names = None
    for line in sed_info_text.splitlines():
        if line.strip().upper().startswith("PARNAMES:"):
            param_names = line.split()[1:]
            break
    param_rows = [
        line.split()[2:] for line in sed_info_text.splitlines()
        if line.strip().upper().startswith("SED:")
    ]
    rc = dict(
        peaks=dict(stretch=0.975, color=0.557),
        sigmas=dict(stretch=0.096, color=0.175),
        redcor={("stretch", "color"): -0.656},
    )
    values = {
        name: np.array([float(r[i]) for r in param_rows])
        for i, name in enumerate(param_names) if name in rc["peaks"]
    }
    weights = make_correlated_normal_weights(values, rc["peaks"], rc["sigmas"], rc["redcor"])
    print(f"[{time.time()-t_start:.1f}s] {len(file_names)} templates SIMSED, pesos SIMSED_REDCOR")

    z_grid, cdf = build_dndz_powerlaw2_cdf(segments=[(3.0e-6, 1.5, Z_MIN, Z_MAX)], z_min=Z_MIN, z_max=Z_MAX)
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=seed_base + 1), node_label="redshift")
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=seed_base + 5, radius=0.0)
    radec_sampler.setters["selected_table_index"].dependency.set_seed(seed_base + 5)
    t0_func = NumpyRandomFunc(
        "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max()), seed=seed_base + 6,
    )

    def _luminosity_distance_pc(size=None, redshift=None, **_kwargs):
        from astropy.cosmology import FlatLambdaCDM
        import astropy.units as u
        cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)
        z = np.asarray(redshift)
        return cosmo.luminosity_distance(z).to(u.pc).value

    distance_func = SizeAwareFunctionNode(_luminosity_distance_pc, node_label="distance", redshift=redshift_func)

    def _field_to_ebv(size=None, field=None, **_kwargs):
        arr = np.asarray(field)
        return np.array([DDF_FIELD_EBV.get(f, 0.0) for f in arr.ravel()]).reshape(arr.shape)

    ebv_func = SizeAwareFunctionNode(_field_to_ebv, node_label="ebv", field=radec_sampler.field)
    mw_extinction = ClippedExtinctionEffect(
        extinction_model="O94", ebv=ebv_func, r_v=MW_RV, frame="observer", backend="dust_extinction",
    )

    source_model = SIMSEDModel.from_dir(
        SIMSED_DIR, weights=weights,
        ra=radec_sampler.ra, dec=radec_sampler.dec,
        redshift=redshift_func, distance=distance_func, t0=t0_func,
    )
    source_model._sampler_node.set_seed(seed_base + 9)
    source_model.add_effect(mw_extinction)
    print(f"[{time.time()-t_start:.1f}s] SIMSEDModel cargado ({len(source_model)} templates)")

    t_sim0 = time.time()
    lc = simulate_lightcurves(source_model, NGENTOT, survey_info=SurveyInfo(
        obstable=obs_table, passbands=passband_group, survey_name="LSST",
    ), rest_time_window_offset=(-30, 100), rng=np.random.default_rng(seed_base + 2))
    print(f"[{time.time()-t_start:.1f}s] simulacion terminada: {len(lc)} objetos, "
          f"{time.time()-t_sim0:.1f}s")

    print("columnas de una lightcurve de muestra:", list(lc.iloc[0]["lightcurve"].columns))

    rows = []
    for _, row in lc.iterrows():
        sub = row["lightcurve"]
        if sub is None or len(sub) == 0:
            continue
        r_band = sub[sub["filter"].astype(str) == "r"]
        if len(r_band) == 0 or "flux_perfect" not in r_band.columns:
            continue
        peak_flux_perfect = r_band["flux_perfect"].max()
        if peak_flux_perfect <= 0:
            continue
        MAG_AB_ZP_NJY = 8.9 + 2.5 * 9
        peak_mag_true = MAG_AB_ZP_NJY - 2.5 * np.log10(peak_flux_perfect)
        rows.append({"SNID": str(int(row["id"])), "z": row["z"], "PEAKMAG_r_true": peak_mag_true})

    out = pd.DataFrame(rows)
    out.to_parquet(HERE / "compare_brightness_truth_output.parquet", index=False)
    print(f"[{time.time()-t_start:.1f}s] {len(out)} objetos con PEAKMAG_r_true calculado (sin ruido), "
          f"guardado en compare_brightness_truth_output.parquet")
    print(out.describe())


if __name__ == "__main__":
    main()
