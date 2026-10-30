"""Agente 2, paso 3: muestra de SN despojadas (IIb, Ib, Ic, Ic-BL) de CSP-I homogeneizada.

Uso:
    python build_csp_sesn.py [--out out/csp_sesn]

Requiere la descarga de Stritzinger+18a (J/A+A/609/A134) y la fuente LaTeX de Stritzinger+18b
en catalog/objects/raw/csp1_se_photometry_stritzinger18 (si falta, correr
catalog/objects/scripts/csp1_se_photometry_stritzinger18.py). Escribe:

- sample.csv: una fila por SN (34): tipo, z heliocentrico, T(B)max, E(B-V)_MW y E(B-V)_host.
- photometry.csv: fotometria optica y NIR en AB, corregida por la Via Lactea (CCM89 +
  O'Donnell94, R_V = 3.1, en la lambda_eff del filtro) y con fase en reposo desde el maximo
  en B. Flujo f_nu en microJansky. Sin correccion K ni de extincion del host (el E(B-V)_host
  queda en sample.csv para cuando se decida como usarlo).

Mismo sistema y misma correccion que build_csp_snii.py, para que ambas muestras sean
comparables. Diferencias con las SNII:
- La fase se mide desde T(B)max, porque Stritzinger+18 no da epocas de explosion.
- E(B-V)_MW no esta en el paper: se consulta el servicio DUST de IRSA (Schlafly & Finkbeiner
  2011, el mismo que usa Gutierrez+17 para las SNII) en las coordenadas de table1, y se guarda
  en out/csp_sesn/ebv_mw_irsa.csv para no repetir la consulta.
- No hay espectros opticos publicos de CSP-I para estas SNe en el catalogo.
"""
import argparse
import math
import os
import re
import sys
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "catalog", "objects", "scripts")
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

import csp_system  # noqa: E402
from extinction import a_lambda  # noqa: E402
from _common import RAW  # noqa: E402
import _stripped_util as u  # noqa: E402
import csp1_se_photometry_stritzinger18 as s18  # noqa: E402

S18 = os.path.join(RAW, "csp1_se_photometry_stritzinger18")
JD_OFFSET = 2450000.0  # T(B)max viene como JD - 2450000
OPT = ["u", "g", "r", "i", "B", "V"]
NIR = ["Y", "J", "H"]
# Tabla -> (sistema de csp_system, bandas). table5 (du Pont + Tek5) no tiene calibracion AB
# en la pagina de CSP: queda con NaN, como en las SNII. table6 es J(RC1) y table7 J(RC2):
# csp_system las separa por fecha (table7 empieza en MJD 54846, el dia del cambio).
TABLES = {4: ("Swope+Site3", OPT), 5: ("duPont+TEK5", OPT), 6: ("Swope+RetroCam", NIR),
          7: ("Swope+RetroCam", NIR), 8: ("duPont+WIRC", NIR)}
IRSA = "https://irsa.ipac.caltech.edu/cgi-bin/DUST/nph-dust?locstr={ra:.5f}+{dec:.5f}+equ+j2000&regSize=2.0"


