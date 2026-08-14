"""
Fase 7 -- agrupa por bin de redshift la salida de compare_brightness_truth.py
(compare_brightness_truth_output.parquet) contra PEAKMAG_r real del .DUMP de
SNANA -- produce la tabla reportada en NOTES.md/docs/index.html.

Uso (despues de correr compare_brightness_truth.py):
    python3 compare_brightness_truth_binned.py
"""
import sys
sys.path.insert(0, ".")
from compare_brightness import read_snana_dump
import pandas as pd
import numpy as np

SNANA_DUMP = (
    "/home/mvalenzuela/DATASIM_LSST_1/DDF/SIMDv8/SNIa-91bg_DDF_baseline_v5.3.1_10yrs/"
    "SNIa-91bg_DDF_baseline_v5.3.1_10yrs.DUMP"
)


def main():
    snana = read_snana_dump(SNANA_DUMP)
    z_s = snana["ZHELIO"].to_numpy()
    mag_s = snana["PEAKMAG_r"].to_numpy()
    valid = (mag_s > -8) & (mag_s < 90) & np.isfinite(mag_s)
    z_s, mag_s = z_s[valid], mag_s[valid]

    lcl = pd.read_parquet("compare_brightness_truth_output.parquet")
    z_l = lcl["z"].to_numpy()
    mag_l = lcl["PEAKMAG_r_true"].to_numpy()

    bins = np.linspace(0.011, 0.6, 8)
    print(f"{'z_bin':>18s} {'N_snana':>8s} {'med_snana':>10s} {'N_lcl':>8s} {'med_lcl':>10s} {'delta':>10s}")
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        ms = (z_s >= lo) & (z_s < hi)
        ml = (z_l >= lo) & (z_l < hi)
        ns, nl = ms.sum(), ml.sum()
        meds = np.median(mag_s[ms]) if ns > 0 else float("nan")
        medl = np.median(mag_l[ml]) if nl > 0 else float("nan")
        d = medl - meds if (ns > 0 and nl > 0) else float("nan")
        print(f"[{lo:.3f},{hi:.3f})  {ns:8d} {meds:10.3f} {nl:8d} {medl:10.3f} {d:10.3f}")

    print()
    print("GLOBAL SNANA:", "N=", len(mag_s), "median=", round(float(np.median(mag_s)), 3),
          "mean=", round(float(np.mean(mag_s)), 3), "std=", round(float(np.std(mag_s)), 3))
    print("GLOBAL LCL (true, noiseless):", "N=", len(mag_l), "median=", round(float(np.median(mag_l)), 3),
          "mean=", round(float(np.mean(mag_l)), 3), "std=", round(float(np.std(mag_l)), 3))


if __name__ == "__main__":
    main()
