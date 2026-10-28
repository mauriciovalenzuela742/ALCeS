"""Inventario por objeto del ZTF Bright Transient Survey (todas las clases de SN).

Fuente: BTS Sample Explorer (sites.astro.caltech.edu/ztf/bts/explorer.php), exportacion CSV
con subsample=sn (SNe clasificadas), sin corte de calidad ni de magnitud adicional.
Columnas: ZTFID, IAUID, RA, Dec, peakmag, type, redshift, A_V, ...

- z_type=unknown: el explorer no dice si el redshift es del host o de la SN (BTS usa ambos).
- A_V (extincion galactica) no se convierte a E(B-V): el explorer no indica el R_V usado.
- Sin bandas ni conteo de fotometria/espectros (el explorer no los da por objeto).
- El archivo crece: el CSV descargado se guarda en raw/ y el script lo reutiliza; borrarlo
  para refrescar. El numero de filas cambia con la fecha de descarga.
"""
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, parse_sexa, raw_dir, write_part  # noqa: E402

SID = "ztf_bts"
URL = ("https://sites.astro.caltech.edu/ztf/bts/explorer.php?f=s&subsample=sn&format=csv"
       "&showra=y&showdec=y&showz=y&showpeakmag=y")

TYPES = {
    "SN Ia": "Ia", "SN Ia-91T": "Ia-91T", "SN Ia-91bg": "Ia-91bg", "SN Iax": "Iax",
    "SN Ia-CSM": "Ia-CSM", "SN Ia-pec": "Ia-other", "SN Ia-SC": "Ia-other",
    "SN II": "II", "SN II-pec": "II", "SN IIP": "IIP", "SN IIL": "IIL", "SN IIn": "IIn",
    "SN IIn-pec": "IIn", "SN IIb": "IIb",
    "SN Ib": "Ib", "SN Ib-pec": "Ib", "SN Ic": "Ic", "SN Ic-pec": "Ic", "SN Ic-BL": "Ic-BL",
    "SN Ibn": "Ibn", "SN Icn": "Icn", "SN Ca-rich-Ca": "Ca-rich",
    "SLSN-I": "SLSN-I", "SLSN-II": "SLSN-II",
}


def main():
    d = raw_dir(SID)
    path = fetch(URL, os.path.join(d, "bts_explorer_sn.csv"))
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows, unmapped = [], Counter()
    for _, r in df.iterrows():
        if not r["ZTFID"].startswith("ZTF"):
            continue
        sub = TYPES.get(r["type"])
        if sub is None:
            unmapped[r["type"]] += 1
            sub = "SN-other"  # p. ej. 'SN Ib/c' (ambigua)
        try:
            ra, dec = parse_sexa(r["RA"], r["Dec"])
            ra, dec = round(ra, 6), round(dec, 6)
        except Exception:
            ra = dec = ""
        alt = r["IAUID"].strip()
        rows.append({
            "sn_name": r["ZTFID"],
            "alt_names": alt if alt and alt != "-" else "",
            "source_id": SID,
            "subclass": sub,
            "ra": ra, "dec": dec,
            "z": r["redshift"].strip(),
            "z_type": "unknown" if r["redshift"].strip() else "",
        })
    write_part(rows, SID)
    print(f"filas: {len(rows)}")
    print("subclases:", dict(Counter(x["subclass"] for x in rows).most_common()))
    print("tipos sin mapeo directo (-> SN-other):", dict(unmapped))


if __name__ == "__main__":
    main()
