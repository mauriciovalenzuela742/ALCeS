"""
fase11_zgrid_compare.py -- Fase 11: compara el flujo que SNANA interpola en
su grilla SIMSED (log-z x fase, GENMODEL_MSKOPT: 512) contra la evaluacion
continua de LightCurveLynx (evaluate_bandfluxes(), sin discretizar z) para
los MISMOS (ISED, Trest, z) reales que SNANA genero -- sin correr
simulate_lightcurves() ni ninguna poblacion Monte Carlo del lado LCL, un
objeto/template a la vez.

Diseno (ver NOTES.md Fase 11 para el razonamiento completo):
- El lado SNANA (`Sinterp`, volcado por GENMODEL_MSKOPT: 512) es el flujo
  interpolado en la grilla, ANTES del escalado por `x0` (que aplica el
  termino de distancia/modulo de distancia, una funcion suave de z sin
  relacion con la interpolacion de grilla).
- Del lado LCL, se evalua cada punto con `distance=10.0` (pc) fijo -- NO la
  distancia luminosa real dependiente de z -- para excluir el mismo termino
  de distancia que `x0` excluye en Sinterp (10 pc hace que el factor
  `(10/distance_pc)**2` de `SIMSEDModel.compute_sed()` sea exactamente 1,
  la convencion estandar de magnitud absoluta).
- Con eso, `mag_SNANA - mag_LCL` en cada punto individual ya aisla el error
  de interpolacion de grilla (mas un offset CONSTANTE de normalizacion de
  unidades entre ambos codigos) -- no hace falta ninguna regresion/ajuste
  suave por grupo de template, porque LCL nunca discretiza z (su
  RectBivariateSpline es solo fase x longitud de onda), asi que su valor ya
  sirve de referencia "continua" punto a punto.
- El offset constante se calibra con la mediana de `mag_SNANA - mag_LCL`
  SOLO en los puntos cerca de un nodo de la grilla (frac~0 o ~1), donde la
  interpolacion de SNANA es exacta por construccion -- evita que la propia
  señal buscada sesgue su calibracion.

Uso:
    python3 fase11_zgrid_compare.py SNIa-91bg
    python3 fase11_zgrid_compare.py SLSN-I-MOSFIT
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lightcurvelynx.models.sed_template_model import SIMSEDModel
from lightcurvelynx.astro_utils.passbands import PassbandGroup
# Fase 74: SNANA_HOME resuelto por local_env.py (portabilidad).
from local_env import SNANA_HOME

HERE = Path(__file__).resolve().parent
LOGDIR = HERE / "fase11_simsed_zgrid"

MAG_AB_ZP_NJY = 8.9 + 2.5 * 9  # mismo convenio que compare_brightness_truth.py (Fase 7)
REF_DISTANCE_PC = 10.0  # excluye el termino de distancia, igual que Sinterp excluye x0
NODE_TOL = 0.03  # +-3% del ancho de celda alrededor de frac=0/1 para calibrar el offset

CLASS_CONFIGS = {
    "SNIa-91bg": dict(
        log_path=LOGDIR / "debug_SNIa91bg.log",
        # SED.INFO real no parsea con yaml.safe_load() (bug conocido, ver
        # setup_simsed_91bg_local.py) -- se usa la copia local saneada, con
        # el mismo orden de lineas SED: (verificado con diff antes de
        # escribir este script) para que ISED de SNANA siga mapeando 1:1 a
        # templates[ISED-1] aqui.
        simsed_dir=str(HERE / "simsed_91bg_local"),
        z_anchor=0.011,
        logzbin=0.02,
        band="r",
    ),
    "SLSN-I-MOSFIT": dict(
        log_path=LOGDIR / "debug_SLSNIMOSFIT.log",
        simsed_dir=str(SNANA_HOME / "run_SNANA/plasticc_models/SIMSED.SLSN-I-MOSFIT"),
        z_anchor=0.02,
        logzbin=0.1,
        band="r",
    ),
}

# "xxx Nobs=%d  ifilt_obs=%d z=%.3f  DAYMAX_ALL=%.1f  lumipar=%.1f" (una vez por evento)
EVENT_RE = re.compile(r"xxx Nobs=(\d+)\s+ifilt_obs=(\d+)\s+z=([\d.]+)\s+DAYMAX_ALL=([-\d.]+)")
# "xxx Trest=%8.2f  x0=%9.3le   Sinterp=%9.3le  ISED=%d  DAYMAX=%.1f" (una vez por epoca real)
EPOCH_RE = re.compile(
    r"xxx Trest=\s*([-\d.]+)\s+x0=\s*([\d.eE+-]+)\s+Sinterp=\s*([\d.eE+-]+)\s+ISED=(\d+)"
)


def parse_debug_log(log_path: Path) -> pd.DataFrame:
    """z se imprime una vez por evento (linea 'Nobs=...'); se propaga hacia
    adelante a cada linea de epoca ('Trest=...Sinterp=...ISED=...') hasta el
    siguiente evento."""
    rows = []
    current_z = None
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m_event = EVENT_RE.search(line)
            if m_event:
                current_z = float(m_event.group(3))
                continue
            m_epoch = EPOCH_RE.search(line)
            if m_epoch and current_z is not None:
                trest, x0, sinterp, ised = m_epoch.groups()
                rows.append(dict(
                    z=current_z, trest=float(trest), x0=float(x0),
                    sinterp=float(sinterp), ised=int(ised),
                ))
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(
            f"No se encontraron lineas de debug en {log_path} -- revisar que "
            f"GENMODEL_MSKOPT: 512 este activo en el .INPUT real usado."
        )
    return df


def lcl_flux_njy(full_model, ised: int, z: float, trest: float, passband_group, band: str) -> float:
    """Evalua evaluate_bandfluxes() para UN template (SNANA ISED, 1-based)
    a una redshift/fase exactas, con distancia fija en 10 pc (referencia
    absoluta, ver docstring del modulo). No usa simulate_lightcurves() ni
    ninguna poblacion -- un solo objeto sintetico por llamada."""
    template = full_model.templates[ised - 1]
    one = SIMSEDModel(
        templates=[template], flux_scale=full_model.flux_scale,
        redshift=float(z), distance=REF_DISTANCE_PC, t0=0.0,
    )
    times = np.array([trest * (1.0 + z)])  # obs-frame: (times-t0)/(1+z) == trest
    flux = one.evaluate_bandfluxes(passband_group, times, np.array([band]), state=None)
    return float(flux[0])


def main(class_key: str) -> None:
    cfg = CLASS_CONFIGS[class_key]

    df = parse_debug_log(cfg["log_path"])
    print(f"[{class_key}] {len(df)} filas de debug parseadas, "
          f"{df['ised'].nunique()} ISED distintos, "
          f"z en [{df['z'].min():.5f}, {df['z'].max():.5f}]")

    print(f"[{class_key}] cargando templates SIMSED completos (una sola vez, "
          f"para poder indexar por ISED)...")
    full_model = SIMSEDModel.from_dir(cfg["simsed_dir"], redshift=0.0, distance=REF_DISTANCE_PC, t0=0.0)
    passband_group = PassbandGroup.from_preset(preset="LSST")

    df["flux_lcl_njy"] = [
        lcl_flux_njy(full_model, row.ised, row.z, row.trest, passband_group, cfg["band"])
        for row in df.itertuples()
    ]

    df["mag_snana"] = -2.5 * np.log10(df["sinterp"].clip(lower=1e-30))
    df["mag_lcl"] = MAG_AB_ZP_NJY - 2.5 * np.log10(df["flux_lcl_njy"].clip(lower=1e-30))
    df["raw_delta"] = df["mag_snana"] - df["mag_lcl"]

    log10z_anchor = np.log10(cfg["z_anchor"])
    df["frac"] = ((np.log10(df["z"]) - log10z_anchor) / cfg["logzbin"]) % 1.0

    near_node = (df["frac"] < NODE_TOL) | (df["frac"] > 1 - NODE_TOL)
    n_calib = int(near_node.sum())
    offset = df.loc[near_node, "raw_delta"].median() if n_calib >= 5 else df["raw_delta"].median()
    print(f"[{class_key}] offset constante calibrado con {n_calib} puntos cerca de un nodo "
          f"(|frac| dentro de {NODE_TOL}): {offset:.4f} mag")

    df["delta_mag"] = df["raw_delta"] - offset

    bins = np.linspace(0, 1, 11)
    df["frac_bin"] = pd.cut(df["frac"], bins, include_lowest=True)
    summary = df.groupby("frac_bin", observed=True)["delta_mag"].agg(["mean", "sem", "count"])
    print(f"\n[{class_key}] Delta(frac) por bin (mag, SNANA - LCL, offset ya restado):")
    print(summary.to_string(float_format=lambda x: f"{x:.4f}"))

    out_csv = HERE / f"fase11_zgrid_{class_key.replace(' ', '_').replace('/', '_')}.csv"
    df.to_csv(out_csv, index=False)
    print(f"\n[{class_key}] CSV completo ({len(df)} filas): {out_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CLASS_CONFIGS:
        print(f"uso: python3 fase11_zgrid_compare.py <clase>  (clases: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    main(sys.argv[1])
