"""Inventario por objeto de Gomez+24 (catalogo de SLSN-I, repo gmzsebastian/SLSNe).

- slsne/ref_data/sne_data.txt: nombre, RA/Dec, Redshift, Method (origen del z), EBV,
  Explosion, Peak (MJD), Quality, Survey.
- slsne/ref_data/supernovae/<SN>/<SN>.txt: fotometria (MJD, Mag, Filter, UL, Ignore...).
n_phot cuenta detecciones (UL == False e Ignore == False); bands son los valores de Filter
de esas detecciones. Fase como en slsne.lcurve: (MJD - Peak)/(1+z), dias en reposo
respecto del pico en r (seccion 2 del paper).
EBV: el paper corrige por extincion de la Via Lactea con Schlafly & Finkbeiner (2011);
se interpreta la columna EBV como E(B-V)_MW.
Se fija el commit de main que se uso (raw/<sid>/commit.txt) y se baja todo de ese commit.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "gomez24_slsn_catalog"
REPO = "gmzsebastian/SLSNe"

ZTYPE = {"Host_lines": "host_spec", "Host_spectrum": "host_spec",
         "SN_features": "spec", "Mg_Lines": "spec", "Photo-z": "photo",
         "Lyman_break": "unknown", "Unknown": "unknown"}


def repo_commit(d):
    """Commit de main; se guarda la primera vez para que el script sea reproducible."""
    f = os.path.join(d, "commit.txt")
    if os.path.exists(f):
        return open(f).read().strip()
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/commits/main",
                                 headers=u.UA)
    sha = json.load(urllib.request.urlopen(req, timeout=60))["sha"]
    open(f, "w").write(sha)
    return sha


def read_table(path):
    lines = [ln.split() for ln in open(path, encoding="utf-8") if ln.strip()]
    head = lines[0]
    return [dict(zip(head, r)) for r in lines[1:]]


def main():
    d = u.raw_dir(SID)
    sha = repo_commit(d)
    base = f"https://raw.githubusercontent.com/{REPO}/{sha}/slsne/ref_data/"
    tab = read_table(u.fetch(base + "sne_data.txt", os.path.join(d, "sne_data.txt")))
    pdir = os.path.join(d, "phot")
    os.makedirs(pdir, exist_ok=True)

    rows = []
    for o in tab:
        sn = o["Name"]
        z = u.ffloat(o["Redshift"])
        peak = u.ffloat(o["Peak"])
        ph = read_table(u.fetch(base + f"supernovae/{sn}/{sn}.txt",
                                os.path.join(pdir, f"{sn}.txt")))
        det = [p for p in ph if p.get("UL") == "False" and p.get("Ignore") == "False"]
        row = dict(
            sn_name=sn, subclass="SLSN-I",
            ra=u.fmt(u.ffloat(o["RA_deg"]), 5), dec=u.fmt(u.ffloat(o["DEC_deg"]), 5),
            z=o["Redshift"], z_type=ZTYPE[o["Method"]],
            ebv_mw=o["EBV"], bands=";".join(sorted({p["Filter"] for p in det})),
            n_phot=len(det),
        )
        if det and peak is not None and z is not None:
            phase = [(float(p["MJD"]) - peak) / (1 + z) for p in det]
            row.update(phase_min=u.fmt(min(phase), 1), phase_max=u.fmt(max(phase), 1),
                       phase_ref="peak")
        rows.append(row)
    u.write_part(SID, rows)
    q = {}
    for o in tab:
        q[o["Quality"]] = q.get(o["Quality"], 0) + 1
    print("calidad:", q)


if __name__ == "__main__":
    main()
