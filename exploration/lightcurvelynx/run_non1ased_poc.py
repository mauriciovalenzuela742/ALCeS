"""
Fase 6 -- primer PoC de LightCurveLynx para GENMODEL: NON1ASED (las 14
clases previas, Fase 0-5, son todas SIMSED o SALT2, ver NOTES.md). Reusa
exactamente el mismo patron ya validado de run_simsed_poc.py (H0=70 + ruido
real de SNANA, extincion MW real, SEARCHEFF real, QC de pipeline.postproc
sin modificar) -- lo unico que cambia es la construccion del source_model,
via non1ased.load_non1ased_model() en vez de SIMSEDModel.from_dir(), porque
los directorios NON1ASED reales no traen SED.INFO (confirmado via ssh
nlhpc, ver non1ased.py).

Primera clase: SNIa-91bg. De las 5 clases NON1ASED ya convertidas y
validadas del lado SNANA (NEXT_SESSION.md, 2026-08-06: SNIax, SNIa-91bg,
TDE, SLSN-I, KN-BULLA-BNS-M2COMP), es la unica candidata solida para un PoC
inicial: SNIax tiene 1001 templates (carga estimada en horas, ver
run_simsed_poc.sbatch); TDE_NON1ASED/SLSN-I_NON1ASED resultaron ser una
familia de template FISICAMENTE distinta (*-BBFIT) de la ya cubierta en
LCL via SIMSED (*-MOSFIT), asi que no sirven para un diagnostico
"mismos templates, distinta codificacion"; KN-BULLA-BNS-M2COMP dio 0/300
detecciones en su validacion SNANA -- objetivo demasiado incierto. SNIa-91bg
tiene solo 35 templates (los mismos archivos .SED que SIMSED.SNIa-91bg,
confirmado por diff de listado de directorio via ssh nlhpc) y detecciones
SNANA no triviales.

Nota real descubierta al preparar este PoC (no asumir el mismo rango que
la clase SIMSED.SNIa-91bg ya corrida en Fase 2B/4): el .INPUT real
NON1ASED (elastic/model_config/SIMGEN_INCLUDE_SNIa-91bg_NON1ASED.INPUT)
usa GENRANGE_REDSHIFT 0.011-1.2, DISTINTO del 0.011-0.6 que CLASS_CONFIGS
de run_simsed_poc.py usa para SNIa-91bg. Investigado: existen dos
generaciones de config SIMSED.SNIa-91bg en NLHPC --
`run_SNANA/model_config/` (0.011-0.6, la que uso el PoC SIMSED ya corrido)
y `run_SNANA/elastic/model_config/` (0.011-1.2, la que se convirtio a
NON1ASED) -- mismos templates fisicos, .INPUT de campana distinto. Este
PoC usa el rango real de SU PROPIO .INPUT NON1ASED (0.011-1.2), asi que su
ratio vs SNANA es valido comparado contra la corrida SNANA real de
SNIa-91bg_NON1ASED (build/full_v5.3_10yrs/postproc/SNIa-91bg_NON1ASED_*) --
pero NO es directamente comparable al ratio ya publicado de la clase
SIMSED.SNIa-91bg (rango de z distinto), por lo que el diagnostico "misma
fisica, distinta codificacion" limpio requeriria ademas re-correr SIMSED
con el rango elastic (0.011-1.2) -- no se hizo aqui, queda como trabajo
futuro documentado, no una comparacion invalida que se paso por alto.

Uso (dentro de un job sbatch, nunca en el login node):
    python3 run_non1ased_poc.py <clave_clase>
    (claves validas: ver CLASS_CONFIGS)
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
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.math_nodes.ra_dec_sampler import ObsTableRADECSampler
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo

from non1ased import load_non1ased_model
from snana_params import build_dndz_powerlaw2_cdf, make_dndz_sampler, SizeAwareFunctionNode, ClippedExtinctionEffect
from searcheff import (
    parse_searcheff_pipeline, parse_pipeline_logic, apply_detection_efficiency, object_level_detected,
)

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
from pipeline.simlib.formatobs import format_obs  # noqa: E402
from lightcurvelynx.astro_utils.mag_flux import mag2flux  # noqa: E402

HERE = Path(__file__).resolve().parent
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
SEARCHEFF_PIPELINE_FILE = SNANA_HOME / "run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT"
SEARCHEFF_LOGIC_FILE = SNANA_HOME / "run_SNANA/LSST_PIPELINE_LOGIC.DAT"
PIXSIZE = 0.2
NGENTOT_LC = 2000  # igual que la mayoria de las clases SIMSED (pipeline/models.yaml: ngen_ddf)
SEED_BASE = 20260814

DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
MW_RV = 3.1

# --- config por clase, parametros reales del .INPUT NON1ASED real ---
CLASS_CONFIGS = {
    "SNIa-91bg": dict(
        non1ased_dir=SNANA_HOME / "run_SNANA/elastic/model_libs_updates/NON1ASED.SNIa-91bg",
        input_path=SNANA_HOME / "run_SNANA/elastic/model_config/SIMGEN_INCLUDE_SNIa-91bg_NON1ASED.INPUT",
        genrange_redshift=(0.011, 1.2),
        dndz=("powerlaw", [(3.0e-6, 1.5, 0.011, 1.2)]),
        sntype=13,
        # sin extincion de host en el .INPUT real (mismo que la variante
        # SIMSED) -- no se agrega ClippedExtinctionEffect de host aqui.
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


def main(class_key: str, ngentot_override: int | None = None, seed_index: int = 0):
    cfg = CLASS_CONFIGS[class_key]
    ngentot = ngentot_override if ngentot_override is not None else cfg.get("ngentot_lc", NGENTOT_LC)
    seed_base = SEED_BASE + seed_index * 1_000_000
    suffix = f"_seed{seed_index}" if seed_index else ""
    out_dir = HERE / f"poc_output_non1ased_{class_key.lower().replace('-', '')}{suffix}"
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

    z_min, z_max = cfg["genrange_redshift"]
    dndz_kind, dndz_params = cfg["dndz"]
    if dndz_kind == "powerlaw":
        z_grid, cdf = build_dndz_powerlaw2_cdf(segments=dndz_params, z_min=z_min, z_max=z_max)
    else:
        raise ValueError(f"dndz_kind desconocido: {dndz_kind}")
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=seed_base + 1), node_label="redshift")
    # radius=0.0 explicito (mismo fix de Fase 5 que run_simsed_poc.py --
    # ver comentario alli): campos DDF son pointings fijos, evita el
    # jitter sub-FOV sin seed de ObsTableRADECSampler.compute().
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=seed_base + 5, radius=0.0)
    # mismo segundo fix de Fase 5: TableSampler.__init__ crea su propio
    # muestreador de indice de fila sin heredar el seed del constructor.
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

    source_model = load_non1ased_model(
        cfg["non1ased_dir"], cfg["input_path"],
        ra=radec_sampler.ra, dec=radec_sampler.dec,
        redshift=redshift_func, distance=distance_func, t0=t0_func,
    )
    # mismo bug de Fase 4 que SIMSEDModel: MultiSEDTemplateModel.__init__
    # nunca pasa seed a su GivenValueSampler interno -- fijarlo aqui para
    # que la seleccion de template sea reproducible.
    source_model._sampler_node.set_seed(seed_base + 9)
    source_model.add_effect(mw_extinction)

    print(f"[{time.time()-t_start:.1f}s] NON1ASED cargado ({len(source_model)} templates, "
          f"pesos reales de NON1A_KEYS)")

    t_sim0 = time.time()
    lc = simulate_lightcurves(source_model, ngentot, survey_info=SurveyInfo(
        obstable=obs_table, passbands=passband_group, survey_name="LSST",
    ), rest_time_window_offset=(-30, 100), rng=np.random.default_rng(seed_base + 2))
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
    detected_mask = apply_detection_efficiency(phot_df, band_curves, seed=seed_base + 7)
    phot_df["PHOTFLAG"] = np.where(detected_mask, 4096, 0)
    detected_snids = object_level_detected(phot_df, min_epochs=min_epochs)
    print(f"[{time.time()-t_start:.1f}s] SEARCHEFF aplicado: {len(detected_snids)}/{len(head_df)} "
          f"objetos detectados (>= {min_epochs} epocas reales, agrupadas)")

    all_ids = lc["id"].astype(int).astype(str)
    dump_df = pd.DataFrame({"CID": all_ids, "ZHELIO": lc["z"].to_numpy(), "ZCMB": lc["z"].to_numpy()})
    head_df_detected = head_df[head_df["SNID"].isin(detected_snids)].reset_index(drop=True)

    head_df["DETECTED"] = head_df["SNID"].isin(detected_snids)
    head_df.to_parquet(out_dir / "head_df.parquet", index=False)
    phot_df.to_parquet(out_dir / "phot_df.parquet", index=False)
    print(f"[{time.time()-t_start:.1f}s] tablas persistidas: head_df.parquet "
          f"({len(head_df)} filas), phot_df.parquet ({len(phot_df)} filas)")

    (out_dir / "summary.json").write_text(json.dumps({
        "class_key": class_key,
        "model_class": "NON1ASED",
        "seed_index": seed_index,
        "ngentot_lc": ngentot,
        "n_with_obs": len(head_df),
        "n_detected": len(detected_snids),
        "n_total_dump": len(dump_df),
        "sim_wall_time_s": sim_wall_time,
        "detection_efficiency_pct": 100.0 * len(detected_snids) / ngentot,
        "snr_median": float(snr_sim.median()),
        "snr_p90": float(snr_sim.quantile(0.9)),
    }, indent=2))

    sys.path.insert(0, "/home/mvalenzuela/AUTOSIM")
    from pipeline.postproc import qc
    qc_dir = out_dir / "qc"
    if len(head_df_detected) > 0:
        paths = qc.run_all_qc(head_df_detected, phot_df, qc_dir, f"LightCurveLynx_{class_key}_NON1ASED_DDF_poc", dump_df=dump_df)
        print(f"[{time.time()-t_start:.1f}s] QC generado: {list(paths.keys())}")
    else:
        print(f"[{time.time()-t_start:.1f}s] ! 0 objetos detectados, QC omitido")
    print(f"[{time.time()-t_start:.1f}s] TOTAL")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in CLASS_CONFIGS:
        print(f"uso: python3 run_non1ased_poc.py <clase> [seed_index]  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    _seed_index = int(sys.argv[2]) if len(sys.argv) == 3 else 0
    main(sys.argv[1], seed_index=_seed_index)
