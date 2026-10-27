"""Inventario por objeto de CSP-I: fotometría DR3 (Krisciunas+17) + espectros DR1 (Folatelli+13).

Fuentes:
- https://csp.obs.carnegiescience.edu/data/CSP_Photometry_DR3.tgz (tab1 + archivos SNooPy)
- https://csp.obs.carnegiescience.edu/data/CSP_spectra_DR1.tgz (un .dat por espectro)
- VizieR J/AJ/154/211 table2 (subtipo) y table3 (fecha de máximo)

Fase: días en el reposo, (t - T(Bmax)) / (1 + z). Si falta T(Bmax) se usa Tpeak (todas las
bandas). Cubre fotometría y espectros. Tiempos SNooPy en JD - 2453000 (verificado contra
la table7 de VizieR).
"""
import glob
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fetch, fixed_width, fmt, raw_dir, sex2deg, write_part  # noqa: E402

SID = "csp_i_ia"
BASE = "https://csp.obs.carnegiescience.edu/data/"
VIZ = "https://cdsarc.cds.unistra.fr/ftp/J/AJ/154/211/"

# Subtipo SNID de la table2 de Krisciunas+17 -> subclase ALCeS.
SUBTYPE = {
    "normal": "Ia", "91bg-like": "Ia-91bg", "91T-like": "Ia-91T", "Iax": "Iax",
    "Ia-CSM": "Ia-CSM", "SC": "Ia-other", "06gz-like": "Ia-other",
    "06bt-like": "Ia-other", "86G-like": "Ia-other", "---": "Ia", "": "Ia",
}
# Códigos de filtro de SN_photo/SNooPy -> banda física.
BAND = {"V0": "V", "V1": "V", "Jrc2": "J", "Ydw": "Y", "Jdw": "J", "Hdw": "H"}
BAND_ORDER = "u B g V r i Y J H".split()


def main():
    d = raw_dir(SID)
    for f in ("CSP_Photometry_DR3.tgz", "CSP_spectra_DR1.tgz"):
        p = fetch(BASE + f, os.path.join(d, f))
        top = "DR3" if "Photometry" in f else "CSP_spectra_DR1"
        if not os.path.isdir(os.path.join(d, top)):
            with tarfile.open(p) as t:
                t.extractall(d, filter="data")
    for t in ("table2", "table3"):
        fetch(VIZ + t + ".dat", os.path.join(d, f"vz_{t}.dat"))

    t2 = fixed_width(os.path.join(d, "vz_table2.dat"), [("SN", 1, 6), ("sub", 20, 28)])
    t3 = fixed_width(os.path.join(d, "vz_table3.dat"),
                     [("SN", 1, 6), ("TB", 8, 15), ("Tpeak", 22, 29)])
    sub = dict(zip(t2.SN, t2["sub"]))
    tmax = {}
    for _, r in t3.iterrows():
        for c in ("TB", "Tpeak"):
            try:
                tmax[r.SN] = float(r[c]) + 2400000.5 - 2453000.0  # MJD -> JD-2453000
                break
            except ValueError:
                continue

    # tab1: nombre, coordenadas, z helio (NED/SDSS)
    tab1 = {}
    with open(os.path.join(d, "DR3", "tab1.dat"), encoding="latin-1") as f:
        next(f)
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = [x.strip() for x in line.split("\t")]
            tab1[p[0]] = p

    # Espectros DR1: contar por objeto y guardar la época (reposo, ya calculada en el header).
    spec = {}
    for fn in glob.glob(os.path.join(d, "CSP_spectra_DR1", "SN*.dat")):
        obj, ep = None, None
        with open(fn, encoding="latin-1") as f:
            for line in f:
                if not line.startswith("#"):
                    break
                if line.startswith("#Object:"):
                    obj = line.split(":", 1)[1].strip()
                elif line.startswith("#Epoch:"):
                    try:
                        ep = float(line.split(":", 1)[1])
                    except ValueError:
                        pass
        if obj:
            spec.setdefault(re.sub(r"^SN", "", obj), []).append(ep)

    rows = []
    for fn in sorted(glob.glob(os.path.join(d, "DR3", "SN*_snpy.txt"))):
        with open(fn, encoding="latin-1") as f:
            head = f.readline().split()
            name = head[0].replace("SN", "", 1)
            z = float(head[1])
            bands, n, ts = set(), 0, []
            cur = None
            for line in f:
                if line.startswith("filter"):
                    cur = line.split()[1]
                    continue
                p = line.split()
                if len(p) >= 3 and cur:
                    bands.add(BAND.get(cur, cur))
                    n += 1
                    ts.append(float(p[0]))
        t1 = tab1.get(name)
        ra, dec = (sex2deg(t1[1], t1[2]) if t1 else (None, None))
        phases = []
        if name in tmax:
            phases = [(t - tmax[name]) / (1 + z) for t in ts]
        sp = [e for e in spec.get(name, []) if e is not None]
        allp = phases + sp
        rows.append({
            "sn_name": "SN " + name,
            "subclass": SUBTYPE[sub.get(name, "")],
            "ra": fmt(ra, 6), "dec": fmt(dec, 6),
            "z": fmt(t1[5] if t1 else z, 4), "z_type": "host_spec",
            "bands": ";".join(b for b in BAND_ORDER if b in bands)
                     + "".join(";" + b for b in sorted(bands - set(BAND_ORDER))),
            "n_phot": n, "n_spec": len(spec.get(name, [])),
            "phase_min": fmt(min(allp), 1) if allp else "",
            "phase_max": fmt(max(allp), 1) if allp else "",
            "phase_ref": "peak" if allp else "",
        })
    missing = sorted(set(spec) - {r["sn_name"][3:] for r in rows})
    if missing:
        print("espectros sin fotometría DR3:", missing)
    write_part(SID, rows)


if __name__ == "__main__":
    main()
