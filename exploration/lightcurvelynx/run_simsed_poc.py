"""
Fase 2 parte B -- version generalizada de run_simsed_91bg_ddf_poc.py que
corre cualquiera de las clases SIMSED del catalogo via una config por
clase, en vez de un script separado por clase. Reusa exactamente el mismo
patron ya validado (H0=70 + ruido real de SNANA inyectado desde Fase 2
parte A, extincion MW real, SEARCHEFF real, QC de pipeline.postproc sin
modificar).

Clases nuevas en esta ronda (elegidas por complejidad variada, ver
NOTES.md Fase 2 parte B): KN-K17 (peso uniforme, DNDZ POWERLAW sin
dependencia de z, redshift bajo), CaRT/CART-MOSFIT (peso uniforme, DNDZ
MD14), SLSN-I/SLSN-I-MOSFIT (peso uniforme, DNDZ MD14, rango de redshift
mucho mas amplio 0.02-9.7 -- prueba de escala/extrapolacion).

Simplificacion deliberada y documentada (no un descuido): estas 3 clases
declaran extincion de galaxia anfitriona (WV07 AV/RV o similar,
GENAV_WV07/GENRANGE_AV/GENPEAK_RV en su .INPUT real) que NO se implementa
aqui. Se investigo el codigo fuente real de SNANA
(~/github/SNANA_src/src/sntools_genExpHalfGauss.c) y el propio codigo trae
un historial de bugs documentados en esa formula ("WV07 AV flag was never
refactored to use this function, so this might be a harmless bug" --
comentario real de Dic 2023 en el codigo), lo que hace riesgoso
reimplementarla de memoria sin una referencia mas solida. Se omite (AV=0)
en vez de adivinar mal la formula -- mismo criterio que la aproximacion de
G10 en Fase 1. Queda como brecha adicional documentada, no una que se
descubrio por accidente.

Uso (dentro de un job sbatch, nunca en el login node):
    python3 run_simsed_poc.py <clave_clase>
    (claves validas: KN-K17, CaRT, SLSN-I)
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

from snana_params import build_dndz_powerlaw2_cdf, build_dndz_md14_cdf, make_dndz_sampler, SizeAwareFunctionNode
from searcheff import parse_searcheff_pipeline, parse_pipeline_logic, apply_detection_efficiency

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402
from lightcurvelynx.astro_utils.mag_flux import mag2flux  # noqa: E402

HERE = Path(__file__).resolve().parent
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
SEARCHEFF_PIPELINE_FILE = SNANA_HOME / "run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT"
SEARCHEFF_LOGIC_FILE = SNANA_HOME / "run_SNANA/LSST_PIPELINE_LOGIC.DAT"
PIXSIZE = 0.2
NGENTOT_LC = 2000  # igual para las 3 clases (pipeline/models.yaml: ngen_ddf)
SEED_BASE = 20260813

DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
MW_RV = 3.1

# --- config por clase, parametros reales de cada SIMGEN_INCLUDE_*.INPUT ---
CLASS_CONFIGS = {
    "KN-K17": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.KN-K17",
        genrange_redshift=(0.011, 0.28),
        dndz=("powerlaw", [(320e-9, 0.0, 0.011, 0.28)]),
        sntype=51,
    ),
    "CaRT": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.CART-MOSFIT",
        genrange_redshift=(0.012, 1.4),
        dndz=("md14", 2.3e-6),
        sntype=87,
    ),
    "SLSN-I": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SLSN-I-MOSFIT",
        genrange_redshift=(0.02, 9.7),
        dndz=("md14", 2.0e-8),
        sntype=40,
    ),
}


def snana_noise_columns(df_ddf: pd.DataFrame) -> pd.DataFrame:
    snana = format_obs(df_ddf, pixsize=PIXSIZE)
    sig_psf_arcsec = df_ddf["seeingFwhmEff"].to_numpy() / (2 * np.sqrt(2 * np.log(2)))
    noise_area_arcsec2 = 4 * np.pi * sig_psf_arcsec ** 2
    out = df_ddf.copy()
    out["sky_bg_e"] = snana["SKYSIG"].to_numpy() ** 2
    out["psf_footprint"] = noise_area_arcsec2 / PIXSIZE ** 2
    out["zp"] = mag2flux(snana["ZPT"].to_numpy())
    return out


def main(class_key: str):
    cfg = CLASS_CONFIGS[class_key]
    out_dir = HERE / f"poc_output_{class_key.lower().replace('-', '')}"
    out_dir.mkdir(exist_ok=True)
    t_start = time.time()

    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    df_ddf = snana_noise_columns(df_ddf)
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    print(f"[{time.time()-t_start:.1f}s] [{class_key}] OpSim DDF: {len(df_ddf):,} obs, "
          f"ruido real de SNANA inyectado")

    passband_group = PassbandGroup.from_preset(preset="LSST")
    print(f"[{time.time()-t_start:.1f}s] passbands cargados")

    simsed_dir = cfg["simsed_dir"]
    file_names, _ = SIMSEDModel._read_simsed_info_file(simsed_dir)
    # peso uniforme (SIMSED_GRIDONLY en el .INPUT real de las 3 clases) --
    # None hace que MultiSEDTemplateModel pese todos los templates igual.
    weights = None
    print(f"[{time.time()-t_start:.1f}s] {len(file_names)} templates SIMSED "
          f"(peso uniforme, SIMSED_GRIDONLY)")

    z_min, z_max = cfg["genrange_redshift"]
    dndz_kind, dndz_params = cfg["dndz"]
    if dndz_kind == "powerlaw":
        z_grid, cdf = build_dndz_powerlaw2_cdf(segments=dndz_params, z_min=z_min, z_max=z_max)
    else:
        z_grid, cdf = build_dndz_md14_cdf(rate0=dndz_params, z_min=z_min, z_max=z_max)
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=SEED_BASE + 1), node_label="redshift")
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=SEED_BASE + 5)
    t0_func = NumpyRandomFunc(
        "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max()), seed=SEED_BASE + 6,
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
    mw_extinction = ExtinctionEffect(
        extinction_model="O94", ebv=ebv_func, r_v=MW_RV, frame="observer", backend="dust_extinction",
    )

    source_model = SIMSEDModel.from_dir(
        simsed_dir, weights=weights,
        ra=radec_sampler.ra, dec=radec_sampler.dec,
        redshift=redshift_func, distance=distance_func, t0=t0_func,
    )
    source_model.add_effect(mw_extinction)
    print(f"[{time.time()-t_start:.1f}s] SIMSEDModel cargado ({len(source_model)} templates)")

    t_sim0 = time.time()
    lc = simulate_lightcurves(source_model, NGENTOT_LC, survey_info=SurveyInfo(
        obstable=obs_table, passbands=passband_group, survey_name="LSST",
    ), rest_time_window_offset=(-30, 100))
    sim_wall_time = time.time() - t_sim0
    print(f"[{time.time()-t_start:.1f}s] simulacion terminada: {len(lc)} objetos, "
          f"{sim_wall_time:.1f}s ({sim_wall_time/max(len(lc),1)*1000:.2f} ms/objeto)")

    head_rows, phot_rows = [], []
    for _, row in lc.iterrows():
        sub = row["lightcurve"]
        if sub is None or len(sub) == 0:
            continue
        snid = str(int(row["id"]))
        head_rows.append({
            "SNID": snid, "SNTYPE": cfg["sntype"], "RA": row["ra"], "DEC": row["dec"],
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
    dump_df = pd.DataFrame({"CID": all_ids, "ZHELIO": lc["z"].to_numpy(), "ZCMB": lc["z"].to_numpy()})
    head_df_detected = head_df[head_df["SNID"].isin(detected_snids)].reset_index(drop=True)

    (out_dir / "summary.json").write_text(json.dumps({
        "class_key": class_key,
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
    qc_dir = out_dir / "qc"
    if len(head_df_detected) > 0:
        paths = qc.run_all_qc(head_df_detected, phot_df, qc_dir, f"LightCurveLynx_{class_key}_DDF_poc", dump_df=dump_df)
        print(f"[{time.time()-t_start:.1f}s] QC generado: {list(paths.keys())}")
    else:
        print(f"[{time.time()-t_start:.1f}s] ! 0 objetos detectados, QC omitido")
    print(f"[{time.time()-t_start:.1f}s] TOTAL")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CLASS_CONFIGS:
        print(f"uso: python3 run_simsed_poc.py <clase>  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    main(sys.argv[1])
