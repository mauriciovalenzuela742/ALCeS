"""Inventario por objeto de Anderson+24 (CSP, 94 SNe II, uBgVri + YJH).

Fuente: VizieR J/A+A/692/A95 (sn.dat, photopt.dat, photnir.dat), descargado del FTP de CDS.
En photopt/photnir cada fila es una epoca con varias bandas; una magnitud 0 significa
"sin dato" (?=0 en el ReadMe). n_phot cuenta magnitudes no nulas en todas las bandas.

La tabla de VizieR no trae redshift, extincion ni epoca de explosion (estan en tablas PNG de
Zenodo 13743303, no legibles por maquina), asi que esas columnas quedan vacias.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, raw_dir, sexa_to_deg, write_part  # noqa: E402

SID = "csp1_snii_photometry_anderson24"
BASE = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/692/A95/"

OPT_COLS = {"u": (22, 28), "g": (37, 43), "r": (51, 57), "i": (65, 71), "B": (79, 85), "V": (93, 99)}
NIR_COLS = {"Y": (22, 28), "J": (36, 42), "H": (50, 56)}
BAND_ORDER = ["u", "B", "g", "V", "r", "i", "Y", "J", "H"]


def read_lines(path):
    with open(path, encoding="ascii", errors="replace") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def count_phot(path, cols, counts):
    for ln in read_lines(path):
        sn = ln[0:9].strip()
        for b, (a, z) in cols.items():
            s = ln[a:z].strip()
            if s and float(s) != 0.0:
                counts.setdefault(sn, {}).setdefault(b, 0)
                counts[sn][b] += 1


def main():
    d = raw_dir(SID)
    files = {f: fetch(BASE + f, os.path.join(d, f)) for f in ("ReadMe", "sn.dat", "photopt.dat", "photnir.dat")}

    counts = {}
    count_phot(files["photopt.dat"], OPT_COLS, counts)
    count_phot(files["photnir.dat"], NIR_COLS, counts)

    rows = []
    for ln in read_lines(files["sn.dat"]):
        sn = ln[0:9].strip()
        ra, dec = sexa_to_deg(ln[10:12], ln[13:15], ln[16:21], ln[23:24], ln[24:26], ln[27:29], ln[30:34])
        # Nombre Simbad sin espacios ('ASASSN -14gm' -> 'ASASSN-14gm'); el nombre corto de la
        # tabla ('ASASS14gm') va como alternativo.
        simbad = ln[50:62].strip().replace(" ", "")
        c = counts.get(sn, {})
        name = simbad or sn
        alt = [sn] if sn != name else []
        rows.append({
            "sn_name": name,
            "alt_names": ";".join(alt),
            "source_id": SID,
            "subclass": "II",
            "ra": round(ra, 6),
            "dec": round(dec, 6),
            "bands": ";".join(b for b in BAND_ORDER if c.get(b)),
            "n_phot": str(sum(c.values())) if c else "",
        })
    df = write_part(rows, SID)
    tot_opt = sum(v for s in counts.values() for b, v in s.items() if b in OPT_COLS)
    tot_nir = sum(v for s in counts.values() for b, v in s.items() if b in NIR_COLS)
    n_nir = sum(1 for s in counts.values() if any(b in NIR_COLS for b in s))
    print(f"SNe: {len(df)}; puntos opticos: {tot_opt}; NIR: {tot_nir} en {n_nir} SNe")


if __name__ == "__main__":
    main()
