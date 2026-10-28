"""Inventario por objeto de Aamer+25 (espectros de SLSN-I, arXiv:2503.21874).

Los espectros procesados de Aamer+25 estan en el repo gmzsebastian/SLSNe (el README pide
citar Aamer+25 por los "processed spectra"), en
slsne/ref_data/supernovae/<SN>/processed_spectra/<SN>_<YYYY.MMDD>.txt.
No se bajan los espectros (el directorio supernovae pesa ~590 MB): se cuenta desde el arbol
del repo (API de GitHub) fijado a un commit. z y Peak salen de sne_data.txt del mismo
commit (catalogo de Gomez+24, mismos objetos). Fase = (MJD(fecha del archivo) - Peak)/(1+z);
la fecha del nombre de archivo tiene resolucion de un dia.
Tambien se reporta en pantalla cuantos espectros 'raw_spectra' hay, para comparar.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "aamer25_slsn_spectra"
REPO = "gmzsebastian/SLSNe"
ZTYPE = {"Host_lines": "host_spec", "Host_spectrum": "host_spec",
         "SN_features": "spec", "Mg_Lines": "spec", "Photo-z": "photo",
         "Lyman_break": "unknown", "Unknown": "unknown"}


def main():
    d = u.raw_dir(SID)
    f = os.path.join(d, "commit.txt")
    if not os.path.exists(f):
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/git/ref/heads/main",
                                     headers=u.UA)
        open(f, "w").write(json.load(urllib.request.urlopen(req, timeout=60))["object"]["sha"])
    sha = open(f).read().strip()
    tree = json.load(open(u.fetch(
        f"https://api.github.com/repos/{REPO}/git/trees/{sha}?recursive=1",
        os.path.join(d, "tree.json"))))
    assert not tree.get("truncated"), "arbol truncado"
    sne = u.fetch(f"https://raw.githubusercontent.com/{REPO}/{sha}/slsne/ref_data/sne_data.txt",
                  os.path.join(d, "sne_data.txt"))
    lines = [ln.split() for ln in open(sne, encoding="utf-8") if ln.strip()]
    meta = {r[0]: dict(zip(lines[0], r)) for r in lines[1:]}

    proc, raw = {}, {}
    pat = re.compile(r"^slsne/ref_data/supernovae/([^/]+)/(processed|raw)_spectra/(.+)\.txt$")
    for x in tree["tree"]:
        m = pat.match(x["path"])
        if not m or x["type"] != "blob":
            continue
        sn, kind, fname = m.groups()
        (proc if kind == "processed" else raw).setdefault(sn, []).append(fname)

    mjd0 = dt.date(1858, 11, 17)
    rows = []
    for sn, files in proc.items():
        o = meta.get(sn, {})
        row = dict(sn_name=sn, subclass="SLSN-I", n_spec=len(files))
        z = u.ffloat(o.get("Redshift"))
        peak = u.ffloat(o.get("Peak"))
        if z is not None:
            row.update(z=o["Redshift"], z_type=ZTYPE.get(o.get("Method"), "unknown"),
                       ra=u.fmt(u.ffloat(o["RA_deg"]), 5), dec=u.fmt(u.ffloat(o["DEC_deg"]), 5),
                       ebv_mw=o["EBV"])
        ph = []
        for fn in files:
            m = re.search(r"_(\d{4})\.(\d{2})(\d{2})", fn)
            if m and peak is not None and z is not None:
                day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                ph.append(((day - mjd0).days - peak) / (1 + z))
        if ph:
            row.update(phase_min=u.fmt(min(ph), 1), phase_max=u.fmt(max(ph), 1),
                       phase_ref="peak")
        rows.append(row)
    u.write_part(SID, rows)
    print(f"processed: {sum(map(len, proc.values()))} espectros de {len(proc)} SNe; "
          f"raw: {sum(map(len, raw.values()))} de {len(raw)} SNe")


if __name__ == "__main__":
    main()
