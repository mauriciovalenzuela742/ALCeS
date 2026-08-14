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

Ronda 2 (ver NOTES.md Fase 2 parte B, continuacion 2): SNIax, TDE-MOSFIT,
SNII-NMF. A diferencia de la ronda 1, aqui SI se implementa extincion de
host cuando el .INPUT real declara el modelo exponencial puro
(`GENTAU_AV`, sin componente WV07/Gaussiana) -- se encontro la formula
real en el codigo fuente de SNANA (snlc_sim.c, funciones
`SFRfun_MD14`/`INDEX_RATEMODEL_CCS15`/`INDEX_RATEMODEL_TDE`) para los
modelos de tasa CC_S15/TDE tambien, que en la ronda 1 se habian evitado
por parecer "nombres propios" sin formula obvia -- resultaron ser
formulas simples y bien documentadas una vez revisado el codigo real, no
las supuestas complejas de PISN_PLK12 (esa sigue sin implementarse, no
se encontro razon para reconsiderarla en esta ronda).

Uso (dentro de un job sbatch, nunca en el login node):
    python3 run_simsed_poc.py <clave_clase>
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
from lightcurvelynx.models.sed_template_model import SIMSEDModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
from lightcurvelynx.utils.extrapolate import LinearDecay, ZeroPadding

from snana_params import (
    build_dndz_powerlaw2_cdf, build_dndz_md14_cdf, build_dndz_ccs15_cdf, build_dndz_tde_cdf,
    build_dndz_pisn_cdf, make_dndz_sampler, make_exp_av_sampler, make_exp_halfgauss_av_sampler,
    make_wv07_av_sampler, make_correlated_normal_weights, SizeAwareFunctionNode, ClippedExtinctionEffect,
)
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
NGENTOT_LC = 2000  # igual para las 3 clases (pipeline/models.yaml: ngen_ddf)
SEED_BASE = 20260813

DDF_FIELD_EBV = {
    "cosmos": 0.0182, "ecdfs": 0.0084, "edfs_a": 0.0062,
    "edfs_b": 0.0152, "elaiss1": 0.0080, "xmm_lss": 0.0251,
}
MW_RV = 3.1

