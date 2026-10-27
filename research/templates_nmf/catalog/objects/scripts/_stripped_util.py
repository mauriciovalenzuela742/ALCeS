"""Utilidades comunes a los scripts de inventario del grupo `stripped` (SESN y SLSN).

Solo librería estándar + pandas. Descarga a objects/raw/<source_id>/ y escribe
objects/parts/<source_id>.csv con las columnas de OBJECTS_SCHEMA.md.
"""
import csv
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.dirname(HERE)
RAW = os.path.join(OBJ, "raw")
PARTS = os.path.join(OBJ, "parts")

COLUMNS = [
    "sn_name", "alt_names", "source_id", "subclass", "ra", "dec", "z", "z_type",
    "dist_mod", "dist_method", "ebv_mw", "ebv_host", "bands", "n_phot", "n_spec",
    "phase_min", "phase_max", "phase_ref", "oh12", "oh12_type", "oh12_calib",
]

UA = {"User-Agent": "ALCeS-template-scout/1.0 (research inventory)"}


def raw_dir(source_id):
    d = os.path.join(RAW, source_id)
    os.makedirs(d, exist_ok=True)
    return d


def fetch(url, dest, force=False, retries=3):
    """Descarga url a dest si no existe ya (caché simple). Devuelve dest."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0 and not force:
        return dest
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"no se pudo descargar {url}: {last}")


def fw(line, a, b):
    """Campo de ancho fijo con bytes 1-indexados [a, b] como en los ReadMe de CDS."""
    return line[a - 1:b].strip()


def ffloat(s):
    s = (s or "").strip()
    if s in ("", "-", "--", "nan", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sexa_ra(h, m, s):
    return 15.0 * (float(h) + float(m) / 60.0 + float(s) / 3600.0)


def sexa_dec(sign, d, m, s):
    v = float(d) + float(m) / 60.0 + float(s) / 3600.0
    return -v if sign.strip() == "-" else v


def fmt(v, nd=None):
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:  # NaN
            return ""
        return f"{v:.{nd}f}" if nd is not None else repr(v)
    return str(v)


def write_part(source_id, rows):
    """rows: lista de dicts con claves de COLUMNS. Ordena por sn_name y escribe el CSV."""
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, f"{source_id}.csv")
    rows = sorted(rows, key=lambda r: r["sn_name"])
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            rr = {c: "" for c in COLUMNS}
            rr.update({k: ("" if v is None else v) for k, v in r.items()})
            rr["source_id"] = source_id
            w.writerow(rr)
    print(f"{out}: {len(rows)} filas")
    return out
