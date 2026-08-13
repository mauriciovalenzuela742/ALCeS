"""
Fase 2 parte B -- primer PoC del wrapper SIMSED, empezando acotado con
SNIa-91bg_DDF (la mas simple de las 11 clases SIMSED del catalogo: 35
templates en una grilla 7x5 de stretch x color, NPAR=2 -- ver NOTES.md
Fase 2 parte B).

Hallazgo clave que cambia el plan original: LightCurveLynx YA trae un
lector SIMSED nativo (`lightcurvelynx.models.sed_template_model.SIMSEDModel`,
via `.from_dir()`) que Fase 0 no encontro -- parsea SED.INFO (YAML), carga
todos los templates (maneja .gz), aplica FLUX_SCALE, y selecciona un
template por objeto via GivenValueSampler(weights=...) internamente. No
hace falta escribir un wrapper propio de lectura -- solo calcular los
pesos correctos por template (bivariada normal correlacionada
stretch/color, igual que SIMSED_REDCOR de SNANA) y pasarlos a from_dir().

Mismo patron que run_snia_ddf_poc.py (Fase 1) en todo lo demas: DDF real,
H0=70 + ruido real de SNANA inyectado (Fase 2 parte A, ya cerrado en parte),
SEARCHEFF real, reuso de pipeline.postproc.qc sin modificar.

Parametros reales de SIMGEN_INCLUDE_SNIa-91bg.INPUT:
    DNDZ: POWERLAW 3.0E-6 1.5              (un solo tramo, no POWERLAW2)
    GENRANGE_REDSHIFT: 0.011 0.6
    GENPEAK_stretch=0.975  GENSIGMA_stretch=0.096 0.096  (simetrica)
    GENPEAK_color=0.557    GENSIGMA_color=0.175 0.175    (simetrica)
    SIMSED_REDCOR(stretch,color) = -0.656

Uso (dentro de un job sbatch, nunca en el login node):
    python3 run_simsed_91bg_ddf_poc.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.effects.extinction import ExtinctionEffect
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.math_nodes.ra_dec_sampler import ObsTableRADECSampler
from lightcurvelynx.models.sed_template_model import SIMSEDModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
from lightcurvelynx.utils.extrapolate import LinearDecay, ZeroPadding

from snana_params import build_dndz_powerlaw2_cdf, make_dndz_sampler, SizeAwareFunctionNode
from searcheff import parse_searcheff_pipeline, parse_pipeline_logic, apply_detection_efficiency

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402
from lightcurvelynx.astro_utils.mag_flux import mag2flux  # noqa: E402

HERE = Path(__file__).resolve().parent
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
SIMSED_DIR = HERE / "simsed_91bg_local"  # ver setup_simsed_91bg_local.py (fix de SED.INFO)
SEARCHEFF_PIPELINE_FILE = SNANA_HOME / "run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT"
SEARCHEFF_LOGIC_FILE = SNANA_HOME / "run_SNANA/LSST_PIPELINE_LOGIC.DAT"
OUT_DIR = HERE / "poc_output_91bg"
PIXSIZE = 0.2

NGENTOT_LC = 2000  # igual que SNANA DDF (pipeline/models.yaml: ngen_ddf)
SEED_BASE = 20260813

# --- parametros reales de SIMGEN_INCLUDE_SNIa-91bg.INPUT ---
GENRANGE_REDSHIFT = (0.011, 0.6)
DNDZ_SEGMENTS = [(3.0e-6, 1.5, GENRANGE_REDSHIFT[0], GENRANGE_REDSHIFT[1])]  # POWERLAW simple
STRETCH_PEAK, STRETCH_SIGMA = 0.975, 0.096
COLOR_PEAK, COLOR_SIGMA = 0.557, 0.175
REDCOR = -0.656

DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
MW_RV = 3.1


def snana_noise_columns(df_ddf: pd.DataFrame) -> pd.DataFrame:
    """Misma funcion que run_snia_ddf_poc.py -- deriva zp/psf_footprint/
    sky_bg_e con la formula real de SNANA (Fase 2 parte A)."""
    snana = format_obs(df_ddf, pixsize=PIXSIZE)
    sig_psf_arcsec = df_ddf["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    noise_area_arcsec2 = 4 * np.pi * sig_psf_arcsec ** 2
    out = df_ddf.copy()
    out["sky_bg_e"] = snana["SKYSIG"].to_numpy() ** 2
    out["psf_footprint"] = noise_area_arcsec2 / PIXSIZE ** 2
    out["zp"] = mag2flux(snana["ZPT"].to_numpy())
    return out


def template_weights_from_redcor(stretch: np.ndarray, color: np.ndarray) -> np.ndarray:
    """Peso de cada template = PDF de la bivariada normal correlacionada
    definida por GENPEAK/GENSIGMA/SIMSED_REDCOR de SNANA, evaluada en el
    (stretch, color) real de cada template -- replica la logica de pesado
    de snlc_sim.exe para SIMSED_REDCOR en vez de un peso uniforme 1/N."""
    cov_ss = STRETCH_SIGMA ** 2
    cov_cc = COLOR_SIGMA ** 2
    cov_sc = REDCOR * STRETCH_SIGMA * COLOR_SIGMA
    cov = np.array([[cov_ss, cov_sc], [cov_sc, cov_cc]])
    inv_cov = np.linalg.inv(cov)
    d = np.stack([stretch - STRETCH_PEAK, color - COLOR_PEAK], axis=1)
    exponent = -0.5 * np.einsum("ni,ij,nj->n", d, inv_cov, d)
    weights = np.exp(exponent)  # normalizacion global no importa para GivenValueSampler
    return weights


def main():
    t_start = time.time()
    OUT_DIR.mkdir(exist_ok=True)

    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    df_ddf = snana_noise_columns(df_ddf)
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    print(f"[{time.time()-t_start:.1f}s] OpSim DDF: {len(df_ddf):,} obs, "
          f"ruido real de SNANA inyectado (Fase 2 parte A)")

    passband_group = PassbandGroup.from_preset(preset="LSST")
    print(f"[{time.time()-t_start:.1f}s] passbands cargados")

    # --- SIMSED nativo: lee SED.INFO + templates, calcula pesos reales por REDCOR ---
    from lightcurvelynx.models.sed_template_model import SIMSEDModel as _SM
    file_names, _ = _SM._read_simsed_info_file(SIMSED_DIR)
    # PARNAMES: stretch color -- mismo orden que SED.INFO, parseado directo
    sed_info_text = (SIMSED_DIR / "SED.INFO").read_text()
    param_rows = [
        line.split()[2:] for line in sed_info_text.splitlines()
        if line.strip().upper().startswith("SED:")
    ]
    template_stretch = np.array([float(r[0]) for r in param_rows])
    template_color = np.array([float(r[1]) for r in param_rows])
    weights = template_weights_from_redcor(template_stretch, template_color)
    print(f"[{time.time()-t_start:.1f}s] {len(file_names)} templates SIMSED, "
          f"pesos via SIMSED_REDCOR real (min={weights.min():.4f} max={weights.max():.4f})")

    # -- samplers, construidos ANTES del modelo: SIMSEDModel valida sus
    # parametros requeridos (distance, etc.) en el constructor, no acepta
    # agregarlos despues via add_parameter() como si fuera opcional. --
    z_grid, cdf = build_dndz_powerlaw2_cdf(
        segments=DNDZ_SEGMENTS, z_min=GENRANGE_REDSHIFT[0], z_max=GENRANGE_REDSHIFT[1],
    )
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=SEED_BASE + 1), node_label="redshift")
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=SEED_BASE + 5)
    t0_func = NumpyRandomFunc(
        "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max()), seed=SEED_BASE + 6,
    )

    def _luminosity_distance_pc(size=None, redshift=None, **_kwargs):
        # SIMSEDModel.compute_sed() usa "distance" (pc), no "redshift"
        # directamente -- convertir con la misma cosmologia H0=70/Om=0.3
        # de Fase 2 parte A.
        from astropy.cosmology import FlatLambdaCDM
        import astropy.units as u
        cosmo = FlatLambdaCDM(H0=70.0, Om0=0.3)
        z = np.asarray(redshift)
        return cosmo.luminosity_distance(z).to(u.pc).value

    distance_func = SizeAwareFunctionNode(
        _luminosity_distance_pc, node_label="distance", redshift=redshift_func,
    )

    def _field_to_ebv(size=None, field=None, **_kwargs):
        arr = np.asarray(field)
        return np.array([DDF_FIELD_EBV.get(f, 0.0) for f in arr.ravel()]).reshape(arr.shape)

    ebv_func = SizeAwareFunctionNode(_field_to_ebv, node_label="ebv", field=radec_sampler.field)
    mw_extinction = ExtinctionEffect(
        extinction_model="O94", ebv=ebv_func, r_v=MW_RV, frame="observer", backend="dust_extinction",
    )

    source_model = SIMSEDModel.from_dir(
        SIMSED_DIR, weights=weights,
        ra=radec_sampler.ra, dec=radec_sampler.dec,
        redshift=redshift_func, distance=distance_func, t0=t0_func,
    )
    source_model.add_effect(mw_extinction)
    print(f"[{time.time()-t_start:.1f}s] SIMSEDModel cargado ({len(source_model)} templates)")

    survey_info = SurveyInfo(obstable=obs_table, passbands=passband_group, survey_name="LSST")
    print(f"[{time.time()-t_start:.1f}s] modelo armado, simulando {NGENTOT_LC} objetos...")

    t_sim0 = time.time()
    lc = simulate_lightcurves(
        source_model, NGENTOT_LC, survey_info, rest_time_window_offset=(-30, 100),
    )
    sim_wall_time = time.time() - t_sim0
    print(f"[{time.time()-t_start:.1f}s] simulacion terminada: {len(lc)} objetos, "
          f"{sim_wall_time:.1f}s ({sim_wall_time/len(lc)*1000:.2f} ms/objeto)")

    # -- aplanar a phot_df + head_df (mismo patron que run_snia_ddf_poc.py) --
    head_rows, phot_rows = [], []
    for _, row in lc.iterrows():
        sub = row["lightcurve"]
        if sub is None or len(sub) == 0:
            continue
        snid = str(int(row["id"]))
        head_rows.append({
            "SNID": snid, "SNTYPE": 13, "RA": row["ra"], "DEC": row["dec"],
            "REDSHIFT_HELIO": row["z"], "PEAKMJD": row["t0"], "NOBS": len(sub),
        })
        for _, obs in sub.iterrows():
            flt = str(obs["filter"])
            flt = "Y" if flt == "y" else flt
            phot_rows.append({
                "SNID": snid, "MJD": obs["mjd"], "FLT": flt,
                "FLUXCAL": obs["flux"], "FLUXCALERR": obs["fluxerr"],
            })

    head_df = pd.DataFrame(head_rows)
    phot_df = pd.DataFrame(phot_rows)
    MAG_AB_ZP_NJY = 8.9 + 2.5 * 9
    positive = phot_df["FLUXCAL"] > 0
    phot_df["MAG"] = np.where(positive, MAG_AB_ZP_NJY - 2.5 * np.log10(phot_df["FLUXCAL"].where(positive)), np.nan)
    print(f"[{time.time()-t_start:.1f}s] aplanado: {len(head_df)} objetos con obs, "
          f"{len(phot_df)} filas de fotometria")

    snr_sim = (phot_df["FLUXCAL"] / phot_df["FLUXCALERR"]).abs()
    print(f"[{time.time()-t_start:.1f}s] SNR simulado (todas las obs): "
          f"mediana={snr_sim.median():.3f}, p90={snr_sim.quantile(0.9):.3f}")

    band_curves = parse_searcheff_pipeline(SEARCHEFF_PIPELINE_FILE)
    min_epochs = parse_pipeline_logic(SEARCHEFF_LOGIC_FILE)
    detected_mask = apply_detection_efficiency(phot_df, band_curves, seed=SEED_BASE + 7)
    phot_df["PHOTFLAG"] = np.where(detected_mask, 4096, 0)
    counts = phot_df[phot_df["PHOTFLAG"] == 4096].groupby("SNID").size()
    detected_snids = set(counts[counts >= min_epochs].index)
    print(f"[{time.time()-t_start:.1f}s] SEARCHEFF aplicado: {len(detected_snids)}/{len(head_df)} "
          f"objetos detectados (>= {min_epochs} epocas)")

    all_ids = lc["id"].astype(int).astype(str)
    dump_df = pd.DataFrame({
        "CID": all_ids, "ZHELIO": lc["z"].to_numpy(), "ZCMB": lc["z"].to_numpy(),
    })
    head_df_detected = head_df[head_df["SNID"].isin(detected_snids)].reset_index(drop=True)

    (OUT_DIR / "summary.json").write_text(json.dumps({
        "ngentot_lc": NGENTOT_LC,
        "n_with_obs": len(head_df),
        "n_detected": len(detected_snids),
        "n_total_dump": len(dump_df),
        "sim_wall_time_s": sim_wall_time,
        "detection_efficiency_pct": 100.0 * len(detected_snids) / NGENTOT_LC,
        "snr_median": float(snr_sim.median()),
        "snr_p90": float(snr_sim.quantile(0.9)),
    }, indent=2))

    sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
    from pipeline.postproc import qc
    qc_dir = OUT_DIR / "qc"
    paths = qc.run_all_qc(head_df_detected, phot_df, qc_dir, "LightCurveLynx_SNIa91bg_DDF_poc", dump_df=dump_df)
    print(f"[{time.time()-t_start:.1f}s] QC generado: {list(paths.keys())}")
    print(f"[{time.time()-t_start:.1f}s] TOTAL")


if __name__ == "__main__":
    main()
