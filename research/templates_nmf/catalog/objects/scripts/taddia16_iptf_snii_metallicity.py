"""Inventario por objeto de Taddia+16 (metalicidad de SNe II de (i)PTF, A&A letter).

Fuente: fuente LaTeX de arXiv:1602.01433. Tablas:
- 'tab:spectra': un espectro por SN usado para pEW(FeII 5018), con fase desde la explosion
  (corregida por dilatacion temporal). '*' = IIL; el resto IIP. Las filas comentadas con '%'
  (sin medicion de pEW) no forman parte de la muestra publicada.
- 'tab:metal': Z del host en unidades solares (LZ, LCZ, O3N2) y coordenadas del host.

No se llena oh12: el paper da Z/Z_sun, no 12+log(O/H), y no dice que valor solar uso para
convertir; pasar a 12+log(O/H) seria inventar. Tampoco hay redshift ni fotometria por objeto.
Nombres: la tabla da '09ecm', '13aaz'; se antepone 'PTF' (2009-2012) o 'iPTF' (2013 en
adelante), la convencion de nombres de PTF/iPTF.
"""
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, raw_dir, write_part  # noqa: E402

SID = "taddia16_iptf_snii_metallicity"
ARXIV_SRC = "https://arxiv.org/src/1602.01433"
TEX = "letter_SNII_EW_final.tex"


def full_name(short):
    yr = int(short[:2])
    return ("iPTF" if yr >= 13 else "PTF") + short


def main():
    d = raw_dir(SID)
    with tarfile.open(fetch(ARXIV_SRC, os.path.join(d, "arxiv_1602.01433_src.tar.gz")), "r:*") as t:
        tex = t.extractfile(t.getmember(TEX)).read().decode("latin-1")
    block = tex.split("label{tab:spectra}")[1].split("enddata")[0]
    rows = []
    for ln in block.splitlines():
        if ln.lstrip().startswith("%"):
            continue
        cells = [c.strip() for c in ln.split("%")[0].split("&")]
        m = re.match(r"^(\d\d[a-z]{2,3})(\*?)$", cells[0]) if len(cells) >= 5 else None
        if not m:
            continue
        ph = re.match(r"^(\d+(?:\.\d+)?)", cells[1])
        rows.append({
            "sn_name": full_name(m.group(1)),
            "source_id": SID,
            "subclass": "IIL" if m.group(2) else "IIP",
            "n_spec": "1",
            "phase_min": ph.group(1) if ph else "",
            "phase_max": ph.group(1) if ph else "",
            "phase_ref": "explosion" if ph else "",
        })
    write_part(rows, SID)
    from collections import Counter
    print(f"SNe: {len(rows)} {dict(Counter(r['subclass'] for r in rows))}")


if __name__ == "__main__":
    main()
