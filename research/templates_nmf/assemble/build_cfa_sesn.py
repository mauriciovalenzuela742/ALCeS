"""Agente 2, paso 3b: SN despojadas de CfA (Bianco+14) en el mismo formato que las de CSP-I.

Uso:
    python build_cfa_sesn.py [--out out/cfa_sesn]

Requiere la descarga de Bianco+14 (J/ApJS/213/19) en
catalog/objects/raw/cfa_sesn_photometry_bianco14 (si falta, correr
catalog/objects/scripts/cfa_sesn_photometry_bianco14.py). La fuente LaTeX del paper
(arXiv:1405.1428) se baja sola: de ahi salen las fechas de maximo, que VizieR no trae.
Escribe:

- sample.csv: una fila por SN (64): tipo, z del host, T(B)max y de donde sale, E(B-V)_MW y si
  la SN tambien esta en CSP-I.
- photometry.csv: fotometria optica y NIR en AB, corregida por la Via Lactea (CCM89 +
  O'Donnell94, R_V = 3.1, en la lambda_eff del filtro), con fase en reposo desde T(B)max.

Diferencias con build_csp_sesn.py:
- Se usa la fotometria en el sistema estandar (table6), no la natural: CfA no publica curvas
  de transmision por camara para pasar la natural a AB. Vega -> AB y lambda_eff de UBVRI
  (Bessell 1990) y JHKs (2MASS) salen de la tabla 1 de Blanton & Roweis (2007); u'r'i' (SDSS,
  Smith+02) ya estan en AB.
- Bianco+14 da el maximo en V (tabla 4). Para comparar con CSP-I la fase va desde T(B)max: se
  usa el maximo en B si esta medido, y si no el de otra banda corrido por la mediana del
  desfase respecto de V de la tabla 7 de Bianco+14, sumando su dispersion al error.
- E(B-V)_MW viene en table2 (Schlafly & Finkbeiner 2011, el mismo mapa que IRSA).
"""
import argparse
import datetime as dt
import math
import os
import re
import sys
import tarfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "catalog", "objects", "scripts")
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

from mw_extinction import a_lambda  # noqa: E402
from _common import RAW  # noqa: E402
import _stripped_util as u  # noqa: E402

B14 = os.path.join(RAW, "cfa_sesn_photometry_bianco14")
ARXIV = "1405.1428"
C_KMS = 299792.458
# Banda de table6 -> (sistema, lambda_eff [A], m_AB - m_Vega), de Blanton & Roweis 2007, tabla 1.
BANDS = {
    "U": ("Landolt", 3571.0, 0.79), "B": ("Landolt", 4344.0, -0.09),
    "V": ("Landolt", 5456.0, 0.02), "R": ("Landolt", 6442.0, 0.21),
    "I": ("Landolt", 7994.0, 0.45),
    "u'": ("SDSS", 3546.0, 0.0), "r'": ("SDSS", 6156.0, 0.0), "i'": ("SDSS", 7472.0, 0.0),
    "J": ("2MASS", 12355.0, 0.91), "H": ("2MASS", 16458.0, 1.39), "Ks": ("2MASS", 21603.0, 1.85),
}
OPT = ["U", "u'", "B", "V", "R", "r'", "I", "i'"]
# Bianco+14, tabla 7: desfase del pico de cada banda respecto de T(V)max (mediana, dispersion).
PEAK_LAG = {"U": (-3.3, 2.1), "B": (-2.3, 1.3), "V": (0.0, 0.0), "R": (1.5, 1.3),
            "I": (3.1, 1.5), "J": (6.9, 3.3), "H": (9.8, 4.3), "K": (10.9, 5.0)}
# Orden de preferencia para estimar T(B)max cuando B no esta medido. Los picos NIR no se usan:
# su desfase respecto de V tiene 3-5 dias de dispersion, y el unico caso que dependeria de
# ellos (2004gk, solo J) da un maximo 115 dias despues del descubrimiento.
PEAK_ORDER = ["B", "V", "R", "I", "U"]
# Las despojadas suben en ~10-20 dias: un maximo mas de MAX_AFTER_DISC dias despues del
# descubrimiento es un error de la tabla (2004gt: B en 53388.52, CSP-I da 53359.6).
MAX_AFTER_DISC = 25.0
TYPES = {"Ib-pec": "Ib", "Ib-n": "Ibn", "Ib-n/IIb-n": "Ibn", "Ib (Ca rich)": "Ca-rich"}


