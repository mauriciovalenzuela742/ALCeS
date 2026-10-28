"""Agente 2, paso 1: muestra de SNII de CSP-I homogeneizada.

Uso:
    python build_csp_snii.py [--out out/csp_snii]

Requiere las descargas de la etapa 2 del catalogo (correr antes, si faltan,
catalog/objects/scripts/{csp1_snii_photometry_anderson24,csp_snii_spectra_gutierrez17,
anderson16_snii_hii_metallicity}.py). Escribe:

- sample.csv: una fila por SN de Gutierrez+17 (z, E(B-V)_MW, epoca de explosion,
  metalicidad local de Anderson+16, cuantos puntos y espectros tiene).
- photometry.csv: fotometria de Anderson+24 en AB, corregida por extincion de la Via Lactea
  (CCM89+O'Donnell94, R_V=3.1, en la lambda_eff del filtro) y con fase en reposo desde la
  explosion. Flujo f_nu en microJansky. Sin correccion K ni de extincion del host.
- spectra.csv: indice de los FITS de Gutierrez+17 (fecha, rango de lambda, brazo, fase en
  reposo). Los espectros no se modifican aqui.

Pasos que dependen de decisiones abiertas (distancia, extincion del host, mangling, rejilla)
no estan en este script.
"""
import argparse
import glob
import math
import os
import re
import sys
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "catalog", "objects", "scripts")
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

import csp_system  # noqa: E402
from extinction import a_lambda  # noqa: E402
from _common import C_KMS, RAW  # noqa: E402
import anderson16_snii_hii_metallicity as a16  # noqa: E402
import csp_snii_spectra_gutierrez17 as g17  # noqa: E402

PHOT = os.path.join(RAW, "csp1_snii_photometry_anderson24")
G17 = os.path.join(RAW, "csp_snii_spectra_gutierrez17")
A16 = os.path.join(RAW, "anderson16_snii_hii_metallicity")

# Columnas (inicio, fin) 1-indexadas e inclusivas del ReadMe de J/A+A/692/A95.
OPT = {"u": (23, 28), "g": (38, 43), "r": (52, 57), "i": (66, 71), "B": (80, 85), "V": (94, 99)}
NIR = {"Y": (23, 28), "J": (37, 42), "H": (51, 56)}
ERR_W = 5  # e_mag ocupa 5 bytes, empezando 2 despues de la magnitud
SYS_OPT, SYS_NIR = (107, 117), (64, 78)


def key(name):
    """'SN 2004er', 'SN2004er', '2004er' -> '2004er'; 'SN 210' -> '210'."""
    return re.sub(r"^SN\s*", "", str(name).strip())


def cut(line, a, b):
    return line[a - 1:b].strip()


def read_photometry(path, cols, sys_cols):
    rows = []
    for ln in open(path, encoding="latin-1"):
        if not ln.strip():
            continue
        sn = cut(ln, 1, 9)
        jd = float(cut(ln, 11, 20))
        system = cut(ln, *sys_cols)
        for band, (a, b) in cols.items():
            mag = float(cut(ln, a, b))
            err = float(cut(ln, b + 2, b + 1 + ERR_W))
            if mag == 0.0:  # ?=0 en el ReadMe: sin dato
                continue
            rows.append((sn, jd, band, system, mag, err))
    return pd.DataFrame(rows, columns=["phot_name", "jd", "band", "system", "mag_nat", "mag_err"])


def phot_names():
    """Nombre de la tabla de fotometria -> clave de Gutierrez+17."""
    out = {}
    for ln in open(os.path.join(PHOT, "sn.dat"), encoding="latin-1"):
        short = cut(ln, 1, 9)
        out[short] = key(short)
    return out


def parse_explosion(cell):
    """'46708.0$^{n}$(3)' -> (46708.0, 'non_detection', 3.0); '*' = cambiada desde Anderson+14."""
    m = re.match(r"^\s*([\d.]+)\$\^\{(\w)\}\$\((\d+(?:\.\d+)?)\)(\*?)", cell)
    if not m:
        return math.nan, "", math.nan, False
    meth = {"n": "non_detection", "s": "spectral_matching"}.get(m.group(2), m.group(2))
    return float(m.group(1)), meth, float(m.group(3)), m.group(4) == "*"


