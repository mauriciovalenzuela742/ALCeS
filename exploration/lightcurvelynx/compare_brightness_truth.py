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

sys.path.insert(0, "/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx")
from run_simsed_poc import CLASS_CONFIGS, build_source_model, snana_noise_columns, restlambda_gate  # noqa: E402

HERE = Path("/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx")
OPSIM_DB = Path("/home/mvalenzuela/AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db")
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

    passband_group = PassbandGroup.from_preset(preset="LSST")
    print(f"[{time.time()-t_start:.1f}s] passbands cargados")

    # Fase 50: bloque real de armado de modelo REUSADO de run_simsed_poc.py
    # (extincion host segun cfg["host_av"]["kind"], dndz, redcor si la clase
    # los declara, seeds) -- no se duplica a mano.
    source_model, _radec_sampler = build_source_model(cfg, obs_table, seed_base, t_start, wfd=False)

    # Fase 47: `flux_perfect.max()` sobre la cadencia real es la metrica que la propia
    # Fase 22 declaro invalida para SNIa/SALT2 (subestima el brillo real para ~33.6% de
    # los objetos, cadencia real de DDF nunca cae cerca del pico verdadero). Corregido:
    # `compute_noise_free_lightcurves()` real sobre una grilla de fase DENSA Y CONTINUA
    # (no atada a ninguna cadencia real observada -- es la diferencia real con el bug de
    # Fase 22/47), tomando el maximo de flujo por banda sobre esa grilla.
    #
    # Fase 50: `rest_phase=0` (un unico punto, la convencion de Fase 39/47) asume que
    # phase=0 ES el pico -- cierto para plantillas tipo SNIa (SALT2, 91bg, SNIax: la
    # grilla real de sus SED arranca en phase negativo, p.ej. -25.0, con phase=0 el
    # maximo por construccion). Descubierto corriendo `CaRT` con ese supuesto: devolvio
    # flujo 0.0 en las 6 bandas para los 2000 objetos -- la grilla real de
    # SIMSED.CART-MOSFIT (`SED.INFO`) arranca en phase=**0.501**, no en phase negativo
    # (convencion "dias desde la explosion", no "dias desde el pico", verificado
    # inspeccionando los `.dat.gz` reales). `rest_phase=0` cae fuera de la grilla
    # definida y el modelo no extrapola -- devuelve 0, no NaN. Corregido para evaluar
    # sobre el `trest_range` real de la clase (mismo `cfg.get("trest_range", (-30, 100))`
    # que ya usa `run_simsed_poc.py` para su ventana de generacion real, Fase 40/43 --
    # no se inventa un rango nuevo) y tomar el maximo de flujo por banda sobre esa
    # grilla completa. Para las clases tipo SNIa esto reproduce el mismo resultado que
    # evaluar solo en phase=0 (el pico YA esta en phase=0 por construccion) -- confirmado
    # con el control positivo de `SNIa-91bg` re-corrido despues de este cambio.
    trest_range = cfg.get("trest_range", (-30.0, 100.0))
    t_sim0 = time.time()
    graph_state = source_model.sample_parameters(
        num_samples=NGENTOT, rng_info=np.random.default_rng(seed_base + 2),
    )
    lc = compute_noise_free_lightcurves(
        source_model, graph_state, passband_group,
        rest_frame_phase_min=trest_range[0], rest_frame_phase_max=trest_range[1], rest_frame_phase_step=1.0,
    )
    print(f"[{time.time()-t_start:.1f}s] evaluacion sin ruido terminada: {len(lc)} objetos, "
          f"trest_range={trest_range}, {time.time()-t_sim0:.1f}s")

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
            peak_flux_true = sub[band].to_numpy().max()
            if peak_flux_true <= 0:
                rec[f"PEAKMAG_{band}_true"] = np.nan
                continue
            rec[f"PEAKMAG_{band}_true"] = MAG_AB_ZP_NJY - 2.5 * np.log10(peak_flux_true)
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
