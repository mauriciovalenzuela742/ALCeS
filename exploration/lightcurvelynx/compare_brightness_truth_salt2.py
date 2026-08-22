"""
Fase 16 (Opcion 2 -- comparacion pointwise ruido->SNR->trigger) -- version
SALT2/SNIa de compare_brightness_truth.py (Fase 7). Extrae flux_perfect
(flujo NO ruidoso, ya calculado internamente por simulate_lightcurves(), ver
object_nested_dict["flux_perfect"] en lightcurvelynx/simulate.py) en vez del
minimo de FLUXCAL ruidoso -- mismo motivo que Fase 7 (SNANA PEAKMAG_r es una
magnitud de pico teorica/sin ruido, comparar contra un minimo ruidoso
introduce sesgo tipo Eddington).

Esto nunca se hizo para la clase SALT2/SNIa (solo para SNIa-91bg SIMSED en
Fase 7) -- run_snia_ddf_poc.py aplana directo a flux/fluxerr y descarta
flux_perfect, igual que el bug que Fase 7 encontro y corrigio para SIMSED.

Reconstruye el MISMO source_model real que run_snia_ddf_poc.py (mismos
parametros SALT2/DNDZ/extincion/cosmologia H0=70, incluida la dispersion
MWEBV real de Fase 10) pero captura flux_perfect en vez de descartarlo.

Uso (sbatch, no en login node -- carga SALT2 + simula 2000 objetos):
    python3 compare_brightness_truth_salt2.py
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sncosmo

from lightcurvelynx.astro_utils.mag_flux import mag2flux
from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.astro_utils.snia_utils import DistModFromRedshift, X0FromDistMod
from lightcurvelynx.effects.extinction import ExtinctionEffect
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.math_nodes.ra_dec_sampler import ObsTableRADECSampler
from lightcurvelynx.models.sncosmo_models import SncosmoWrapperModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
from lightcurvelynx.utils.extrapolate import LinearDecay, ZeroPadding

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402

from snana_params import (
    build_dndz_powerlaw2_cdf, make_dndz_sampler, make_bifurcated_normal_sampler,
    make_mwebv_ratio_scatter,
    SizeAwareFunctionNode,
)

HERE = Path(__file__).resolve().parent
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
SALT2_LOCAL_DIR = HERE / "salt2_h17_local"

NGENTOT_LC = 2000
SEED_BASE = 20260812  # mismo SEED_BASE que run_snia_ddf_poc.py -- misma poblacion exacta

GENRANGE_REDSHIFT = (0.011, 1.2)
SALT2C = dict(peak=-0.054, sigma_lo=0.043, sigma_hi=0.101, lo=-0.3, hi=0.5)
SALT2X1 = dict(peak=0.973, sigma_lo=1.472, sigma_hi=0.222, lo=-3.0, hi=2.0)
ALPHA, BETA = 0.14, 3.1
SIGMA_INT = 0.090
DNDZ_SEGMENTS = [(2.5e-5, 1.5, 0.0, 1.0), (9.7e-5, -0.5, 1.0, 3.0)]

DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
MW_RV = 3.1
GENSIGMA_MWEBV_RATIO = 0.16
PIXSIZE = 0.2


def snana_noise_columns(df_ddf: pd.DataFrame) -> pd.DataFrame:
    snana = format_obs(df_ddf, pixsize=PIXSIZE)
    sig_psf_arcsec = df_ddf["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    noise_area_arcsec2 = 4 * np.pi * sig_psf_arcsec ** 2
    out = df_ddf.copy()
    out["sky_bg_e"] = snana["SKYSIG"].to_numpy() ** 2
    out["psf_footprint"] = noise_area_arcsec2 / PIXSIZE ** 2
    out["zp"] = mag2flux(snana["ZPT"].to_numpy())
    return out


def main():
    seed_base = SEED_BASE
    t_start = time.time()

    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    df_ddf = snana_noise_columns(df_ddf)
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    print(f"[{time.time()-t_start:.1f}s] OpSim DDF: {len(df_ddf):,} obs")

    passband_group = PassbandGroup.from_preset(preset="LSST")
    print(f"[{time.time()-t_start:.1f}s] passbands cargados")

    local_src = sncosmo.SALT2Source(modeldir=str(SALT2_LOCAL_DIR), name="salt2-h17-local")
    print(f"[{time.time()-t_start:.1f}s] SALT2.WFIRST-H17 local cargado")

    z_grid, cdf = build_dndz_powerlaw2_cdf(
        segments=DNDZ_SEGMENTS, z_min=GENRANGE_REDSHIFT[0], z_max=GENRANGE_REDSHIFT[1],
    )
    redshift_func = SizeAwareFunctionNode(
        make_dndz_sampler(z_grid, cdf, seed=seed_base + 1), node_label="redshift"
    )
    c_func = SizeAwareFunctionNode(
        make_bifurcated_normal_sampler(**SALT2C, seed=seed_base + 2), node_label="c"
    )
    x1_func = SizeAwareFunctionNode(
        make_bifurcated_normal_sampler(**SALT2X1, seed=seed_base + 3), node_label="x1"
    )
    # Fase 34: Omega_m real de SNANA es 0.315 (OMEGA_MATTER_DEFAULT, sntools.h),
    # nunca sobreescrito en el .INPUT real -- 0.3 era un valor redondo asumido,
    # nunca verificado. Confirmado numericamente: ajustando Om0 contra el MU
    # real del .DUMP, el optimo es 0.3144 (residuo mediano cae de 0.017 a
    # 0.0007 mag) -- coincide con el default real de SNANA.
    distmod_func = DistModFromRedshift(redshift_func, H0=70.0, Omega_m=0.315)
    # Fase 20: -19.365 es el M_abs real que hace que X0FromDistMod coincida
    # exacto con SALT2x0calc() de SNANA -- ver run_snia_ddf_poc.py y NOTES.md
    # Fase 20 para la verificacion numerica completa (no cierra el residuo,
    # es una correccion de calibracion real, independiente de esa pregunta).
    m_abs_func = NumpyRandomFunc("normal", loc=-19.365, scale=SIGMA_INT, seed=seed_base + 4)
    x0_func = X0FromDistMod(
        distmod=distmod_func, x1=x1_func, c=c_func, alpha=ALPHA, beta=BETA, m_abs=m_abs_func,
    )
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=seed_base + 5, radius=0.0)
    radec_sampler.setters["selected_table_index"].dependency.set_seed(seed_base + 5)
    t0_func = NumpyRandomFunc(
        "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max()),
        seed=seed_base + 6,
    )

    _mwebv_scatter = make_mwebv_ratio_scatter(GENSIGMA_MWEBV_RATIO, seed=seed_base + 10)

    def _field_to_ebv(size=None, field=None, **_kwargs):
        arr = np.asarray(field)
        nominal = np.array([DDF_FIELD_EBV.get(f, 0.0) for f in arr.ravel()]).reshape(arr.shape)
        return _mwebv_scatter(nominal)

    ebv_func = SizeAwareFunctionNode(_field_to_ebv, node_label="ebv", field=radec_sampler.field)
    # Fase 24: OPT_MWCOLORLAW=99 real -> F99, no O94 (ver run_snia_ddf_poc.py / NOTES.md).
    mw_extinction = ExtinctionEffect(
        extinction_model="F99", ebv=ebv_func, r_v=MW_RV, frame="observer", backend="dust_extinction",
    )

    source = SncosmoWrapperModel(
        local_src, t0=t0_func, x0=x0_func, x1=x1_func, c=c_func,
        ra=radec_sampler.ra, dec=radec_sampler.dec, redshift=redshift_func,
        node_label="source", time_extrapolation=LinearDecay(50.0), wave_extrapolation=ZeroPadding(),
    )
    source.add_effect(mw_extinction)
    survey_info = SurveyInfo(obstable=obs_table, passbands=passband_group, survey_name="LSST")
    print(f"[{time.time()-t_start:.1f}s] modelo armado, simulando {NGENTOT_LC} objetos...")

    t_sim0 = time.time()
    lc = simulate_lightcurves(
        source, NGENTOT_LC, survey_info, rest_time_window_offset=(-30, 100),
        rng=np.random.default_rng(seed_base + 8),
    )
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
    out.to_parquet(HERE / "compare_brightness_truth_salt2_output.parquet", index=False)
    print(f"[{time.time()-t_start:.1f}s] {len(out)} objetos con PEAKMAG_r_true calculado (sin ruido), "
          f"guardado en compare_brightness_truth_salt2_output.parquet")
    print(out.describe())


if __name__ == "__main__":
    main()