def read_sample():
    rows = []
    for ln in open(os.path.join(S18, "table1.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        tmax = u.ffloat(u.fw(ln, 129, 135))
        rows.append({
            "sn": u.fw(ln, 1, 6),
            "type": u.fw(ln, 113, 118),
            "ra": u.sexa_ra(u.fw(ln, 8, 9), u.fw(ln, 11, 12), u.fw(ln, 14, 18)),
            "dec": u.sexa_dec(u.fw(ln, 20, 20), u.fw(ln, 21, 22), u.fw(ln, 24, 25),
                              u.fw(ln, 27, 30)),
            "z_helio": u.ffloat(u.fw(ln, 76, 81)),
            "tbmax_mjd": tmax + JD_OFFSET - 2400000.5 if tmax is not None else math.nan,
            "tbmax_err_d": u.ffloat(u.fw(ln, 137, 140)),
            # 'd': T(B)max de la relacion de la fig. 3 de Taddia+18, no medido directamente.
            "tbmax_from_relation": u.fw(ln, 141, 141) == "d",
        })
    return pd.DataFrame(rows)


def read_photometry(path, system, bands, start=20):
    """Magnitudes cada 14 bytes desde `start`; error 7 bytes despues; '---' = sin dato."""
    rows = []
    for ln in open(path, encoding="latin-1"):
        if not ln.strip():
            continue
        sn, jd = u.fw(ln, 1, 6), float(u.fw(ln, 8, 17))
        for k, b in enumerate(bands):
            a = start + 14 * k
            mag, err = u.ffloat(u.fw(ln, a, a + 5)), u.ffloat(u.fw(ln, a + 7, a + 11))
            if mag is not None:
                rows.append((sn, jd, b, system, mag, err if err is not None else math.nan))
    return pd.DataFrame(rows, columns=["sn", "jd", "band", "system", "mag_nat", "mag_err"])


def parse_irsa(xml):
    m = re.search(r"<refPixelValueSandF>\s*([0-9.]+)\s*\(mag\)", xml)
    return float(m.group(1)) if m else math.nan


def ebv_mw(sample, cache):
    """E(B-V) de Schlafly & Finkbeiner (2011) desde IRSA, con cache en CSV."""
    have = pd.read_csv(cache, dtype={"sn": str}) if os.path.exists(cache) else \
        pd.DataFrame(columns=["sn", "ebv_mw"])
    known = dict(zip(have["sn"], have["ebv_mw"]))
    for r in sample.itertuples():
        if r.sn in known and not math.isnan(known[r.sn]):
            continue
        with urllib.request.urlopen(IRSA.format(ra=r.ra, dec=r.dec), timeout=120) as f:
            known[r.sn] = parse_irsa(f.read().decode("utf-8", "replace"))
    pd.DataFrame(sorted(known.items()), columns=["sn", "ebv_mw"]).to_csv(cache, index=False)
    return sample["sn"].map(known)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "csp_sesn"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    sample = read_sample()
    sample["ebv_mw"] = ebv_mw(sample, os.path.join(args.out, "ebv_mw_irsa.csv"))
    ebvh = s18.read_ebv_host(S18)
    sample["ebv_host_s18b"] = sample["sn"].map(ebvh)
    sample = sample.set_index("sn")

    ph = pd.concat([read_photometry(os.path.join(S18, f"table{t}.dat"), sys_, bands)
                    for t, (sys_, bands) in TABLES.items()], ignore_index=True)
    ph["mjd"] = ph["jd"] - 2400000.5
    looked = [csp_system.lookup(s, b, m) for s, b, m in zip(ph["system"], ph["band"], ph["mjd"])]
    ph["filter"] = [x[0] for x in looked]
    ph["lambda_eff"] = [x[1] for x in looked]
    ph["ab_offset"] = [x[2] for x in looked]
    ph["mag_ab"] = ph["mag_nat"] + ph["ab_offset"]
    ph["a_mw"] = a_lambda(ph["lambda_eff"].to_numpy(), ph["sn"].map(sample["ebv_mw"]).to_numpy())
    ph["mag_ab_mwcorr"] = ph["mag_ab"] - ph["a_mw"]
    ph["fnu_ujy"] = 10 ** (-0.4 * (ph["mag_ab_mwcorr"] - 23.9))
    ph["fnu_err_ujy"] = ph["fnu_ujy"] * ph["mag_err"] * math.log(10) / 2.5
    z = ph["sn"].map(sample["z_helio"])
    ph["phase_rest"] = (ph["mjd"] - ph["sn"].map(sample["tbmax_mjd"])) / (1 + z)
    ph["lambda_rest"] = ph["lambda_eff"] / (1 + z)
    ph["type"] = ph["sn"].map(sample["type"])
    ph = ph.drop(columns=["jd"])
    ph.to_csv(os.path.join(args.out, "photometry.csv"), index=False, float_format="%.5g")

    ok = ph[ph["mag_ab"].notna()]
    sample["n_phot"] = ok.groupby("sn").size().reindex(sample.index).fillna(0).astype(int)
    sample["n_nights_opt"] = (ok[ok["band"].isin(OPT)].assign(n=ok["mjd"].round())
                              .groupby("sn")["n"].nunique().reindex(sample.index).fillna(0).astype(int))
    sample["bands"] = ok.groupby("sn")["band"].agg(
        lambda s: ";".join(b for b in OPT + NIR if b in set(s))).reindex(sample.index).fillna("")
    opt = ok[ok["band"].isin(OPT)]
    sample["phase_min_opt"] = opt.groupby("sn")["phase_rest"].min().reindex(sample.index)
    sample["phase_max_opt"] = opt.groupby("sn")["phase_rest"].max().reindex(sample.index)
    sample.reset_index().to_csv(os.path.join(args.out, "sample.csv"), index=False, float_format="%.6g")

    print(f"sample: {len(sample)} SNe ({sample['type'].value_counts().to_dict()}); "
          f"E(B-V)_MW: {sample['ebv_mw'].notna().sum()}; E(B-V)_host: {sample['ebv_host_s18b'].notna().sum()}")
    print(f"fotometria: {len(ph)} puntos (opt {ph['band'].isin(OPT).sum()}, NIR {ph['band'].isin(NIR).sum()}); "
          f"sin calibracion AB: {ph['ab_offset'].isna().sum()} "
          f"({sorted(ph.loc[ph['ab_offset'].isna(), 'system'].unique())})")
    print(f"con maximo cubierto (fase < 0 en optico): {(sample['phase_min_opt'] < 0).sum()}; "
          f"desde 5 d antes: {(sample['phase_min_opt'] <= -5).sum()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
