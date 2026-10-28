"""Inventario por objeto de ZTF SN Ia DR2 (Rigault+25, arXiv:2409.04346).

El zip completo (ztfsniadr2_lite.zip, 1.37 GB) supera el límite; se usan los archivos
remotos que lee el paquete `ztfcosmo` (https://ztfcosmo.in2p3.fr/download/<ruta con __>):
- tables__snia_data.csv (3628 SNe: nombre ZTF/IAU, z y su origen, tipo/subtipo, MW E(B-V),
  t0 SALT2, RA/Dec).
- tables__spec_dataframe.parquet (5138 espectros: ztfname, fase) -> n_spec.
- Cabecera de cada curva de luz (lightcurves__<ztfname>_lc.csv, solo los primeros 8 kB por
  HTTP Range; las curvas completas suman ~600 MB). De la tabla "baseline_corr (applied)" se
  suman n_sn (puntos dentro de la ventana de la SN) por filtro -> bands y n_phot.

Origen de z (fracciones de arXiv:2407.06828: 61% catálogo de host, 9% líneas del host en el
espectro de la SN, 30% SNID): z_gal -> host_spec; z_SEDm / z_nonSEDm -> host_spec;
z_snid -> spec; z_override / z_unknown -> unknown.
"""
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import UA, fetch, fmt, raw_dir, write_part  # noqa: E402

SID = "ztf_dr2_ia"
BASE = "https://ztfcosmo.in2p3.fr/download/"
ZTYPE = {"z_gal": "host_spec", "z_SEDm": "host_spec", "z_nonSEDm": "host_spec",
         "z_snid": "spec", "z_override": "unknown", "z_unknown": "unknown"}
SUB = {"norm": "Ia", "norm/99aa": "Ia", "norm/04gs": "Ia",
       "91t": "Ia-91T", "99aa": "Ia-91T", "99aa/91t": "Ia-91T",
       "91bg": "Ia-91bg", "91bg/86G": "Ia-91bg",
       "iax": "Iax", "csm": "Ia-CSM",
       "03fg": "Ia-other", "02es": "Ia-other", "18byg": "Ia-other", "00cx": "Ia-other",
       "19yvq": "Ia-other"}
FILT = {"ztfg": "g", "ztfr": "r", "ztfi": "i"}


def header(name, d):
    """Primeros 8 kB de la curva de luz (cache en raw/ztf_dr2_ia/lc_headers/)."""
    p = os.path.join(d, f"{name}.txt")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, encoding="utf-8").read()
    for k in range(4):
        try:
            req = urllib.request.Request(BASE + f"lightcurves__{name}_lc.csv",
                                         headers={**UA, "Range": "bytes=0-8191"})
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode("utf-8", "replace")
            with open(p, "w", encoding="utf-8") as f:
                f.write(txt)
            return txt
        except OSError as e:
            if getattr(e, "code", None) == 404:
                return ""
            time.sleep(3 * (k + 1))
    return None


def parse(txt):
    """Suma n_sn por filtro de la tabla 'baseline_corr (applied)'."""
    if not txt:
        return {}
    m = re.search(r"# baseline_corr \(applied\):.*?\n#\s+field.*?\n(.*?)# -----", txt, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        p = line.lstrip("#").split()
        if len(p) >= 12 and p[2] in FILT:
            out[FILT[p[2]]] = out.get(FILT[p[2]], 0) + int(p[9])
    return out


def main():
    d = raw_dir(SID)
    hd = os.path.join(d, "lc_headers")
    os.makedirs(hd, exist_ok=True)
    t = pd.read_csv(fetch(BASE + "tables__snia_data.csv",
                          os.path.join(d, "tables__snia_data.csv")), index_col=0)
    sp = pd.read_parquet(fetch(BASE + "tables__spec_dataframe.parquet",
                               os.path.join(d, "tables__spec_dataframe.parquet")))
    nspec = sp.groupby("ztfname").size()

    names = list(t.ztfname)
    with ThreadPoolExecutor(4) as ex:
        heads = dict(zip(names, ex.map(lambda n: header(n, hd), names)))
    failed = [n for n, h in heads.items() if h is None]
    rows = []
    for _, r in t.iterrows():
        nb = parse(heads.get(r.ztfname))
        iau = r.iau_name if isinstance(r.iau_name, str) and r.iau_name.strip() else ""
        sub = SUB.get(r.sub_type, "Ia") if isinstance(r.sub_type, str) else "Ia"
        rows.append({
            "sn_name": r.ztfname, "alt_names": f"SN {iau}" if iau else "",
            "subclass": sub, "ra": fmt(r.ra, 6), "dec": fmt(r.dec, 6),
            "z": fmt(r.redshift, 6), "z_type": ZTYPE.get(r.source, "unknown"),
            "ebv_mw": fmt(r.mwebv, 4),
            "bands": ";".join(b for b in "gri" if nb.get(b, 0) > 0),
            "n_phot": sum(nb.values()) if nb else "",
            "n_spec": int(nspec.get(r.ztfname, 0)),
        })
    print("cabeceras fallidas:", len(failed), failed[:10])
    print("sin tabla baseline:", sum(1 for r in rows if r["n_phot"] == ""))
    df = write_part(SID, rows)
    print("espectros:", df.n_spec.astype(int).sum(), " SNe con espectro:",
          (df.n_spec.astype(int) > 0).sum())


if __name__ == "__main__":
    main()
