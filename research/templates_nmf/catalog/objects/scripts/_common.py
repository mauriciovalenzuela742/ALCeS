"""Utilidades comunes de los scripts de inventario por objeto (etapa 2).

Solo libreria estandar + pandas. Las descargas se guardan en objects/raw/<source_id>/ y no se
repiten si el archivo ya existe (borrar el archivo para forzar la descarga).
"""
import os
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.dirname(HERE)
RAW = os.path.join(OBJ, "raw")
PARTS = os.path.join(OBJ, "parts")

COLUMNS = [
    "sn_name", "alt_names", "source_id", "subclass", "ra", "dec", "z", "z_type", "dist_mod",
    "dist_method", "ebv_mw", "ebv_host", "bands", "n_phot", "n_spec", "phase_min", "phase_max",
    "phase_ref", "oh12", "oh12_type", "oh12_calib",
]

C_KMS = 299792.458
# Sin "Mozilla": CDS usa un filtro anti-bot (Anubis) que desafia a los UA de navegador.
UA = {"User-Agent": "ALCeS-template-inventory/1.0 (python-urllib)"}


def raw_dir(source_id):
    d = os.path.join(RAW, source_id)
    os.makedirs(d, exist_ok=True)
    return d


def fetch(url, path, timeout=300):
    """Descarga url a path si no existe. Devuelve path."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    head = data[:200].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        if not path.lower().endswith((".html", ".htm", ".php")):
            raise RuntimeError(f"{url} devolvio HTML (pagina anti-bot o error), no se guarda")
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def sexa_to_deg(ra_h, ra_m, ra_s, sign, de_d, de_m, de_s):
    ra = 15.0 * (float(ra_h) + float(ra_m) / 60.0 + float(ra_s) / 3600.0)
    dec = float(de_d) + float(de_m) / 60.0 + float(de_s) / 3600.0
    if str(sign).strip() == "-":
        dec = -dec
    return ra, dec


def parse_sexa(ra_str, dec_str):
    """'01:59:20.77', '+19:00:10.6' (o con espacios) -> grados."""
    r = ra_str.replace(":", " ").split()
    d = dec_str.strip()
    sign = "-" if d.startswith("-") else "+"
    d = d.lstrip("+-").replace(":", " ").split()
    return sexa_to_deg(r[0], r[1], r[2], sign, d[0], d[1], d[2])


def fmt(v, nd=5):
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:
            return ""
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else str(int(round(v)))
    return str(v)


def write_part(rows, source_id):
    df = pd.DataFrame(rows)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNS].fillna("")
    for c in COLUMNS:
        df[c] = df[c].map(lambda v: fmt(v) if isinstance(v, float) else ("" if v is None else str(v)))
    df = df.sort_values("sn_name", kind="stable").reset_index(drop=True)
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, f"{source_id}.csv")
    df.to_csv(out, index=False, lineterminator="\n")
    print(f"{out}: {len(df)} filas")
    return df
