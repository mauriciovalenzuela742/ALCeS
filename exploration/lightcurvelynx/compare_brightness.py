"""
Fase 7 -- comparacion directa de brillo simulado (PEAKMAG) entre SNANA real
y LightCurveLynx, ANTES de aplicar SEARCHEFF -- decoupled de todo lo
investigado en Fase 3/4/6 (extincion, trigger de epoca, SEARCHEFF/encoding),
que son todos del lado de deteccion, no del lado de fisica/fotometria
simulada. Compara la poblacion COMPLETA generada (NGENTOT), no solo los
detectados -- SNANA: "SELECTION: NONE (write every generated event)" en el
header del .DUMP real.

Uso: python3 compare_brightness.py <snana_dump_path> <lcl_poc_output_dir> <label>

NOTA (ver NOTES.md Fase 7): esta version compara PEAKMAG_r real de SNANA
(sin ruido) contra el MINIMO de magnitud observada CON RUIDO de LCL --
introduce un sesgo tipo Eddington (mas fuerte a bajo SNR/alto z) que
fabrico un patron de "LCL mucho mas brillante a alto z" que resulto ser en
gran parte artefacto de la metrica, no una diferencia real entre
simuladores. Ver compare_brightness_truth.py para la version corregida
(usa flux_perfect, sin ruido, de ambos lados). Se deja este script tal
cual como referencia del hallazgo metodologico, no se borra el error.
"""
import sys
import numpy as np
import pandas as pd

VARNAMES = None


def read_snana_dump(path):
    global VARNAMES
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("VARNAMES:"):
                VARNAMES = line.split()[1:]
                break
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("SN:"):
                rows.append(line.split()[1:])
    df = pd.DataFrame(rows, columns=VARNAMES)
    for c in df.columns:
        if c not in ("CID",):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def lcl_peak_mag_per_band(phot_df, band):
    sub = phot_df[(phot_df["FLT"] == band) & (phot_df["FLUXCAL"] > 0)]
    peak = sub.groupby("SNID")["MAG"].min()  # min mag = brightest = peak
    return peak


def main():
    snana_dump_path, lcl_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]

    snana = read_snana_dump(snana_dump_path)
    print(f"[{label}] SNANA DUMP: {len(snana)} objetos (poblacion COMPLETA, NGENTOT real)")

    head = pd.read_parquet(f"{lcl_dir}/head_df.parquet")
    phot = pd.read_parquet(f"{lcl_dir}/phot_df.parquet")
    print(f"[{label}] LCL head_df: {len(head)} objetos con obs (de NGENTOT real, ver summary.json)")

    lcl_peak_r = lcl_peak_mag_per_band(phot, "r")
    head = head.set_index("SNID")
    head["PEAKMAG_r_LCL"] = lcl_peak_r
    lcl_valid = head.dropna(subset=["PEAKMAG_r_LCL"])
    print(f"[{label}] LCL objetos con al menos 1 obs r-band positiva: {len(lcl_valid)}")

    z_snana = snana["ZHELIO"].to_numpy()
    mag_snana = snana["PEAKMAG_r"].to_numpy()
    valid_snana = (mag_snana > -8) & (mag_snana < 90) & np.isfinite(mag_snana)
    z_snana, mag_snana = z_snana[valid_snana], mag_snana[valid_snana]

    z_lcl = lcl_valid["REDSHIFT_HELIO"].to_numpy()
    mag_lcl = lcl_valid["PEAKMAG_r_LCL"].to_numpy()

    z_min = min(z_snana.min(), z_lcl.min())
    z_max = max(z_snana.max(), z_lcl.max())
    bins = np.linspace(z_min, z_max, 8)

    print(f"\n[{label}] === PEAKMAG_r por bin de redshift (mediana) ===")
    print(f"{'z_bin':>18s} {'N_snana':>8s} {'med_snana':>10s} {'N_lcl':>8s} {'med_lcl':>10s} {'delta(LCL-SNANA)':>18s}")
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        m_s = (z_snana >= lo) & (z_snana < hi)
        m_l = (z_lcl >= lo) & (z_lcl < hi)
        n_s, n_l = m_s.sum(), m_l.sum()
        med_s = np.median(mag_snana[m_s]) if n_s > 0 else float("nan")
        med_l = np.median(mag_lcl[m_l]) if n_l > 0 else float("nan")
        delta = med_l - med_s if (n_s > 0 and n_l > 0) else float("nan")
        print(f"[{lo:6.3f},{hi:6.3f})  {n_s:8d} {med_s:10.3f} {n_l:8d} {med_l:10.3f} {delta:18.3f}")

    print(f"\n[{label}] === global (todos los bins combinados) ===")
    print(f"SNANA: N={len(mag_snana)}, mediana PEAKMAG_r={np.median(mag_snana):.3f}, "
          f"media={np.mean(mag_snana):.3f}, std={np.std(mag_snana):.3f}")
    print(f"LCL:   N={len(mag_lcl)}, mediana PEAKMAG_r={np.median(mag_lcl):.3f}, "
          f"media={np.mean(mag_lcl):.3f}, std={np.std(mag_lcl):.3f}")


if __name__ == "__main__":
    main()
