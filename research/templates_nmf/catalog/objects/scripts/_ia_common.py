"""Utilidades compartidas por los scripts de inventario de la familia Ia.

Solo librería estándar + pandas. Las descargas se cachean en objects/raw/<source_id>/:
si el archivo ya existe no se vuelve a bajar, así que correr de nuevo da lo mismo.
"""
import os
import time
import urllib.request

import pandas as pd

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


def fetch(url, dest, timeout=120, retries=4):
    """Descarga url a dest si dest no existe (con reintentos). Devuelve dest."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    tmp = dest + ".part"
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp, dest)
            return dest
        except (OSError, TimeoutError) as e:
            print(f"fetch {url}: intento {k + 1} falló ({e})")
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"no se pudo descargar {url}")


def fixed_width(path, spec, comment=None):
    """Lee un archivo de ancho fijo de CDS. spec = [(nombre, byte_ini, byte_fin)] 1-indexado."""
    rows = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or (comment and line.startswith(comment)):
                continue
            rows.append({n: line[a - 1:b].strip() for n, a, b in spec})
    return pd.DataFrame(rows)


def sex2deg(ra, dec):
    """'hh:mm:ss.s', '+dd:mm:ss' (o separado por espacios) -> grados."""
    try:
        h, m, s = [float(x) for x in ra.replace(":", " ").split()]
        sign = -1 if dec.strip().startswith("-") else 1
        d, dm, ds = [abs(float(x)) for x in dec.replace(":", " ").split()]
    except (ValueError, AttributeError):
        return None, None
    return round(15 * (h + m / 60 + s / 3600), 6), round(sign * (d + dm / 60 + ds / 3600), 6)


def write_part(source_id, rows):
    df = pd.DataFrame(rows)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNS].fillna("")
    df["source_id"] = source_id
    df = df.sort_values("sn_name").reset_index(drop=True)
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, f"{source_id}.csv")
    df.to_csv(out, index=False)
    print(f"{out}: {len(df)} filas")
    print(df["subclass"].value_counts().to_string())
    return df


def fmt(x, nd=4):
    """Número -> texto con nd decimales, vacío si no es número."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if v != v:
        return ""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else str(int(round(v)))
    return "0" if s == "-0" else s


VIZ_MIRRORS = ["https://vizier.cds.unistra.fr", "https://vizier.idia.ac.za"]


def viz_tsv(source, cols, dest, extra=""):
    """Tabla de VizieR por asu-tsv (columnas `cols`), probando espejos. Devuelve DataFrame."""
    import io
    import urllib.parse
    q = (f"-source={urllib.parse.quote(source)}&-out.max=unlimited&-out.add=_RAJ,_DEJ"
         f"&-out={urllib.parse.quote(','.join(cols))}" + extra)
    q = q.replace("&-out.add=_RAJ,_DEJ", "")
    if not (os.path.exists(dest) and os.path.getsize(dest) > 0):
        last = None
        for m in VIZ_MIRRORS:
            try:
                fetch(f"{m}/viz-bin/asu-tsv?{q}", dest, retries=2)
                break
            except RuntimeError as e:
                last = e
        else:
            raise last
    lines = [ln for ln in open(dest, encoding="latin-1").read().splitlines()
             if ln and not ln.startswith("#")]
    # cabecera = primera línea; luego unidades y guiones
    body = [lines[0]] + [ln for ln in lines[3:]]
    df = pd.read_csv(io.StringIO("\n".join(body)), sep="\t", dtype=str,
                     keep_default_na=False)
    return df.apply(lambda c: c.str.strip())
