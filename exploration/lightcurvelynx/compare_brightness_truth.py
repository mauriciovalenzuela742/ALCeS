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

Fase 47: `flux_perfect.max()` sobre la cadencia real (usado desde Fase 7)
es la MISMA metrica que la propia Fase 22 declaro invalida para SNIa/SALT2
-- subestima el brillo real para ~33.6% de los objetos, cadencia real de
DDF nunca cae cerca del pico verdadero. Ese fix migro a
compare_brightness_truth_salt2.py en Fase 39 pero nunca se porto a este
script -- corregido acá: `compute_noise_free_lightcurves()` real, evaluado
en `rest_phase=0` (pico verdadero continuo), no el maximo sobre cadencia.

Fase 50: generalizado para aceptar cualquier clase de CLASS_CONFIGS (antes
hardcodeado a SNIa-91bg, duplicando a mano redcor/dndz/Z_MIN-MAX/SIMSED_DIR
-- ese duplicado es exactamente el mecanismo por el que el fix de Fase 22
tardo 25 fases en llegar a este archivo, ver NOTES.md). El armado del
modelo (extincion host/MW, dndz, redcor, seeds) se REUSA de
run_simsed_poc.build_source_model(), no se reinventa. Mide las 6 bandas
LSST (u g r i z y), no solo r -- el patron cromatico fue lo que destapo
Fases 23/36/37, y esta es la primera vez que se mide una clase nueva.
Integra el filtro de contaminacion de campo (Fase 36/48,
filter_ddf_field_contamination) desde el arranque, aplicado sobre la
referencia SNANA en compare_brightness_truth_binned.py (este script solo
produce el lado LCL).

Fase 53: la extincion de host (clases con cfg["host_av"]) ya NO se aplica
como ClippedExtinctionEffect punto a punto sobre el SED
(host_extinction_mode="scalar" en build_source_model()) -- Fase 52 encontro
que SNANA real la aplica como un escalar de magnitud POR BANDA, evaluado en
la longitud de onda media REST-FRAME del filtro (GALextinct(RV_host,
AV_host, meanlam_rest, 94, ...), genmag_SIMSED.c:1554-1567), no sobre el SED
completo antes de integrar. Se recupera host_av real (sampleado, mismo seed)
via source_model.get_param(graph_state, "host_av") y se aplica la
correccion (host_extinction_mag_offset()) sobre PEAKMAG_x_true ya calculado.
No se toca run_simsed_poc.py::main() (produccion) -- ver NOTES.md Fase 53.

Reconstruye el MISMO source_model real que run_simsed_poc.py para la clase
pedida (mismos parametros reales de CLASS_CONFIGS, mismo H0=70, misma
extincion MW/host).

Uso (sbatch, no en login node -- carga los templates SIMSED reales de la
clase + evalua NGENTOT objetos sin ruido):
    python3 compare_brightness_truth.py <clase>   (claves: ver CLASS_CONFIGS)
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import compute_noise_free_lightcurves

# Fase 74: REPO_ROOT resuelto por local_env.py (portabilidad).
from local_env import REPO_ROOT
sys.path.insert(0, str(REPO_ROOT / "exploration/lightcurvelynx"))
from run_simsed_poc import (  # noqa: E402
    CLASS_CONFIGS, build_source_model, snana_noise_columns, restlambda_gate,
    passband_mean_wavelengths, host_extinction_mag_offset, LSST_PASSBAND_TABLE_DIR,
)

HERE = REPO_ROOT / "exploration/lightcurvelynx"
OPSIM_DB = REPO_ROOT / "data/opsim/baseline_v5.3.1_10yrs.db"
NGENTOT = 2000
SEED_BASE = 20260815  # deliberadamente distinto del SEED_BASE de run_simsed_poc.py
                       # (20260813) -- realizacion independiente, no pisa las
                       # corridas de produccion ya reportadas.
BANDS = ["u", "g", "r", "i", "z", "y"]
MAG_AB_ZP_NJY = 8.9 + 2.5 * 9