def read_sample():
    rows = {}
    for ln in open(os.path.join(B14, "table1.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn, raw = u.fw(ln, 4, 9), u.fw(ln, 45, 56)
        disc = dt.datetime.strptime(u.fw(ln, 58, 68), "%Y %b %d")
        # VizieR repite fechas de otra SN en 2009jf y 2007aw: el anio no calza con el nombre.
        disc_mjd = (disc - dt.datetime(1858, 11, 17)).days if str(disc.year) == sn[:4] else math.nan
        rows[sn] = {
            "sn": sn, "type": TYPES.get(raw, raw), "type_raw": raw,
            "ra": u.sexa_ra(u.fw(ln, 24, 25), u.fw(ln, 27, 28), u.fw(ln, 30, 31)),
            "dec": u.sexa_dec(u.fw(ln, 33, 33), u.fw(ln, 34, 35), u.fw(ln, 37, 38),
                              u.fw(ln, 40, 43)),
            "disc_mjd": disc_mjd,
        }
    for ln in open(os.path.join(B14, "table2.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        r = rows[u.fw(ln, 4, 9)]
        r["z_helio"] = u.ffloat(u.fw(ln, 42, 46)) / C_KMS
        r["ebv_mw"] = u.ffloat(u.fw(ln, 105, 110))
    return pd.DataFrame(rows.values())


def parse_peaks(tex):
    """Tablas de maximos de Bianco+14 (maxdata_table.tex) -> {sn: {banda: (mjd, err)}}.

    Las fechas de la tabla son MJD aunque la columna diga JD (SN 2005bf: el texto da
    JD 2453498.96 y la tabla 53498.46). Las filas comentadas con % no tienen fechas
    confiables y se ignoran. Si una SN aparece dos veces (2005bf, doble maximo) se queda la
    primera, que es el primer pico, como en CSP-I.
    """
    peaks = {}
    heads = [["U", "B", "V"], ["R", "I"], ["J", "H", "K"]]
    blocks = re.findall(r"\\startdata(.*?)\\enddata", tex, re.S)
    for bands, body in zip(heads, blocks):
        for ln in body.splitlines():
            ln = ln.strip()
            if not ln.startswith("SN"):
                continue
            cells = [c.strip() for c in ln.rstrip("\\").split("&")]
            sn = re.sub(r"\\tablenotemark\{.*?\}", "", cells[0]).replace("SN~", "").replace("SN", "").strip()
            d = peaks.setdefault(sn, {})
            for k, b in enumerate(bands):
                m = re.match(r"([0-9.]+)\s*\(([0-9.]+)\)", cells[1 + 3 * k] if 1 + 3 * k < len(cells) else "")
                if m and b not in d:
                    d[b] = (float(m.group(1)), float(m.group(2)))
    return peaks


def tbmax_from_peaks(p):
    """(T(B)max, error, banda usada) a partir de los maximos medidos de una SN."""
    for b in PEAK_ORDER:
        if b in p:
            t, e = p[b]
            lag, sd = PEAK_LAG[b]
            if b == "B":
                return t, e, b
            return t - lag + PEAK_LAG["B"][0], float(np.sqrt(e ** 2 + sd ** 2 + PEAK_LAG["B"][1] ** 2)), b
    return math.nan, math.nan, ""


def read_tex():
    src = u.fetch(f"https://arxiv.org/e-print/{ARXIV}", os.path.join(B14, f"arXiv_{ARXIV}_src.tar.gz"))
    with tarfile.open(src, "r:gz") as tf:
        return tf.extractfile("maxdata_table.tex").read().decode("latin-1")


def read_photometry(path):
    rows = []
    for ln in open(path, encoding="latin-1"):
        if not ln.strip():
            continue
        rows.append((u.fw(ln, 1, 6), u.fw(ln, 8, 9), float(u.fw(ln, 11, 21)),
                     float(u.fw(ln, 23, 28)), u.ffloat(u.fw(ln, 30, 34)), u.fw(ln, 36, 44)))
    return pd.DataFrame(rows, columns=["sn", "band", "mjd", "mag_std", "mag_err", "code"])


def compare_csp(ph, csp_dir, max_dt=0.6):
    """Diferencia CfA - CSP en AB corregido por MW, mismo SN y misma noche, por banda."""
    path = os.path.join(csp_dir, "photometry.csv")
    if not os.path.exists(path):
        return None
    csp = pd.read_csv(path, dtype={"sn": str})
    pairs = {"B": "B", "V": "V", "r'": "r", "i'": "i"}
    out = []
    for bc, bs in pairs.items():
        a = ph[(ph["band"] == bc) & ph["mag_ab_mwcorr"].notna()].sort_values("mjd")
        b = csp[(csp["band"] == bs) & csp["mag_ab_mwcorr"].notna()].sort_values("mjd")
        m = pd.merge_asof(a, b[["sn", "mjd", "mag_ab_mwcorr"]], on="mjd", by="sn",
                          tolerance=max_dt, direction="nearest", suffixes=("", "_csp")).dropna(subset=["mag_ab_mwcorr_csp"])
        if len(m):
            d = m["mag_ab_mwcorr"] - m["mag_ab_mwcorr_csp"]
            out.append({"band": bc, "n": len(m), "n_sn": m["sn"].nunique(), "median": d.median(),
                        "mad": float(np.median(np.abs(d - d.median())))})
    return pd.DataFrame(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "cfa_sesn"))
    ap.add_argument("--csp", default=os.path.join(HERE, "out", "csp_sesn"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    sample = read_sample()
    peaks = parse_peaks(read_tex())
    t = [tbmax_from_peaks(peaks.get(sn, {})) for sn in sample["sn"]]
    sample["tbmax_mjd"] = [x[0] for x in t]
    sample["tbmax_err_d"] = [x[1] for x in t]
    sample["tbmax_band"] = [x[2] for x in t]
    late = sample["tbmax_mjd"] - sample["disc_mjd"] > MAX_AFTER_DISC
    sample["tbmax_rejected_mjd"] = sample["tbmax_mjd"].where(late)
    sample.loc[late, ["tbmax_mjd", "tbmax_err_d"]] = math.nan
    sample.loc[late, "tbmax_band"] = "rechazado"
    csp_sample = os.path.join(args.csp, "sample.csv")
    if os.path.exists(csp_sample):
        cs = pd.read_csv(csp_sample, dtype={"sn": str}).set_index("sn")
        sample["in_csp"] = sample["sn"].isin(cs.index)
        sample["tbmax_csp_mjd"] = sample["sn"].map(cs["tbmax_mjd"])
    sample = sample.set_index("sn")

    ph = read_photometry(os.path.join(B14, "table6.dat"))
    ph["system"] = ph["band"].map(lambda b: BANDS[b][0])
    ph["lambda_eff"] = ph["band"].map(lambda b: BANDS[b][1])
    ph["ab_offset"] = ph["band"].map(lambda b: BANDS[b][2])
    ph["mag_ab"] = ph["mag_std"] + ph["ab_offset"]
    ph["a_mw"] = a_lambda(ph["lambda_eff"].to_numpy(), ph["sn"].map(sample["ebv_mw"]).to_numpy())
    ph["mag_ab_mwcorr"] = ph["mag_ab"] - ph["a_mw"]
    ph["fnu_ujy"] = 10 ** (-0.4 * (ph["mag_ab_mwcorr"] - 23.9))
    ph["fnu_err_ujy"] = ph["fnu_ujy"] * ph["mag_err"] * math.log(10) / 2.5
    z = ph["sn"].map(sample["z_helio"])
    ph["phase_rest"] = (ph["mjd"] - ph["sn"].map(sample["tbmax_mjd"])) / (1 + z)
    ph["lambda_rest"] = ph["lambda_eff"] / (1 + z)
    ph["type"] = ph["sn"].map(sample["type"])
    # El MJD aparte: con %.5g perderia la fraccion del dia.
    ph.assign(mjd=ph["mjd"].map("{:.5f}".format)).to_csv(
        os.path.join(args.out, "photometry.csv"), index=False, float_format="%.5g")

    opt = ph[ph["band"].isin(OPT)]
    sample["n_phot"] = ph.groupby("sn").size().reindex(sample.index).fillna(0).astype(int)
    sample["n_nights_opt"] = (opt.assign(n=opt["mjd"].round()).groupby("sn")["n"].nunique()
                              .reindex(sample.index).fillna(0).astype(int))
    sample["bands"] = ph.groupby("sn")["band"].agg(
        lambda s: ";".join(b for b in BANDS if b in set(s))).reindex(sample.index).fillna("")
    sample["phase_min_opt"] = opt.groupby("sn")["phase_rest"].min().reindex(sample.index)
    sample["phase_max_opt"] = opt.groupby("sn")["phase_rest"].max().reindex(sample.index)
    sample.reset_index().assign(tbmax_mjd=sample["tbmax_mjd"].map("{:.3f}".format).to_numpy()).to_csv(
        os.path.join(args.out, "sample.csv"), index=False, float_format="%.6g")

    print(f"sample: {len(sample)} SNe ({sample['type'].value_counts().to_dict()})")
    print(f"T(B)max: {sample['tbmax_mjd'].notna().sum()} SNe "
          f"({sample['tbmax_band'].replace('', 'ninguna').value_counts().to_dict()})")
    print(f"fotometria: {len(ph)} puntos (opt {len(opt)}, NIR {len(ph) - len(opt)})")
    if "in_csp" in sample:
        both = sample[sample["in_csp"] & sample["tbmax_mjd"].notna()]
        d = both["tbmax_mjd"] - both["tbmax_csp_mjd"]
        print(f"T(B)max CfA - CSP en {len(both)} SNe comunes: mediana {d.median():+.1f} d, "
              f"MAD {np.median(np.abs(d - d.median())):.1f} d; |dif| > 5 d: "
              f"{', '.join(f'{s} ({v:+.0f})' for s, v in d[d.abs() > 5].items()) or 'ninguna'}")
        cmp_ = compare_csp(ph, args.csp)
        if cmp_ is not None and len(cmp_):
            cmp_.to_csv(os.path.join(args.out, "compare_csp.csv"), index=False, float_format="%.4g")
            print("CfA - CSP en AB (misma SN y noche):")
            print(cmp_.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
