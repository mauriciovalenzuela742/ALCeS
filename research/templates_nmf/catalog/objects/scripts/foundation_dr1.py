"""Inventario por objeto de Foundation DR1 (Foley+18, MNRAS 475, 193; arXiv:1711.02474).

- Curvas de luz: repo GitHub djones1040/Foundation_DR1 (zip de la rama master), archivos SNANA
  en Foundation_DR1/ (180 SNe cosmológicas) y Foundation_DR1_NoCosmo/ (45 que no pasan cortes).
  Del header: RA, DEC, MWEBV, REDSHIFT_HELIO, SEARCH_PEAKMJD; se cuentan las líneas OBS.
- Foundation_DR1.FITRES.TEXT: PKMJD del ajuste SALT2 (solo las 180).
- VizieR J/MNRAS/475/193 table1 (tipo y nombres), table3 (redshifts no catalogados y de dónde
  salen), table5 (clasificaciones actualizadas; ya reflejadas en table1).

Fase: (MJD - PKMJD) / (1 + z_helio); si no hay FITRES, SEARCH_PEAKMJD del header.
"""
import glob
import io
import os
import re
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fetch, fmt, raw_dir, viz_tsv, write_part  # noqa: E402

SID = "foundation_dr1"
ZIP = "https://codeload.github.com/djones1040/Foundation_DR1/zip/refs/heads/master"

# Type de table1 -> subclase ALCeS. Vacío = Ia normal.
TYPE = {"": "Ia", "91T": "Ia-91T", "91T?": "Ia-91T", "91bg": "Ia-91bg",
        "06gz": "Ia-other", "00cx?; 91bg?": "Ia-other", "Ic": "Ic"}


def key(s):
    s = re.sub(r"[^0-9A-Za-z]", "", str(s)).upper().replace("MASTEROT", "MASTER")
    return re.sub(r"^(SN|AT)(?=\d{4})", "", s)


def parse_snana(text):
    head, n, mjd, bands = {}, 0, [], set()
    for line in text.splitlines():
        if line.startswith("OBS:"):
            p = line.split()
            n += 1
            mjd.append(float(p[1]))
            bands.add(p[2])
        elif ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            head[k.strip()] = v.split("+-")[0].split("#")[0].strip()
    return head, n, mjd, bands


def main():
    d = raw_dir(SID)
    zp = fetch(ZIP, os.path.join(d, "Foundation_DR1-master.zip"))
    t1 = viz_tsv("J/MNRAS/475/193/table1", ["IAU", "DName", "AName", "Type"],
                 os.path.join(d, "table1.tsv"))
    t3 = viz_tsv("J/MNRAS/475/193/table3", ["SN", "z", "From"], os.path.join(d, "table3.tsv"))

    # índice de nombres de table1
    idx = {}
    for i, r in t1.iterrows():
        for nm in [r.IAU, r.DName] + re.split(r"[;,]", r.AName):
            if nm.strip():
                idx[key(nm)] = i
    zfrom = {key(r.SN): r.From for _, r in t3.iterrows()}

    def lookup(snid):
        k = key(snid)
        if k in idx:
            return idx[k]
        # nombres PSN/MASTER/CSS truncados en el repo: prefijo único
        for kk in (k, key(snid.split("-")[0]) if "-" in snid[4:] else None):
            if not kk or len(kk) < 8:
                continue
            c = {v for k2, v in idx.items() if k2.startswith(kk)}
            if len(c) == 1:
                return c.pop()
        return None

    rows, nomatch = [], []
    with zipfile.ZipFile(zp) as z:
        fit = z.read("Foundation_DR1-master/Foundation_DR1.FITRES.TEXT").decode()
        lines = [ln for ln in fit.splitlines() if ln.startswith(("VARNAMES:", "SN:"))]
        cols = lines[0].split()[1:]
        fr = pd.read_csv(io.StringIO("\n".join(" ".join(ln.split()[1:]) for ln in lines[1:])),
                         sep=" ", names=cols, dtype=str)
        pk = dict(zip(fr.CID, fr.PKMJD.astype(float)))
        files = sorted(n for n in z.namelist()
                       if re.match(r"Foundation_DR1-master/Foundation_DR1(_NoCosmo)?/"
                                   r"Foundation_DR1_.+\.txt$", n))
        for fn in files:
            head, n, mjd, bands = parse_snana(z.read(fn).decode("latin-1"))
            snid = head["SNID"]
            i = lookup(snid)
            if i is None:
                nomatch.append(snid)
                typ, names = "", []
            else:
                r = t1.loc[i]
                typ = r.Type
                names = [x.strip() for x in [r.IAU, r.DName] + re.split(r"[;,]", r.AName)
                         if x.strip()]
            iau = names[0] if i is not None and t1.loc[i].IAU else ""
            sn_name = ("SN " + iau) if iau else snid
            alt = [x for x in dict.fromkeys(names + [snid]) if key(x) != key(sn_name)]
            zh = float(head["REDSHIFT_HELIO"])
            peak = pk.get(snid, float(head.get("SEARCH_PEAKMJD", "nan")))
            ph = [(m - peak) / (1 + zh) for m in mjd] if peak == peak else []
            src = None
            for nm in names + [snid]:
                src = src or zfrom.get(key(nm))
            rows.append({
                "sn_name": sn_name, "alt_names": ";".join(alt),
                "subclass": TYPE[typ],
                "ra": fmt(head["RA"], 6), "dec": fmt(head["DECL"], 6),
                "z": fmt(zh, 5),
                # table3: 'SN' = de rasgos de la SN; 'nucleus'/'SN position' = líneas del host.
                # Resto: redshift catalogado (NED) del host.
                "z_type": "spec" if src == "SN" else "host_spec",
                "ebv_mw": fmt(head["MWEBV"], 4),
                "bands": ";".join(b for b in "griz" if b in bands),
                "n_phot": n,
                "phase_min": fmt(min(ph), 1) if ph else "",
                "phase_max": fmt(max(ph), 1) if ph else "",
                "phase_ref": "peak" if ph else "",
                "_cosmo": "NoCosmo" not in fn,
            })
    print("archivos:", len(files), " cosmo:", sum(r["_cosmo"] for r in rows))
    print("sin match en table1:", nomatch)
    for r in rows:
        r.pop("_cosmo")
    write_part(SID, rows)


if __name__ == "__main__":
    main()