# --- config por clase, parametros reales de cada SIMGEN_INCLUDE_*.INPUT ---
CLASS_CONFIGS = {
    # Fase 3: modelo de host extinction real ESSENCE-WV07 (Wood-Vasey+2007),
    # ver make_wv07_av_sampler() en snana_params.py -- reemplaza la omision
    # (AV=0) de las rondas 1-4 de Fase 2B. GENRANGE_AV=0-3 real en las 9
    # clases que lo declaran; KN-K17/KN-BULLA19 son las 2 unicas con
    # WV07_REWGT_EXPAV=0.5 (confirmado en su .INPUT real), las demas 7 no
    # lo declaran (rewgt_expav=None -> AEXP sin modificar).
    # Fase 4: SNIa-91bg migrada aqui desde run_simsed_91bg_ddf_poc.py (Fase 2B
    # ronda 1, script historico dedicado) para reusar el fix del trigger de
    # SEARCHEFF (ver NOTES.md) sin duplicar logica -- mismos parametros reales
    # de SIMGEN_INCLUDE_SNIa-91bg.INPUT, sin cambios.
    "SNIa-91bg": dict(
        simsed_dir=HERE / "simsed_91bg_local",
        genrange_redshift=(0.011, 0.6),
        dndz=("powerlaw", [(3.0e-6, 1.5, 0.011, 0.6)]),
        sntype=13,
        redcor_params=dict(
            peaks=dict(stretch=0.975, color=0.557),
            sigmas=dict(stretch=0.096, color=0.175),
            redcor={("stretch", "color"): -0.656},
        ),
    ),
    # Fase 6: mismos 35 templates fisicos que "SNIa-91bg" de arriba
    # (simsed_91bg_local -- confirmado por diff de listado de directorio
    # que run_SNANA/elastic/model_libs_updates/SIMSED.SNIa-91bg/ trae los
    # mismos archivos .SED que plasticc_models/SIMSED.SNIa-91bg/, mas
    # NON1A.LIST/SED.BINARY), pero con GENRANGE_REDSHIFT del .INPUT real
    # "elastic" (0.011-1.2, run_SNANA/elastic/model_config/
    # SIMGEN_INCLUDE_SNIa-91bg.INPUT) -- el mismo .INPUT del que se
    # convirtio SNIa-91bg_NON1ASED. No hay corrida SNANA de este .INPUT
    # SIMSED-elastic en la campana real (solo se uso como fuente para la
    # conversion a NON1ASED) -- esta clase no tiene ratio propio vs SNANA,
    # es solo para comparar LCL-SIMSED vs LCL-NON1ASED al mismo rango de z
    # y aislar si la codificacion del modelo (no la fisica ni el rango)
    # afecta el resultado (ver run_non1ased_poc.py).
    "SNIa-91bg-elastic": dict(
        simsed_dir=HERE / "simsed_91bg_local",
        genrange_redshift=(0.011, 1.2),
        dndz=("powerlaw", [(3.0e-6, 1.5, 0.011, 1.2)]),
        sntype=13,
        redcor_params=dict(
            peaks=dict(stretch=0.975, color=0.557),
            sigmas=dict(stretch=0.096, color=0.175),
            redcor={("stretch", "color"): -0.656},
        ),
    ),
    "KN-K17": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.KN-K17",
        genrange_redshift=(0.011, 0.28),
        dndz=("powerlaw", [(320e-9, 0.0, 0.011, 0.28)]),
        sntype=51,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=0.5, r_v=3.1),
    ),
    "CaRT": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.CART-MOSFIT",
        genrange_redshift=(0.012, 1.4),
        dndz=("md14", 2.3e-6),
        sntype=87,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    "SLSN-I": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SLSN-I-MOSFIT",
        genrange_redshift=(0.02, 9.7),
        dndz=("md14", 2.0e-8),
        sntype=40,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    "SNIax": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SNIax",
        genrange_redshift=(0.011, 0.7),
        dndz=("md14", 6.0e-6),
        sntype=12,
        # Fase 2B ronda 3: el .INPUT real de SNIax declara ADEMAS de
        # GENTAU_AV=1.7 los parametros GENSIG_AV=0.6/GENRATIO_AV0=4.0 --
        # NO es pura exponencial (la ronda 2 lo trato como tal por error,
        # sin leer esas dos lineas). Es la mezcla exponencial+semi-Gaussiana
        # de make_exp_halfgauss_av_sampler(), via GENPROFILE_AV en
        # snlc_sim.c::gen_AV() -- un camino de codigo real y distinto del
        # flag GENAV_WV07 (ese SI sigue bugueado/omitido, confirmado que
        # SNIax no lo declara). GENRANGE_AV real: 0.001-3.0.
        host_av=dict(kind="exp_halfgauss", tau=1.7, sig=0.6, ratio=4.0,
                      av_range=(0.001, 3.0), r_v=3.1),
    ),
    "TDE-MOSFIT": dict(
        # SED.INFO real trae una linea suelta invalida ("tde_384.json",
        # sin prefijo "SED:" ni ':') que rompe el parser YAML de
        # LightCurveLynx (no el de SNANA, que no es YAML estricto) -- ver
        # setup_simsed_local.py. Se usa una copia local saneada (SED.INFO
        # reescrito, templates symlinkeados, archivo real no tocado).
        simsed_dir=HERE / "simsed_tdemosfit_local",
        genrange_redshift=(0.01, 2.9),
        dndz=("tde", 1.0e-6),
        sntype=51,
        # GENAV_WV07 esta comentado (deshabilitado) en el .INPUT real de
        # esta clase -- usa GENTAU_AV=0.4 puro (comentario real: "expon
        # component only, no Gauss core"), no el modelo WV07 mixto.
        host_av=dict(kind="exp", tau=0.4, av_max=3.0, r_v=3.1),
    ),
    "SNII-NMF": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SNII-NMF",
        genrange_redshift=(0.011, 1.0),
        dndz=("ccs15", 0.162),
        sntype=42,
        # sin extincion de host declarada en el .INPUT real -- comparacion
        # limpia, igual que SNIa/SNIa-91bg.
        redcor_params=dict(
            peaks=dict(pc1=0.0854, pc2=0.0199, pc3=0.0250),
            sigmas=dict(pc1=0.075, pc2=0.021, pc3=0.017),
            redcor={("pc1", "pc2"): 0.241, ("pc1", "pc3"): 0.052, ("pc2", "pc3"): -0.074},
        ),
    ),
    # Fase 2B ronda 3: 3 clases SIMSED que declaran WV07 real (confirmado
    # `GENAV_WV07: 1` en su .INPUT, no el camino GENPROFILE_AV de SNIax).
    # ILOT-MOSFIT y SNIIn-MOSFIT reusan DNDZ: CC_S15 (ya validado en
    # SNII-NMF); PISN-MOSFIT usa el polinomio PISN_PLK12 real. Host
    # extinction real agregada en Fase 3, ver comentario arriba.
    "ILOT-MOSFIT": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.ILOT-MOSFIT",
        genrange_redshift=(0.011, 0.30),
        dndz=("ccs15", 0.06),
        sntype=61,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    "SNIIn-MOSFIT": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SNIIn-MOSFIT",
        genrange_redshift=(0.03, 2.0),
        dndz=("ccs15", 0.0235),
        sntype=45,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    "PISN-MOSFIT": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.PISN-MOSFIT",
        genrange_redshift=(0.02, 2.4),
        dndz=("pisn", 1.0),
        sntype=70,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    # Fase 2B ronda 4: cierra el catalogo. KN-BULLA19 es la ultima de las
    # 11 clases SIMSED originales (su estructura de 3 sub-variantes
    # anidadas -- SIMSED.BULLA-BHNS-M1-2COMP, -BNS-M2-2COMP, -BNS-M3-3COMP
    # -- quedo sin investigar desde Fase 2B ronda 1; el .INPUT real usa
    # solo BNS-M2-2COMP via GENMODEL). PISN-STELLA-HECORE/-HYDROGENIC son
    # 2 clases mas alla de las 11 originales, encontradas al re-revisar
    # pipeline/models.yaml -- mismo GENMODEL:.../SIMSED.* que las demas,
    # nunca corridas.
    #
    # KN-BULLA19 usa `WV07_REWGT_EXPAV: 0.5` (no `GENAV_WV07: 1` directo) --
    # confirmado leyendo snlc_sim.c (linea ~7887): cualquier valor real de
    # WV07_REWGT_EXPAV activa `INPUTS.WV07_GENAV_FLAG = DO_WV07 = 1`, el
    # mismo flag que usan KN-K17/CaRT/SLSN-I. PISN-STELLA-HECORE/-HYDROGENIC
    # declaran `GENAV_WV07: 1` directo, igual que PISN-MOSFIT.
    "KN-BULLA19": dict(
        # los 550 "*.txt.gz" reales no son gzip -- son ZIP mal etiquetados
        # (firma PK, confirmado con `file`), cada uno con 1 miembro interno
        # del mismo nombre. Ver setup_knbulla19_local.py: copia local con
        # cada archivo descomprimido del ZIP y re-comprimido como gzip real
        # (SED.INFO no necesita fix, ya parsea limpio). Archivo real no
        # tocado.
        simsed_dir=HERE / "simsed_knbulla19_local",
        genrange_redshift=(0.011, 0.28),
        dndz=("powerlaw", [(320e-9, 0.0, 0.011, 0.28)]),  # identico a KN-K17
        sntype=52,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=0.5, r_v=3.1),
    ),
    "PISN-STELLA-HECORE": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/elastic/model_libs_updates/SIMSED.PISN-STELLA-HECORE",
        genrange_redshift=(0.02, 2.2),
        dndz=("pisn", 1.0),
        sntype=71,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
    ),
    "PISN-STELLA-HYDROGENIC": dict(
        simsed_dir=SNANA_HOME / "run_SNANA/elastic/model_libs_updates/SIMSED.PISN-STELLA-HYDROGENIC",
        genrange_redshift=(0.02, 2.2),
        dndz=("pisn", 1.0),
        sntype=72,
        # unica clase del catalogo con ngen_ddf != 2000 (pipeline/models.yaml:
        # 20000) -- confirmado, no un valor por defecto sin verificar.
        ngentot_lc=20000,
        host_av=dict(kind="wv07", av_range=(0.0, 3.0), rewgt_expav=None, r_v=3.1),
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
    # la mayoria de las clases DDF usan NGENTOT_LC=2000 (pipeline/models.yaml:
    # ngen_ddf), pero PISN-STELLA-HYDROGENIC es la excepcion real (ngen_ddf:
    # 20000) -- cfg["ngentot_lc"] la overridea; ngentot_override (usado por
    # los smoke tests) tiene prioridad sobre ambas.
    ngentot = ngentot_override if ngentot_override is not None else cfg.get("ngentot_lc", NGENTOT_LC)
    # Fase 5: seed_index != 0 corre una realizacion independiente (semilla
    # real distinta, offset grande para no chocar con los sub-offsets +1..+9
    # ya usados abajo) en un directorio de salida separado -- no pisa el
    # resultado "principal" (seed_index=0) ya reportado en el dashboard/
    # NOTES.md, para poder cuantificar varianza entre semillas sin invalidar
    # las comparaciones ya publicadas.
    seed_base = SEED_BASE + seed_index * 1_000_000
    suffix = f"_seed{seed_index}" if seed_index else ""
    out_dir = HERE / f"poc_output_{class_key.lower().replace('-', '')}{suffix}"
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
    if "redcor_params" in cfg:
        # peso real via bivariada/multivariada normal correlacionada
        # (SIMSED_REDCOR), no uniforme -- parsear los valores propios de
        # cada template desde SED.INFO (mismo orden que PARNAMES).
        sed_info_text = (simsed_dir / "SED.INFO").read_text()
        param_names = None
        for line in sed_info_text.splitlines():
            if line.strip().upper().startswith("PARNAMES:"):
                param_names = line.split()[1:]
                break
        param_rows = [
            line.split()[2:] for line in sed_info_text.splitlines()
            if line.strip().upper().startswith("SED:")
        ]
        rc = cfg["redcor_params"]
        # PARNAMES puede traer columnas extra que no son parametros fisicos
        # correlacionados (p.ej. "II_INDEX" antes de pc1/pc2/pc3 en
        # SNII-NMF) -- solo se usan las columnas que aparecen en
        # redcor_params["peaks"], el resto se ignora.
        values = {
            name: np.array([float(r[i]) for r in param_rows])
            for i, name in enumerate(param_names)
            if name in rc["peaks"]
        }
        weights = make_correlated_normal_weights(values, rc["peaks"], rc["sigmas"], rc["redcor"])
        print(f"[{time.time()-t_start:.1f}s] {len(file_names)} templates SIMSED, "
              f"pesos via SIMSED_REDCOR real ({list(values.keys())})")
    else:
        # peso uniforme (SIMSED_GRIDONLY en el .INPUT real) -- None hace
        # que MultiSEDTemplateModel pese todos los templates igual.
        weights = None
        print(f"[{time.time()-t_start:.1f}s] {len(file_names)} templates SIMSED "
              f"(peso uniforme, SIMSED_GRIDONLY)")

    z_min, z_max = cfg["genrange_redshift"]
    dndz_kind, dndz_params = cfg["dndz"]
    if dndz_kind == "powerlaw":
        z_grid, cdf = build_dndz_powerlaw2_cdf(segments=dndz_params, z_min=z_min, z_max=z_max)
    elif dndz_kind == "md14":
        z_grid, cdf = build_dndz_md14_cdf(rate0=dndz_params, z_min=z_min, z_max=z_max)
    elif dndz_kind == "ccs15":
        z_grid, cdf = build_dndz_ccs15_cdf(scale=dndz_params, z_min=z_min, z_max=z_max)
    elif dndz_kind == "tde":
        z_grid, cdf = build_dndz_tde_cdf(rate0=dndz_params, z_min=z_min, z_max=z_max)
    elif dndz_kind == "pisn":
        z_grid, cdf = build_dndz_pisn_cdf(scale=dndz_params, z_min=z_min, z_max=z_max)
    else:
        raise ValueError(f"dndz_kind desconocido: {dndz_kind}")
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=seed_base + 1), node_label="redshift")
    # Fase 5: radius=0.0 explicito -- ObsTableRADECSampler.compute() aplica
    # un jitter de posicion dentro del FOV usando np.random.default_rng()
    # SIN seed cuando self.radius>0 (heredado del radius real de OpSim,
    # bug de la libreria, confirmado leyendo ra_dec_sampler.py). Los campos
    # DDF son pointings fijos, no requieren jitter sub-FOV -- radius=0.0
    # evita ese codepath entero.
    radec_sampler = ObsTableRADECSampler(obs_table, extra_cols=["field"], seed=seed_base + 5, radius=0.0)
    # Segundo bug de la libreria, mas profundo: TableSampler.__init__
    # (clase base de ObsTableRADECSampler) crea su propio muestreador de
    # indice de fila via `NumpyRandomFunc("integers", low=0, high=N)` SIN
    # pasarle seed= (confirmado leyendo given_sampler.py) -- el seed=
    # que se le pasa al constructor de ObsTableRADECSampler nunca llega a
    # este nodo hijo, asi que la fila/pointing real elegida para cada
    # objeto (y por lo tanto que observaciones reales le corresponden)
    # segui siendo no reproducible incluso despues del fix de radius=0.0
    # de arriba. Mismo patron que el bug de SIMSEDModel de Fase 4: fijar
    # el seed del nodo interno directamente via .setters[...].dependency.
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
        simsed_dir, weights=weights,
        ra=radec_sampler.ra, dec=radec_sampler.dec,
        redshift=redshift_func, distance=distance_func, t0=t0_func,
    )
    # Fase 4: SIMSEDModel.from_dir() nunca pasa un seed a su
    # GivenValueSampler interno (confirmado leyendo sed_template_model.py:
    # `self._sampler_node = GivenValueSampler(all_inds, weights=weights)`,
    # sin `seed=`) -- NumpyRandomFunc con seed=None cae a
    # `os.urandom()` (math_nodes/np_random.py), es decir la seleccion de
    # template real de SIMSED **nunca fue reproducible** entre corridas en
    # ninguna ronda anterior de Fase 2B/3, pese a SEED_BASE. Fijar el seed
    # aqui para que corridas futuras sean reproducibles -- no se re-corrio
    # el catalogo completo de nuevo solo por esto (ver NOTES.md Fase 4).
    source_model._sampler_node.set_seed(seed_base + 9)
    source_model.add_effect(mw_extinction)

    if "host_av" in cfg:
        # extincion de host real -- tres variantes reales de SNANA, todas
        # verificadas linea por linea contra snlc_sim.c (ver NOTES.md):
        # "exp" = solo componente exponencial (TDE-MOSFIT); "exp_halfgauss"
        # = mezcla exponencial+semi-Gaussiana via GENPROFILE_AV (SNIax);
        # "wv07" = modelo ESSENCE-WV07 real (GENAV_WV07(), Fase 3) --
        # funcion autonoma con constantes fijas (tau=0.4, sqsigma=0.01),
        # NO la que tenia el bug historico (esa es getRan_GEN_EXP_HALFGAUSS,
        # nunca llamada por GENAV_WV07).
        hp = cfg["host_av"]
        kind = hp.get("kind", "exp")
        if kind == "exp_halfgauss":
            av_sampler_fn = make_exp_halfgauss_av_sampler(
                tau=hp["tau"], sig=hp["sig"], ratio=hp["ratio"],
                av_range=hp["av_range"], seed=seed_base + 8,
            )
            av_desc = f"GENTAU_AV={hp['tau']}"
        elif kind == "wv07":
            av_sampler_fn = make_wv07_av_sampler(
                av_range=hp["av_range"], rewgt_expav=hp.get("rewgt_expav"), seed=seed_base + 8,
            )
            av_desc = f"WV07_REWGT_EXPAV={hp.get('rewgt_expav')}"
        else:
            av_sampler_fn = make_exp_av_sampler(tau=hp["tau"], av_max=hp["av_max"], seed=seed_base + 8)
            av_desc = f"GENTAU_AV={hp['tau']}"
        av_func = SizeAwareFunctionNode(av_sampler_fn, node_label="host_av")

        def _av_to_ebv(size=None, host_av=None, **_kwargs):
            return np.asarray(host_av) / hp["r_v"]

        host_ebv_func = SizeAwareFunctionNode(_av_to_ebv, node_label="host_ebv", host_av=av_func)
        host_extinction = ClippedExtinctionEffect(
            extinction_model="CCM89", ebv=host_ebv_func, r_v=hp["r_v"], frame="rest", backend="dust_extinction",
        )
        source_model.add_effect(host_extinction)
        print(f"[{time.time()-t_start:.1f}s] extincion de host real aplicada "
              f"(kind={kind}, {av_desc}, R_V={hp['r_v']})")

    print(f"[{time.time()-t_start:.1f}s] SIMSEDModel cargado ({len(source_model)} templates)")

    t_sim0 = time.time()
    # Fase 5: rng= explicito -- simulate_lightcurves() acepta un
    # numpy.random.Generator opcional que se propaga a cualquier nodo del
    # grafo sin seed propio (p.ej. la aplicacion de ruido fotometrico), y
    # que si no se pasa cae en un generador default no reproducible. Los
    # otros nodos (redshift, radec, t0, host_av, template) ya tienen su
    # propio seed explicito arriba -- este cierra el ultimo hueco.
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
    # Fase 4: agrupar observaciones en epocas reales (NEWMJD_DIF=0.007d, ver
    # searcheff.group_into_epochs) antes de aplicar el trigger ">=2 epocas" --
    # contar observaciones individuales (como hacian las Fases 0-3) infla el
    # trigger, ver NOTES.md.
    detected_snids = object_level_detected(phot_df, min_epochs=min_epochs)
    print(f"[{time.time()-t_start:.1f}s] SEARCHEFF aplicado: {len(detected_snids)}/{len(head_df)} "
          f"objetos detectados (>= {min_epochs} epocas reales, agrupadas)")

    all_ids = lc["id"].astype(int).astype(str)
    dump_df = pd.DataFrame({"CID": all_ids, "ZHELIO": lc["z"].to_numpy(), "ZCMB": lc["z"].to_numpy()})
    head_df_detected = head_df[head_df["SNID"].isin(detected_snids)].reset_index(drop=True)

    # Fase 5: persistir la tabla real (head_df/phot_df), no solo el resumen
    # agregado -- hasta ahora el pipeline nunca escribia a disco los datos
    # crudos de la simulacion (ni FITS/DUMP estilo SNANA, LightCurveLynx no
    # tiene un writer nativo para eso, confirmado revisando la documentacion
    # oficial -- ni ninguna otra tabla), solo las imagenes QC y el JSON de
    # metricas agregadas. Parquet (via pyarrow) por tamano -- phot_df puede
    # tener millones de filas para NGENTOT completo. No se versiona en git
    # (ver .gitignore), solo vive en el output dir de NLHPC/local.
    head_df["DETECTED"] = head_df["SNID"].isin(detected_snids)
    head_df.to_parquet(out_dir / "head_df.parquet", index=False)
    phot_df.to_parquet(out_dir / "phot_df.parquet", index=False)
    print(f"[{time.time()-t_start:.1f}s] tablas persistidas: head_df.parquet "
          f"({len(head_df)} filas), phot_df.parquet ({len(phot_df)} filas)")

    (out_dir / "summary.json").write_text(json.dumps({
        "class_key": class_key,
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
        paths = qc.run_all_qc(head_df_detected, phot_df, qc_dir, f"LightCurveLynx_{class_key}_DDF_poc", dump_df=dump_df)
        print(f"[{time.time()-t_start:.1f}s] QC generado: {list(paths.keys())}")
    else:
        print(f"[{time.time()-t_start:.1f}s] ! 0 objetos detectados, QC omitido")
    print(f"[{time.time()-t_start:.1f}s] TOTAL")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in CLASS_CONFIGS:
        print(f"uso: python3 run_simsed_poc.py <clase> [seed_index]  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    _seed_index = int(sys.argv[2]) if len(sys.argv) == 3 else 0
    main(sys.argv[1], seed_index=_seed_index)