def read_sample():
    tex = g17.tex_members(os.path.join(G17, "arxiv_1709.02487_src.tar.gz"))
    info = g17.parse_info(tex["table_info.tex"])
    expl = {}
    for ln in g17.strip_comments(tex["table_info.tex"]).splitlines():
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) == 10 and cells[0] in info:
            expl[cells[0]] = parse_explosion(cells[7])

    text = a16.read_tex(os.path.join(A16, "arxiv_1602.00011_src.tar.gz"))
    oh = {}
    for b in a16.tabulars(text):
        if "M13 N2" in b:
            for name, mark, cells in a16.rows_of(b):
                oh[name] = (a16.num(cells[2]), mark == "*")

    rows = []
    for name, r in info.items():
        t0, meth, t0_err, changed = expl.get(name, (math.nan, "", math.nan, False))
        o, from_a10 = oh.get(name, (None, False))
        rows.append({
            "sn": name,
            "z_helio": r["v"] / C_KMS if r["v"] else math.nan,
            "z_type": r["z_type"],
            "ebv_mw": float(r["ebv_mw"]),
            "t_expl_mjd": t0,
            "t_expl_err_d": t0_err,
            "t_expl_method": meth,
            "t_expl_changed_vs_a14": changed,
            "oh12": o if o is not None else math.nan,
            "oh12_calib": "N2_M13" if o is not None else "",
            "oh12_from_a10": from_a10 if o is not None else "",
        })
    return pd.DataFrame(rows)


MJD0 = datetime(1858, 11, 17)


def plausible(mjd):
    return 40000 < mjd < 70000  # 1968-2050; descarta MJD-OBS basura (3e-20, -1.7e38)


def _yy(yy):
    return 1900 + yy if yy > 50 else 2000 + yy


def fits_mjd(hdr, fname, year_hint=None):
    """MJD de observacion. Orden: JD, MJD-OBS/MJD, DATE-OBS ISO, fecha en el nombre del archivo
    ('14jan94', '3jul90'; sin anio, 'sn88a.02feb', usa year_hint) y por ultimo DATE-OBS dd/mm/yy,
    que es ambiguo: en SN 1986L y SN 1993K contradice al nombre y al JD de los otros brazos."""
    if hdr.get("JD") and plausible(float(hdr["JD"]) - 2400000.5):
        return float(hdr["JD"]) - 2400000.5
    for k in ("MJD-OBS", "MJD"):
        v = hdr.get(k)
        if isinstance(v, (int, float)) and plausible(float(v)):
            return float(v)
    d = str(hdr.get("DATE-OBS") or "")
    m = re.match(r"^(\d{4})-\s*(\d{1,2})-\s*(\d{1,2})", d)  # hay fechas como '2002-10- 8'
    if m:
        return (datetime(*map(int, m.groups())) - MJD0).days + 0.0
    m = re.search(r"(?<![a-z\d])(\d{1,2})([a-z]{3})(\d\d)?(?!\d)", fname.lower())
    if m:
        dd, mon, yy = m.groups()
        try:
            month = datetime.strptime(mon, "%b").month
            year = _yy(int(yy)) if yy else year_hint
            if year:
                return (datetime(year, month, int(dd)) - MJD0).days + 0.0
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d\d)$", d)
    if m:
        dd, mm, yy = map(int, m.groups())
        try:
            return (datetime(_yy(yy), mm, dd) - MJD0).days + 0.0
        except ValueError:
            pass
    return math.nan


def folder_year(folder):
    """'SN88A' -> 1988; 'SN210' -> None."""
    m = re.match(r"^SN(\d\d)[A-Za-z]", folder)
    return _yy(int(m.group(1))) if m else None


def read_spectra():
    from astropy.io import fits

    base = os.path.join(G17, "x", "Gutierrez_et_al_2017")
    if not os.path.isdir(base):
        import tarfile
        with tarfile.open(os.path.join(G17, "Gutierrez_et_al_2017.tar.gz"), "r:gz") as t:
            t.extractall(os.path.join(G17, "x"), filter="data")
    rows = []
    for f in sorted(glob.glob(os.path.join(base, "*", "*.fits"))):
        folder = os.path.basename(os.path.dirname(f))
        with fits.open(f) as h:
            hd = h[0].header
            n = hd.get("NAXIS1")
            w0 = hd.get("CRVAL1")
            dw = hd.get("CDELT1") or hd.get("CD1_1")
            p0 = hd.get("CRPIX1", 1.0)
        fn = os.path.basename(f).lower()
        arm = next((a for a in ("blue", "red", "opt", "ir", "mid") if f".{a}." in fn), "")
        rows.append({
            "folder": folder,
            "file": os.path.relpath(f, G17).replace(os.sep, "/"),
            "mjd": fits_mjd(hd, fn, year_hint=folder_year(folder)),
            # 5 FITS no traen CRVAL1/CDELT1: quedan sin rango (no se adivina la solucion).
            "wave_min": w0 + (1 - p0) * dw if n and w0 is not None and dw else math.nan,
            "wave_max": w0 + (n - p0) * dw if n and w0 is not None and dw else math.nan,
            "npix": n,
            "arm": arm,
            "bunit": hd.get("BUNIT", ""),
        })
    return pd.DataFrame(rows)


