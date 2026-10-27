"""Inventario por objeto de CfA3 (Hicken+09, J/ApJ/700/331) y CfA4 (Hicken+12, J/ApJS/200/12).

Tablas de VizieR (sistema estándar):
- CfA3 table1 (nombre, coordenadas), table5 (curvas de luz), table8 (zCMB y extinción del
  host de MLCS2k2 para 134 SNe con buen muestreo).
- CfA4 table1 (coordenadas, z helio y CMB, E(B-V) MW), table6 (curvas de luz).

Sin fecha de máximo en estas tablas: las fases quedan vacías.
Subclase: los papers no dan subtipo por objeto en estas tablas -> 'Ia'.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fetch, fixed_width, fmt, raw_dir, sex2deg, write_part  # noqa: E402

SID = "cfa3_cfa4_photometry"
V3 = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/700/331/"
V4 = "https://cdsarc.cds.unistra.fr/ftp/J/ApJS/200/12/"
FILT3 = {"1": "U", "2": "B", "3": "V", "4": "R", "5": "I", "13": "r'", "14": "i'"}
ORDER = ["U", "u'", "B", "V", "R", "r'", "I", "i'"]


def name(sn):
    """'snf20080522000' -> 'SNF20080522-000'; '2006ct' -> 'SN 2006ct'; 'PTF10bjs' igual."""
    m = re.match(r"^snf(\d{8})(\d{3})$", sn, re.I)
    if m:
        return f"SNF{m.group(1)}-{m.group(2)}"
    if re.match(r"^\d{4}[A-Za-z]+$", sn):
        return "SN " + sn
    return sn


def radec(r):
    return sex2deg(f"{r.RAh} {r.RAm} {r.RAs}", f"{r.DE}{r.DEd} {r.DEm} {r.DEs}")


def summarize(lc, bandmap=None):
    out = {}
    for sn, g in lc.groupby("SN"):
        b = {bandmap.get(x, x) if bandmap else x for x in g.Filt}
        out[sn] = {"bands": set(b), "n": len(g)}
    return out


def main():
    d = raw_dir(SID)
    f = {}
    for t in ("table1", "table5", "table8"):
        f["3" + t] = fetch(V3 + t + ".dat", os.path.join(d, f"cfa3_{t}.dat"))
    for t in ("table1", "table6"):
        f["4" + t] = fetch(V4 + t + ".dat", os.path.join(d, f"cfa4_{t}.dat"))

    pos = [("RAh", 0, 0), ("RAm", 0, 0), ("RAs", 0, 0), ("DE", 0, 0), ("DEd", 0, 0),
           ("DEm", 0, 0), ("DEs", 0, 0)]
    c3 = fixed_width(f["3table1"], [("SN", 1, 6)] + [
        (n, a, b) for (n, _, _), (a, b) in zip(
            pos, [(33, 34), (36, 37), (39, 44), (46, 46), (47, 48), (50, 51), (53, 57)])])
    lc3 = fixed_width(f["3table5"], [("SN", 1, 6), ("Filt", 8, 9)])
    t8 = fixed_width(f["3table8"], [("SN", 1, 6), ("zCMB", 8, 13), ("EBV", 84, 89)])
    c4 = fixed_width(f["4table1"], [("SN", 1, 14)] + [
        (n, a, b) for (n, _, _), (a, b) in zip(
            pos, [(16, 17), (19, 20), (22, 27), (29, 29), (30, 31), (33, 34), (36, 40)])]
        + [("z", 72, 77), ("zCMB", 79, 84), ("EBVmw", 86, 91)])
    lc4 = fixed_width(f["4table6"], [("SN", 1, 14), ("Filt", 16, 17)])

    s3 = summarize(lc3, FILT3)
    s4 = summarize(lc4)
    t8 = {r.SN: r for _, r in t8.iterrows()}

    rows = {}
    for _, r in c3.iterrows():
        ra, dec = radec(r)
        s = s3.get(r.SN, {"bands": set(), "n": 0})
        e = t8.get(r.SN)
        rows[r.SN] = {
            "sn_name": name(r.SN), "subclass": "Ia", "ra": fmt(ra, 6), "dec": fmt(dec, 6),
            # zCMB de la table8 (solo 134 SNe); el paper no dice si es del host o de la SN.
            "z": fmt(e.zCMB, 4) if e is not None else "",
            "z_type": "unknown" if e is not None else "",
            "ebv_host": fmt(e.EBV, 4) if e is not None and e.EBV else "",
            "_bands": s["bands"], "n_phot": s["n"],
        }
    for _, r in c4.iterrows():
        ra, dec = radec(r)
        s = s4.get(r.SN, {"bands": set(), "n": 0})
        row = {
            "sn_name": name(r.SN), "subclass": "Ia", "ra": fmt(ra, 6), "dec": fmt(dec, 6),
            # z helio "principalmente de NED" (galaxia huésped) según la nota de table1.
            "z": fmt(r.z, 4), "z_type": "host_spec" if r.z else "",
            "ebv_mw": fmt(r.EBVmw, 4), "_bands": s["bands"], "n_phot": s["n"],
        }
        if r.SN in rows:  # SN en ambos: se suman los puntos y se unen las bandas
            old = rows[r.SN]
            old["_bands"] |= row["_bands"]
            old["n_phot"] += row["n_phot"]
            for k in ("z", "z_type", "ebv_mw"):
                old[k] = row[k] or old.get(k, "")
        else:
            rows[r.SN] = row
    out = []
    for r in rows.values():
        b = r.pop("_bands")
        r["bands"] = ";".join([x for x in ORDER if x in b] + sorted(b - set(ORDER)))
        out.append(r)
    both = set(c3.SN) & set(c4.SN)
    print(f"CfA3: {len(c3)}  CfA4: {len(c4)}  en ambos: {len(both)} {sorted(both)}")
    df = write_part(SID, out)
    print("puntos:", df.n_phot.astype(int).sum())


if __name__ == "__main__":
    main()
