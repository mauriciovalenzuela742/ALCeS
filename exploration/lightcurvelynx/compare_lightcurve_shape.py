"""
Fase 60 (segundo pendiente) / Fase 63: mide forma/duracion de curva de luz
directamente contra SNANA, no solo brillo pico -- extension real de la
metodologia de Fase 39 (pareo objeto-a-objeto y epoca-a-epoca via
`SIM_MAGOBS`/`_PHOT.FITS` real) a una clase SIMSED, mas un paso nuevo:
recomputar el TRIGGER real (searcheff.py, ya versionado y usado en
produccion) sobre la fotometria evaluada por LightCurveLynx en las MISMAS
epocas/ruido reales, para medir si LightCurveLynx sostiene la ventana de
deteccion (MJD_DETECT_FIRST/LAST) mas tiempo que SNANA real -- el mecanismo
que Fase 60 dejo como hipotesis (ILOT-MOSFIT es mas tenue en el pico pero
sobre-detecta 7.09x).

Restriccion real importante (no un descuido): `_HEAD.FITS`/`_PHOT.FITS`
solo persisten los objetos que SNANA realmente escribio (`NGENLC_WRITE`,
p.ej. 73/2000 para ILOT-MOSFIT, 3.65% -- coincide con el `SNANA%` real ya
usado en Fase 48/49/59). Es decir, esta fase solo puede comparar sobre el
CENSO COMPLETO de objetos que SNANA si detecto (no hay fotometria real de
los que rechazo, esos no se escriben a FITS) -- la pregunta que responde es
"para los mismos objetos que SNANA detecto, con los mismos parametros/
cadencia/ruido reales, sostiene LightCurveLynx (al evaluar su propio modelo)
una ventana de deteccion mas larga que SNANA real?", no "cuantos objetos
que SNANA rechazo LCL detecta de mas" (eso requeriria reconstruir cadencia
sintetica para los ~1927 objetos no escritos, fuera de alcance de esta
fase).

Reusa sin reimplementar: `searcheff.parse_searcheff_pipeline/
parse_pipeline_logic/apply_detection_efficiency/group_into_epochs` (mismo
codigo real que usa `run_simsed_poc.py` en produccion) y
`host_extinction_mag_offset()`/`passband_mean_wavelengths()` (Fase 53).

Uso (interactivo esta bien para clases chicas como ILOT-MOSFIT -- N objetos
= NGENLC_WRITE real, no NGENTOT_LC; para clases con mas objetos escritos
evaluar si conviene sbatch):
    python3 compare_lightcurve_shape.py <clase>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.models.sed_template_model import SEDTemplate, SIMSEDModel

from run_simsed_poc import (
    CLASS_CONFIGS, host_extinction_mag_offset, passband_mean_wavelengths,
    LSST_PASSBAND_TABLE_DIR,
)
# Fase 74: SNANA_HOME resuelto por local_env.py (portabilidad).
from local_env import SNANA_HOME
from searcheff import (
    parse_searcheff_pipeline, parse_pipeline_logic, apply_detection_efficiency,
    group_into_epochs, PHOTFLAG_DETECT,
)

HERE = Path(__file__).resolve().parent
SEARCHEFF_PIPELINE_FILE = SNANA_HOME / "run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT"
SEARCHEFF_LOGIC_FILE = SNANA_HOME / "run_SNANA/LSST_PIPELINE_LOGIC.DAT"

MAGZP_NJY = 8.9 + 2.5 * 9  # Fase 39/pilotos: bandflux de evaluate_bandfluxes() en nJy

# Directorio real de produccion no siempre coincide con la clave de
# CLASS_CONFIGS (p.ej. ILOT-MOSFIT -> directorio "ILOT_DDF...", sin sufijo).
REAL_DDF_DIR_NAME = {
    "ILOT-MOSFIT": "ILOT_DDF_baseline_v5.3.1_10yrs",
}
# Nombre real de la columna de indice de template en el SED.INFO de cada
# clase (SIMSED_GRIDONLY: <nombre>, confirmado distinto por clase).
INDEX_COL_NAME = {
    "ILOT-MOSFIT": "ILOT_INDEX",
}


def load_class_data(class_key: str):
    cfg = CLASS_CONFIGS[class_key]
    dir_name = REAL_DDF_DIR_NAME.get(class_key, f"{class_key}_DDF_baseline_v5.3.1_10yrs")
    base = SNANA_HOME / "DATASIM_LSST_1/DDF/SIMDv8" / dir_name
    head = fits.open(base / f"{dir_name}_HEAD.FITS")[1].data
    phot = fits.open(base / f"{dir_name}_PHOT.FITS")[1].data
    sed_info_lines = [
        l.split() for l in open(cfg["simsed_dir"] / "SED.INFO") if l.strip().startswith("SED:")
    ]
    names = [l[1] for l in sed_info_lines]
    idx_vals = np.array([float(l[2]) for l in sed_info_lines])
    val2row = {v: i for i, v in enumerate(idx_vals)}
    flux_scale = 1.0
    for l in open(cfg["simsed_dir"] / "SED.INFO"):
        if l.strip().startswith("FLUX_SCALE:"):
            flux_scale = float(l.split()[1])
    return cfg, head, phot, names, val2row, flux_scale


def build_template(simsed_dir: Path, names: list, row: int):
    path = simsed_dir / names[row]
    if not path.exists():
        path = path.with_suffix(path.suffix + ".gz")
    data = np.loadtxt(path, comments="#")
    order = np.argsort(data[:, 0], kind="stable")
    ps, fs = data[order, 0], data[order, 2]
    u, st = np.unique(ps, return_index=True)
    t0_bolo = float(u[np.argmax(np.add.reduceat(fs, st))])
    return SEDTemplate(data, sed_data_t0=t0_bolo, interpolation_type="linear", periodic=False)


def main(class_key: str, n_objects: int | None = None):
    t_start = time.time()
    cfg, head, phot, names, val2row, flux_scale = load_class_data(class_key)
    n_total = len(head)
    n_use = n_total if n_objects is None else min(n_objects, n_total)
    print(f"[{time.time()-t_start:.1f}s] {class_key}: {n_total} objetos reales escritos por SNANA "
          f"(NGENLC_WRITE) -- usando {n_use}")

    pb = PassbandGroup.from_preset(preset="LSST", table_dir=str(LSST_PASSBAND_TABLE_DIR))
    bands = ["u", "g", "r", "i", "z", "y"]
    meanlam = passband_mean_wavelengths(pb, bands)

    band_curves = parse_searcheff_pipeline(SEARCHEFF_PIPELINE_FILE)
    min_epochs = parse_pipeline_logic(SEARCHEFF_LOGIC_FILE)
    print(f"[{time.time()-t_start:.1f}s] SEARCHEFF real cargado (min_epochs={min_epochs})")

    template_cache: dict[int, SEDTemplate] = {}
    rows = []
    for k in range(n_use):
        tidx = float(head["SIM_TEMPLATE_INDEX"][k])
        row = val2row[tidx]
        if row not in template_cache:
            template_cache[row] = build_template(cfg["simsed_dir"], names, row)
        tmpl = template_cache[row]

        z = float(head["SIM_REDSHIFT_HELIO"][k])
        dlmu = float(head["SIM_DLMU"][k])
        dist_pc = 10.0 ** (dlmu / 5.0 + 1.0)
        tpk = float(head["SIM_PEAKMJD"][k])
        av, rv = float(head["SIM_AV"][k]), float(head["SIM_RV"][k])

        model = SIMSEDModel(
            [tmpl], flux_scale=flux_scale, weights=None,
            ra=float(head["RA"][k]), dec=float(head["DEC"][k]),
            redshift=z, distance=dist_pc, t0=tpk,
        )
        state = model.sample_parameters(num_samples=1, rng_info=np.random.default_rng(0))

        i0, i1 = int(head["PTROBS_MIN"][k]) - 1, int(head["PTROBS_MAX"][k])
        mjd = phot["MJD"][i0:i1].astype(float)
        flt_snana = np.array([b.strip().replace("LSST-", "") for b in phot["BAND"][i0:i1]])
        # LightCurveLynx/PassbandGroup usa 'y' minuscula; SEARCHEFF real (y el
        # BAND real del PHOT.FITS) usa 'Y' mayuscula -- dos representaciones
        # de la misma columna, cada una para su consumidor real.
        flt = np.where(flt_snana == "Y", "y", flt_snana)
        fluxcal_real = phot["FLUXCAL"][i0:i1].astype(float)
        fluxcalerr_real = phot["FLUXCALERR"][i0:i1].astype(float)
        smag = phot["SIM_MAGOBS"][i0:i1].astype(float)
        # Fase 63: el ZEROPT real es POR EPOCA (viene del SIMLIB real, ~29-32
        # dependiendo de banda/condiciones) -- NO el ZP=27.5 fijo que asume la
        # documentacion generica de SNANA. Confirmado con un caso real
        # (mag=24.5, FLUXCAL_real=270 implicaba ZP real=30.6, no 27.5) tras un
        # primer intento con ZP fijo que subestimaba fluxcal_lcl ~15-20x y
        # anulaba practicamente toda deteccion del lado LCL.
        zeropt_real = phot["ZEROPT"][i0:i1].astype(float)

        valid_band = np.isin(flt, bands)
        mjd, flt, flt_snana = mjd[valid_band], flt[valid_band], flt_snana[valid_band]
        fluxcal_real, fluxcalerr_real = fluxcal_real[valid_band], fluxcalerr_real[valid_band]
        smag, zeropt_real = smag[valid_band], zeropt_real[valid_band]
        if len(mjd) == 0:
            continue

        bf = model.evaluate_bandfluxes(pb, mjd, flt, state)
        with np.errstate(divide="ignore", invalid="ignore"):
            mag_lcl = MAGZP_NJY - 2.5 * np.log10(bf)
        # dmag_host solo depende de (z, av, rv, banda) -- constante por objeto,
        # se calcula UNA vez por banda presente (no por epoca) para evitar
        # reconstruir el modelo de polvo O94 cientos de veces por objeto.
        dmag_host_by_band = {
            b: float(host_extinction_mag_offset(z, av, rv, meanlam[b])[0]) for b in set(flt)
        }
        dmag_host = np.array([dmag_host_by_band[b] for b in flt])
        mag_lcl_total = mag_lcl + dmag_host
        fluxcal_lcl = 10.0 ** (-0.4 * (mag_lcl_total - zeropt_real))

        snid = int(head["SNID"][k]) if isinstance(head["SNID"][k], (int, np.integer)) else k

        # Fase 63: una sola realizacion Monte Carlo de apply_detection_efficiency()
        # resulto ser extremadamente ruidosa a nivel de objeto para clases de
        # trest_range ancho (miles de epocas reales por objeto, la mayoria de
        # SNR marginal) -- el control (recomputar sobre el FLUXCAL real de
        # SNANA) dio una ventana de deteccion mucho mas ancha que la real de
        # SNANA en un piloto de 5 objetos, pese a que el codigo es identico al
        # de produccion. Diagnosticado: NO es un bug, es varianza real de un
        # solo sorteo independiente (la curva real tiene eficiencia
        # EXACTAMENTE 0 para SNR<3 en las 6 bandas, pero SNR en [3,5] ya tiene
        # eficiencia 11-47%, suficiente para que create-ame >=2 epocas
        # "detectadas" dispersas en cualquier parte de una ventana de
        # observacion de anos, en un sorteo independiente distinto al que
        # realmente hizo SNANA). Se promedia sobre N_SEEDS sorteos
        # independientes para reducir esa varianza -- reporta mediana de
        # duracion y fraccion de objetos detectados sobre las semillas.
        def run_trigger_multiseed(fluxcal, fluxcalerr, n_seeds=20):
            epoch_id = group_into_epochs(mjd)
            firsts, lasts, neps = [], [], []
            for s in range(n_seeds):
                frame = pd.DataFrame({
                    "SNID": snid, "MJD": mjd, "FLT": flt_snana,
                    "FLUXCAL": fluxcal, "FLUXCALERR": fluxcalerr,
                })
                det = apply_detection_efficiency(frame, band_curves, seed=1000 * k + s)
                det_epochs = set(epoch_id[det.to_numpy()])
                if len(det_epochs) < min_epochs:
                    continue
                det_mjd = mjd[np.isin(epoch_id, list(det_epochs))]
                firsts.append(float(det_mjd.min())); lasts.append(float(det_mjd.max()))
                neps.append(len(det_epochs))
            return firsts, lasts, neps

        lcl_firsts, lcl_lasts, lcl_neps = run_trigger_multiseed(fluxcal_lcl, fluxcalerr_real)
        ctrl_firsts, ctrl_lasts, ctrl_neps = run_trigger_multiseed(fluxcal_real, fluxcalerr_real)

        near = np.abs((mjd - tpk) / (1.0 + z)) < 5
        resid_all = mag_lcl_total - smag
        n_seeds = 20
        rows.append(dict(
            SNID=snid, z=z, tidx=tidx, row=row, av=av,
            real_mjd_first=float(head["MJD_DETECT_FIRST"][k]),
            real_mjd_last=float(head["MJD_DETECT_LAST"][k]),
            lcl_detect_rate=len(lcl_firsts) / n_seeds,
            lcl_dur_med=float(np.median(np.array(lcl_lasts) - np.array(lcl_firsts))) if lcl_firsts else np.nan,
            ctrl_detect_rate=len(ctrl_firsts) / n_seeds,
            ctrl_dur_med=float(np.median(np.array(ctrl_lasts) - np.array(ctrl_firsts))) if ctrl_firsts else np.nan,
            resid_med=float(np.nanmedian(resid_all)),
            resid_near_peak=float(np.nanmedian(resid_all[near])) if near.sum() else np.nan,
            n_epochs_real=len(mjd),
        ))
        if (k + 1) % 10 == 0 or k == n_use - 1:
            print(f"[{time.time()-t_start:.1f}s] {k+1}/{n_use} objetos procesados")

    out = pd.DataFrame(rows)
    out["real_dur"] = out["real_mjd_last"] - out["real_mjd_first"]
    has_lcl = out["lcl_dur_med"].notna()
    has_ctrl = out["ctrl_dur_med"].notna()

    out_dir = HERE / f"shape_output_{class_key.lower().replace('-', '')}"
    out_dir.mkdir(exist_ok=True)
    out.to_parquet(out_dir / "objects.parquet", index=False)

    summary = dict(
        class_key=class_key, n_objects=len(out), n_seeds_per_object=20,
        resid_med_all=float(out["resid_med"].median()),
        resid_med_near_peak=float(out["resid_near_peak"].median(skipna=True)),
        lcl_detect_rate_mean=float(out["lcl_detect_rate"].mean()),
        ctrl_detect_rate_mean=float(out["ctrl_detect_rate"].mean()),
        real_dur_median=float(out["real_dur"].median()),
        lcl_dur_median=float(out.loc[has_lcl, "lcl_dur_med"].median()) if has_lcl.any() else None,
        ctrl_dur_median=float(out.loc[has_ctrl, "ctrl_dur_med"].median()) if has_ctrl.any() else None,
        delta_dur_lcl_minus_real_median=float(
            (out.loc[has_lcl, "lcl_dur_med"] - out.loc[has_lcl, "real_dur"]).median()
        ) if has_lcl.any() else None,
        delta_dur_ctrl_minus_real_median=float(
            (out.loc[has_ctrl, "ctrl_dur_med"] - out.loc[has_ctrl, "real_dur"]).median()
        ) if has_ctrl.any() else None,
        frac_lcl_dur_longer=float(
            (out.loc[has_lcl, "lcl_dur_med"] > out.loc[has_lcl, "real_dur"]).mean()
        ) if has_lcl.any() else None,
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"[{time.time()-t_start:.1f}s] terminado, {len(out)} objetos -> {out_dir}")


if __name__ == "__main__":
    class_key = sys.argv[1] if len(sys.argv) > 1 else "ILOT-MOSFIT"
    n_objects = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(class_key, n_objects)
