"""Inventario por objeto de Hinds+25 (SNe II de ZTF BTS: tiempos de subida y CSM).

Fuente: archivo auxiliar de arXiv:2503.19969v3 (anc/Hinds_ea_25.dat, tabla en formato CDS,
0.4 MB). Columnas usadas: ZTFID, TNSID, Type, z. La tabla no trae numero de puntos ni
espectros; las curvas son de ZTF (g y r, usadas para t_25_75 y r_t_25_75).

z_type=unknown: el paper (seccion de la muestra) dice que clasificaciones y redshifts vienen
de BTS (Qin et al. en prep.) o de TNS, sin separar redshift del host y de la SN.
Bandas: 'ztfg;ztfr' (nombres propios para no mezclarlas con g/r de otros sistemas).
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, raw_dir, write_part  # noqa: E402

SID = "ztf_bts_snii_hinds25"
URL = "https://arxiv.org/src/2503.19969v3/anc/Hinds_ea_25.dat"
TYPES = {"II": "II", "IIb": "IIb", "IIn": "IIn"}


def main():
    d = raw_dir(SID)
    path = fetch(URL, os.path.join(d, "Hinds_ea_25.dat"))
    rows = []
    with open(path, encoding="latin-1") as f:
        for ln in f:
            if not re.match(r"^ZTF\d\d[a-z]{7}\s", ln):
                continue
            ztf = ln[0:12].strip()
            tns = ln[13:23].strip().strip("-")  # "-" = sin nombre TNS
            typ = ln[24:27].strip()
            z = float(ln[28:48])
            rows.append({
                "sn_name": ztf,
                "alt_names": tns,
                "source_id": SID,
                "subclass": TYPES.get(typ, "SN-other"),
                "z": round(z, 6),
                "z_type": "unknown",
                "bands": "ztfg;ztfr",
            })
    write_part(rows, SID)
    print(f"filas: {len(rows)} {dict(Counter(r['subclass'] for r in rows))}")
    zs = [r["z"] for r in rows]
    print(f"z: {min(zs)} - {max(zs)}")


if __name__ == "__main__":
    main()
