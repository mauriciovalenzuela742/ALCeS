"""
Fase 7 -- agrupa por bin de redshift la salida de compare_brightness_truth.py
contra PEAKMAG_* real del .DUMP de SNANA -- produce la tabla reportada en
NOTES.md/docs/index.html.

Fase 48: filtro de contaminacion de campo (filter_ddf_field_contamination,
snana_params.py -- ver NOTES.md Fase 36/48, causa raiz real: el SIMLIB de
produccion incluye el campo RGES del Roman Galactic Exoplanet Survey bajo el
mismo prefijo "DD:" que los 6 campos DDF reales) portado a este script
versionado, aplicado antes de binear. Reproduce el -0.068 mag de Fase 47
para SNIa-91bg con el control positivo generalizado (ver Fase 50).

Fase 50: generalizado para aceptar cualquier clase (antes hardcodeado a
SNIa-91bg / banda r unica) -- 7 bins equi-anchos sobre el GENRANGE_REDSHIFT
real de la clase (CLASS_CONFIGS), las 6 bandas LSST, bin 1 se reporta pero
no se promedia (mismo criterio de Fases 20/22/47). El nombre de carpeta del
.DUMP real no siempre coincide con la clave de CLASS_CONFIGS (ver Fase 48:
TDE-MOSFIT->TDE, ILOT-MOSFIT->ILOT) -- DUMP_FOLDER_OVERRIDES documenta las
excepciones ya confirmadas; SNIax y CaRT coinciden literalmente (confirmado
por listado real de ~/DATASIM_LSST_1/DDF/SIMDv8/).

Uso (despues de correr compare_brightness_truth.py <clase>):
    python3 compare_brightness_truth_binned.py <clase>
"""
import sys
sys.path.insert(0, ".")
from compare_brightness import read_snana_dump
from run_simsed_poc import CLASS_CONFIGS
from snana_params import filter_ddf_field_contamination
# Fase 74: SNANA_HOME/REPO_ROOT resueltos por local_env.py (portabilidad).
from local_env import SNANA_HOME, REPO_ROOT
import pandas as pd
import numpy as np

OPSIM_DB = str(REPO_ROOT / "data/opsim/baseline_v5.3.1_10yrs.db")
DATASIM_DIR = str(SNANA_HOME / "DATASIM_LSST_1/DDF/SIMDv8")

DUMP_FOLDER_OVERRIDES = {
    "TDE-MOSFIT": "TDE",
    "ILOT-MOSFIT": "ILOT",
}

BANDS = ["u", "g", "r", "i", "z", "y"]
SNANA_COL = {"u": "PEAKMAG_u", "g": "PEAKMAG_g", "r": "PEAKMAG_r",
             "i": "PEAKMAG_i", "z": "PEAKMAG_z", "y": "PEAKMAG_Y"}


def main(class_key: str):
    if class_key not in CLASS_CONFIGS:
        print(f"uso: python3 compare_brightness_truth_binned.py <clase>  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    cfg = CLASS_CONFIGS[class_key]
    z_min, z_max = cfg["genrange_redshift"]
    dump_folder = DUMP_FOLDER_OVERRIDES.get(class_key, class_key)
    dump_path = f"{DATASIM_DIR}/{dump_folder}_DDF_baseline_v5.3.1_10yrs/{dump_folder}_DDF_baseline_v5.3.1_10yrs.DUMP"

    snana = read_snana_dump(dump_path)
    n_before = len(snana)
    snana = filter_ddf_field_contamination(snana, OPSIM_DB, max_sep_deg=2.0)
    print(f"[{class_key}] Filtro de contaminacion de campo (Fase 36/47/48): {n_before - len(snana)}/{n_before} "
          f"objetos removidos ({100 * (n_before - len(snana)) / n_before:.1f}%)")

    lcl_path = f"compare_brightness_truth_{class_key.lower().replace('-', '')}_output.parquet"
    lcl = pd.read_parquet(lcl_path)
    z_l_all = lcl["z"].to_numpy()

    bins = np.linspace(z_min, z_max, 8)
    deltas_bins2_7 = {b: [] for b in BANDS}

    for band in BANDS:
        scol = SNANA_COL[band]
        if scol not in snana.columns:
            print(f"\n=== banda {band}: columna {scol} ausente en el .DUMP, se omite ===")
            continue
        z_s = snana["ZHELIO"].to_numpy()
        mag_s = snana[scol].to_numpy()
        valid_s = (mag_s > -8) & (mag_s < 90) & np.isfinite(mag_s)
        z_s_v, mag_s_v = z_s[valid_s], mag_s[valid_s]

        lcol = f"PEAKMAG_{band}_true"
        mag_l_all = lcl[lcol].to_numpy()
        valid_l = np.isfinite(mag_l_all)
        z_l_v, mag_l_v = z_l_all[valid_l], mag_l_all[valid_l]

        print(f"\n=== banda {band} ===")
        print(f"{'z_bin':>18s} {'N_snana':>8s} {'med_snana':>10s} {'N_lcl':>8s} {'med_lcl':>10s} {'delta':>10s}")
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            ms = (z_s_v >= lo) & (z_s_v < hi)
            ml = (z_l_v >= lo) & (z_l_v < hi)
            ns, nl = ms.sum(), ml.sum()
            meds = np.median(mag_s_v[ms]) if ns > 0 else float("nan")
            medl = np.median(mag_l_v[ml]) if nl > 0 else float("nan")
            d = medl - meds if (ns > 0 and nl > 0) else float("nan")
            print(f"[{lo:.3f},{hi:.3f})  {ns:8d} {meds:10.3f} {nl:8d} {medl:10.3f} {d:10.3f}")
            if i >= 1 and np.isfinite(d):
                deltas_bins2_7[band].append(d)

        print(f"GLOBAL SNANA:", "N=", len(mag_s_v), "median=", round(float(np.median(mag_s_v)), 3))
        print(f"GLOBAL LCL (true, noiseless):", "N=", len(mag_l_v), "median=", round(float(np.median(mag_l_v)), 3))

    print(f"\n=== [{class_key}] delta medio bins 2-7 por banda ===")
    for band in BANDS:
        ds = deltas_bins2_7[band]
        if ds:
            print(f"  {band}: {np.mean(ds):+.3f} mag (N_bins={len(ds)})")
        else:
            print(f"  {band}: sin datos")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"uso: python3 compare_brightness_truth_binned.py <clase>  (opciones: {list(CLASS_CONFIGS)})")
        sys.exit(1)
    main(sys.argv[1])
