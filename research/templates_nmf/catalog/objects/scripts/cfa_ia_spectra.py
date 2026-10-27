"""Inventario por objeto de los espectros CfA de SNe Ia (Blondin+12, AJ 143, 126).

Usa solo las tablas de VizieR J/AJ/143/126 (no el tarball de 164 MB de espectros):
- table1: SN, z heliocéntrico (NED), MJD del máximo en B.
- table3: 24 SNe cuyo z no viene de NED (con referencia del origen).
- table4: clasificación Wang+09 (N, HV, 91T, 91bg) para 246 SNe con espectro cerca del máximo.
- tablea1: diario de 2603 espectros, con la fase en reposo respecto del máximo en B.

Subclase: Wcl=91T -> Ia-91T; 91bg -> Ia-91bg; f_Wcl (peculiar, sin clase Wang) -> Ia-other;
resto (N, HV o sin clasificar) -> Ia.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fetch, fixed_width, fmt, raw_dir, write_part  # noqa: E402

SID = "cfa_ia_spectra"
VIZ = "https://cdsarc.cds.unistra.fr/ftp/J/AJ/143/126/"


def main():
    d = raw_dir(SID)
    p = {t: fetch(VIZ + t + ".dat", os.path.join(d, t + ".dat"))
         for t in ("table1", "table3", "table4", "tablea1")}
    t1 = fixed_width(p["table1"], [("SN", 1, 15), ("z", 17, 22), ("MJD", 24, 30)])
    t3 = fixed_width(p["table3"], [("SN", 1, 15), ("z", 41, 46), ("f_z", 48, 48),
                                   ("r_z", 50, 53)])
    t4 = fixed_width(p["table4"], [("SN", 1, 15), ("Wcl", 45, 48), ("f_Wcl", 50, 50)])
    a1 = fixed_width(p["tablea1"], [("SN", 1, 15), ("f_Phase", 44, 44), ("Phase", 45, 50)])

    ztype = {}
    for _, r in t3.iterrows():
        if r.f_z == "f":            # redshift de un cúmulo cercano
            ztype[r.SN] = "unknown"
        elif r.r_z == "SNID":       # del propio espectro de la SN
            ztype[r.SN] = "spec"
        elif r.r_z in ("abs", "em", "1"):  # líneas de la galaxia huésped
            ztype[r.SN] = "host_spec"
        else:                       # CBET / Bailey+09: origen no especificado
            ztype[r.SN] = "unknown"
    wang = {r.SN: (r.Wcl, r.f_Wcl) for _, r in t4.iterrows()}

    rows = []
    for _, r in t1.iterrows():
        sp = a1[a1.SN == r.SN]
        ph = sp[(sp.f_Phase != "@")].Phase.map(lambda x: float(x) if x else None).dropna()
        wcl, fw = wang.get(r.SN, ("", ""))
        if wcl == "91T":
            sub = "Ia-91T"
        elif wcl == "91bg":
            sub = "Ia-91bg"
        elif fw:
            sub = "Ia-other"
        else:
            sub = "Ia"
        rows.append({
            "sn_name": r.SN, "subclass": sub,
            "z": fmt(r.z, 4), "z_type": ztype.get(r.SN, "host_spec") if r.z else "",
            "n_spec": len(sp),
            "phase_min": fmt(ph.min(), 1) if len(ph) else "",
            "phase_max": fmt(ph.max(), 1) if len(ph) else "",
            "phase_ref": "peak" if len(ph) else "",
        })
    df = write_part(SID, rows)
    print("espectros totales:", df.n_spec.astype(int).sum())


if __name__ == "__main__":
    main()