def main(class_key: str):
    if class_key not in CLASS_CONFIGS:
        print(f"uso: python3 compare_brightness_truth.py <clase>  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    cfg = CLASS_CONFIGS[class_key]
    t_start = time.time()
    seed_base = SEED_BASE

    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    df_ddf = snana_noise_columns(df_ddf)
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    print(f"[{time.time()-t_start:.1f}s] [{class_key}] OpSim DDF: {len(df_ddf):,} obs")

    passband_group = PassbandGroup.from_preset(preset="LSST", table_dir=str(LSST_PASSBAND_TABLE_DIR))
    print(f"[{time.time()-t_start:.1f}s] passbands cargados (Fase 55: u truncado a 4134A real)")

    # Fase 50: bloque real de armado de modelo REUSADO de run_simsed_poc.py
    # (extincion host segun cfg["host_av"]["kind"], dndz, redcor si la clase
    # los declara, seeds) -- no se duplica a mano.
    # Fase 56: simsed_t0_mode="bolometric_peak" -- ver NOTES.md. Reemplaza la
    # cadena de intentos de Fases 47/50/52/54 (que asumian que Trest=0 real de
    # SNANA era la fase nativa 0 del archivo .SED, o el maximo sobre una
    # ventana) por la causa raiz real: SNANA shiftea cada template a su pico
    # bolometrico real ANTES de generar (T0shiftPeak_SEDMODEL, confirmado
    # activo por defecto para SIMSED), asi que Trest=0 real ES el pico
    # bolometrico -- no una convencion a adivinar por clase.
    source_model, _radec_sampler = build_source_model(
        cfg, obs_table, seed_base, t_start, wfd=False,
        host_extinction_mode="scalar", simsed_t0_mode="bolometric_peak",
    )

    # Fase 47: `flux_perfect.max()` sobre la cadencia real es la metrica que la propia
    # Fase 22 declaro invalida para SNIa/SALT2 (subestima el brillo real para ~33.6% de
    # los objetos, cadencia real de DDF nunca cae cerca del pico verdadero). Corregido a
    # `compute_noise_free_lightcurves()` real, evaluado en un unico punto continuo
    # (`rest_phase=0`), no atado a ninguna cadencia observada.
    #
    # Fase 50 tuvo que abandonar temporalmente el punto unico y usar el maximo sobre
    # una ventana completa porque, bajo `simsed_t0_mode="raw"` (el unico que existia
    # entonces), `rest_phase=0` significaba literalmente "fase nativa 0 del archivo
    # .SED" -- valido por construccion para `SNIa-91bg`/`SNIax` (fase nativa 0 =
    # pico, ~cierto), pero `CaRT` arranca en fase nativa +0.501 y su pico real cae
    # varios dias despues (Fase 54: hasta +33 dias segun el template) -- `rest_phase=0`
    # caia fuera de la grilla y devolvia flujo 0. Fase 52/54 investigaron el `PEAKMAG`
    # real de SNANA (`snlc_sim.c:8455-8456/27104-27107`, magnitud exacta en
    # `Trest=0`) pero interpretaron "Trest=0" como la fase nativa del archivo -- Fase 54
    # confirmo que esa lectura reproduce EXACTO la prediccion para `SNIa-91bg` pero
    # rompe `CaRT` (+2 a +4 mag).
    #
    # Fase 56 resuelve la causa raiz: con `simsed_t0_mode="bolometric_peak"` (arriba),
    # `rest_phase=0` YA ES el pico bolometrico real de cada template -- el mismo Trest=0
    # que usa SNANA (`genmag_SIMSED.c:351-361`, `T0shiftPeak_SEDMODEL` real). Vuelve a
    # ser seguro evaluar en un unico punto (`rest_frame_phase_min=0.0,
    # rest_frame_phase_max=0.5, rest_frame_phase_step=1.0`, la convencion original de
    # Fase 39/47) para las 3 clases -- el pico bolometrico de cualquier template, por
    # construccion, cae dentro de su propia cobertura real (`CaRT` incluido).
    t_sim0 = time.time()
    graph_state = source_model.sample_parameters(
        num_samples=NGENTOT, rng_info=np.random.default_rng(seed_base + 2),
    )
    lc = compute_noise_free_lightcurves(
        source_model, graph_state, passband_group,
        rest_frame_phase_min=0.0, rest_frame_phase_max=0.5, rest_frame_phase_step=1.0,
    )
    print(f"[{time.time()-t_start:.1f}s] evaluacion sin ruido terminada: {len(lc)} objetos, "
          f"Trest=0 (pico bolometrico real), {time.time()-t_sim0:.1f}s")

    # Fase 53: correccion escalar de extincion de host, precalculada una vez
    # por banda (no por objeto -- host_extinction_mag_offset() ya vectoriza
    # sobre todos los objetos a la vez). host_av_arr/z_arr vienen del MISMO
    # graph_state que genero `lc`, mismo orden (id=0..N-1) -- indexables
    # directo por row["id"] en el loop de abajo.
    delta_mag_by_band = None
    if "host_av" in cfg:
        host_av_arr = np.atleast_1d(np.asarray(source_model.get_param(graph_state, "host_av")))
        meanlam_obs = passband_mean_wavelengths(passband_group, BANDS)
        r_v = cfg["host_av"]["r_v"]
        z_arr = lc["z"].to_numpy()
        delta_mag_by_band = {
            band: host_extinction_mag_offset(z_arr, host_av_arr, r_v, meanlam_obs[band])
            for band in BANDS
        }
        print(f"[{time.time()-t_start:.1f}s] Fase 53: extincion de host como escalar por banda "
              f"(meanlam_rest real via GALextinct, no sobre el SED completo)")

    # Fase 13: si la clase declara restlambda_range, replicar el "bail if any
    # part of filter trans is outside model range" real de SNANA -- una banda
    # cuyo rango observado no cabe COMPLETO en marco de reposo dentro de
    # RESTLAMBDA_RANGE nunca es generada por SNANA a ese z, asi que se reporta
    # como NaN en vez de un flujo extrapolado/clampeado.
    restlambda_range = cfg.get("restlambda_range")

    rows = []
    n_gated = {b: 0 for b in BANDS}
    for _, row in lc.iterrows():
        sub = row["lightcurve"]
        if sub is None or len(sub) == 0:
            continue
        z = row["z"]
        rec = {"SNID": str(int(row["id"])), "z": z}
        for band in BANDS:
            if band not in sub.columns:
                rec[f"PEAKMAG_{band}_true"] = np.nan
                continue
            if restlambda_range is not None and not restlambda_gate(z, "Y" if band == "y" else band, restlambda_range):
                rec[f"PEAKMAG_{band}_true"] = np.nan
                n_gated[band] += 1
                continue
            # Fase 56: un unico punto de grilla (rest_phase=0, ya el pico
            # bolometrico real gracias a simsed_t0_mode="bolometric_peak" --
            # ver bloque de arriba). sub tiene una sola fila por banda.
            peak_flux_true = sub[band].to_numpy()[0]
            if peak_flux_true <= 0:
                rec[f"PEAKMAG_{band}_true"] = np.nan
                continue
            mag_true = MAG_AB_ZP_NJY - 2.5 * np.log10(peak_flux_true)
            if delta_mag_by_band is not None:
                # row["id"] es el indice real (0..N-1) del mismo graph_state
                # que uso host_extinction_mag_offset() -- ver bloque de arriba.
                mag_true += delta_mag_by_band[band][int(row["id"])]
            rec[f"PEAKMAG_{band}_true"] = mag_true
        rows.append(rec)

    if restlambda_range is not None:
        print(f"[{time.time()-t_start:.1f}s] Fase 13: bandas suprimidas por RESTLAMBDA_RANGE="
              f"{restlambda_range} en marco de reposo: {n_gated}")

    out = pd.DataFrame(rows)
    out_path = HERE / f"compare_brightness_truth_{class_key.lower().replace('-', '')}_output.parquet"
    out.to_parquet(out_path, index=False)
    print(f"[{time.time()-t_start:.1f}s] {len(out)} objetos calculados (sin ruido), "
          f"guardado en {out_path.name}")
    print(out.describe())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"uso: python3 compare_brightness_truth.py <clase>  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    main(sys.argv[1])
