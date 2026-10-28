"""Inventario por objeto de Pantheon+ (Scolnic+22 / Brout+22, arXiv:2112.03863, 2202.04077).

Archivo: Pantheon+_Data/4_DISTANCES_AND_COVAR/Pantheon+SH0ES.dat del repo GitHub
PantheonPlusSH0ES/DataRelease (1701 curvas de luz de 1550 SNe; una SN puede aparecer
varias veces si la observaron varios surveys). Se colapsa a una fila por CID:
- z = zHEL (primera aparición). El archivo no dice si viene del host o de la SN -> unknown.
- Calibradores (IS_CALIBRATOR=1): dist_mod = CEPH_DIST (distancia Cefeida del host),
  dist_method = independent.
- Resto: dist_mod = media de MU_SH0ES entre apariciones (Tripp estandarizado),
  dist_method = hubble_flow.
- ebv_mw = MWEBV. Sin bandas/puntos: la fotometría es la de los surveys originales
  (CSP, CfA, Foundation...) y contarla aquí la duplicaría.

CIDs puramente numéricos (SDSS, PS1, DES, SNLS...) se prefijan con el survey
('SDSS-16314') para que no choquen entre surveys ni con nombres IAU.
"""
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fetch, fmt, raw_dir, write_part  # noqa: E402

SID = "pantheon_plus"
URL = ("https://raw.githubusercontent.com/PantheonPlusSH0ES/DataRelease/main/"
       "Pantheon%2B_Data/4_DISTANCES_AND_COVAR/Pantheon%2BSH0ES.dat")
SURVEY = {1: "SDSS", 4: "SNLS", 5: "CSP", 10: "DES", 15: "PS1MD", 18: "CNIa0.02",
          50: "LOWZ/JRK07", 51: "LOSS1", 56: "SOUSA", 57: "LOSS2", 61: "CFA1", 62: "CFA2",
          63: "CFA3S", 64: "CFA3K", 65: "CFA4p2", 66: "CFA4p3", 100: "HST", 101: "SNAP",
          106: "CANDELS", 150: "FOUND"}


def name(cid, surveys):
    cid = str(cid)
    if re.fullmatch(r"\d{4}[a-z]{1,3}", cid) or re.fullmatch(r"\d{4}[A-Z]", cid):
        return "SN " + cid
    if re.fullmatch(r"\d+", cid):
        return f"{SURVEY.get(surveys[0], surveys[0])}-{cid}"
    return cid


def main():
    d = raw_dir(SID)
    t = pd.read_csv(fetch(URL, os.path.join(d, "Pantheon+SH0ES.dat")), sep=r"\s+")
    # '2005df_ANU' y '2008fv_comb' son la misma SN que '2005df'/'2008fv' (otra reducción).
    t["SNKEY"] = t.CID.str.replace(r"^(\d{4}[a-z]+)_\w+$", lambda m: m.group(1), regex=True)
    rows = []
    for cid, g in t.groupby("SNKEY", sort=False):
        r = g.iloc[0]
        cal = (g.IS_CALIBRATOR == 1).any()
        if cal:
            dm, meth = g.CEPH_DIST.iloc[0], "independent"
        else:
            dm, meth = g.MU_SH0ES.mean(), "hubble_flow"
        surveys = list(g.IDSURVEY)
        rows.append({
            "sn_name": name(cid, surveys),
            "alt_names": ";".join(x for x in dict.fromkeys([str(cid)] + list(g.CID))
                                  if x != name(cid, surveys)),
            "subclass": "Ia",
            "ra": fmt(r.RA, 6), "dec": fmt(r.DEC, 6),
            "z": fmt(r.zHEL, 5), "z_type": "unknown",
            "dist_mod": fmt(dm, 4), "dist_method": meth,
            "ebv_mw": fmt(r.MWEBV, 4),
        })
    print("curvas de luz:", len(t), " CID únicos:", t.CID.nunique(), " SNe:", t.SNKEY.nunique(),
          " calibradores:", t[t.IS_CALIBRATOR == 1].CID.nunique())
    write_part(SID, rows)


if __name__ == "__main__":
    main()