def folder_to_key(folder, keys):
    """'SN86L' -> '1986L'; 'SN210' -> '210'."""
    s = folder[2:] if folder.upper().startswith("SN") else folder
    if s in keys:
        return s
    for century in ("19", "20"):
        if century + s in keys:
            return century + s
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "csp_snii"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    sample = read_sample().set_index("sn")

    ph = pd.concat([
        read_photometry(os.path.join(PHOT, "photopt.dat"), OPT, SYS_OPT),
        read_photometry(os.path.join(PHOT, "photnir.dat"), NIR, SYS_NIR),
    ], ignore_index=True)
    names = phot_names()
    ph["sn"] = ph["phot_name"].map(names)
    ph["mjd"] = ph["jd"] - 2400000.5
    looked = [csp_system.lookup(s, b, m) for s, b, m in zip(ph["system"], ph["band"], ph["mjd"])]
    ph["filter"] = [x[0] for x in looked]
    ph["lambda_eff"] = [x[1] for x in looked]
    ph["ab_offset"] = [x[2] for x in looked]
    ph["mag_ab"] = ph["mag_nat"] + ph["ab_offset"]
    ebv = ph["sn"].map(sample["ebv_mw"])
    ph["a_mw"] = a_lambda(ph["lambda_eff"].to_numpy(), ebv.to_numpy())
    ph["mag_ab_mwcorr"] = ph["mag_ab"] - ph["a_mw"]
    ph["fnu_ujy"] = 10 ** (-0.4 * (ph["mag_ab_mwcorr"] - 23.9))
    ph["fnu_err_ujy"] = ph["fnu_ujy"] * ph["mag_err"] * math.log(10) / 2.5
    z = ph["sn"].map(sample["z_helio"])
    ph["phase_rest"] = (ph["mjd"] - ph["sn"].map(sample["t_expl_mjd"])) / (1 + z)
    ph["lambda_rest"] = ph["lambda_eff"] / (1 + z)
    ph["in_sample"] = ph["sn"].isin(sample.index)
    ph = ph.drop(columns=["jd"])
    ph.to_csv(os.path.join(args.out, "photometry.csv"), index=False, float_format="%.5g")

    sp = read_spectra()
    sp["sn"] = [folder_to_key(f, set(sample.index)) for f in sp["folder"]]
    zs = sp["sn"].map(sample["z_helio"])
    sp["phase_rest"] = (sp["mjd"] - sp["sn"].map(sample["t_expl_mjd"])) / (1 + zs)
    sp.to_csv(os.path.join(args.out, "spectra.csv"), index=False, float_format="%.6g")

    ok = ph[ph["in_sample"] & ph["mag_ab"].notna()]
    sample["n_phot"] = ok.groupby("sn").size().reindex(sample.index).fillna(0).astype(int)
    sample["bands"] = ok.groupby("sn")["band"].agg(lambda s: ";".join(sorted(set(s)))).reindex(sample.index).fillna("")
    sample["n_spec_files"] = sp[sp["sn"] != ""].groupby("sn").size().reindex(sample.index).fillna(0).astype(int)
    sample["n_spec_nights"] = (sp[sp["sn"] != ""].assign(night=sp["mjd"].round())
                               .groupby("sn")["night"].nunique().reindex(sample.index).fillna(0).astype(int))
    sample.reset_index().to_csv(os.path.join(args.out, "sample.csv"), index=False, float_format="%.6g")

    # Diagnostico.
    print(f"sample: {len(sample)} SNe; con fotometria: {(sample['n_phot'] > 0).sum()}; "
          f"con metalicidad: {sample['oh12'].notna().sum()}; "
          f"con ambas y >=3 noches de espectros: "
          f"{((sample['n_phot'] > 0) & sample['oh12'].notna() & (sample['n_spec_nights'] >= 3)).sum()}")
    print(f"fotometria: {len(ph)} puntos; fuera de la muestra de G17: "
          f"{(~ph['in_sample']).sum()} ({ph.loc[~ph['in_sample'], 'phot_name'].nunique()} SNe); "
          f"sin calibracion AB: {ph['ab_offset'].isna().sum()} "
          f"({sorted(ph.loc[ph['ab_offset'].isna(), 'system'].unique())})")
    print(f"espectros: {len(sp)} FITS; sin SN de la muestra: {sorted(sp.loc[sp['sn'] == '', 'folder'].unique())}; "
          f"sin fecha: {sp['mjd'].isna().sum()}")
    bad = ph[ph["in_sample"] & (ph["phase_rest"] < -5)]
    if len(bad):
        print(f"aviso: {len(bad)} puntos con fase < -5 d (antes de la explosion):",
              sorted(bad["sn"].unique()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
