"""Inventario por objeto de Stritzinger+18 (CSP-I SE SNe, J/A+A/609/A134).

table1: coordenadas, z heliocentrico (NED o lineas del host en el espectro de la SN),
tipo, T(B)max (JD-2450000, columna F7.2).
table4/5: optico (u g r i B V) en sistemas naturales Swope y du Pont.
table6/7/8: NIR (Y J H) Swope (RC1, RC2) y du Pont.
n_phot cuenta magnitudes no nulas (todas las bandas). La fase se calcula sobre todas
las epocas con alguna medida: (JD - T(B)max) / (1+z), dias en reposo respecto del
maximo en B.
Extincion del host: el paper companero (Stritzinger+18b, arXiv:1707.07615) no esta en
VizieR. Se baja su fuente LaTeX de arXiv y se lee la tabla tab:EVMX; ebv_host es
-E(V-B)_host (21 SNe). Las SNe "minimally reddened" y las 3 sin cobertura (2006fo,
2008gc, 2009ca) no tienen valor en esa tabla y quedan vacias.
"""
import re
import tarfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "csp1_se_photometry_stritzinger18"
CAT = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/609/A134/"

OPT = ["u", "g", "r", "i", "B", "V"]
NIR = ["Y", "J", "H"]
TYPE_MAP = {"IIb": "IIb", "Ib": "Ib", "Ic": "Ic", "Ic-BL": "Ic-BL"}


def read_phot(path, bands, start=20):
    out = []
    for ln in open(path, encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 1, 6)
        jd = float(u.fw(ln, 8, 17))
        got = []
        for k, b in enumerate(bands):
            a = start + 14 * k
            if u.ffloat(u.fw(ln, a, a + 5)) is not None:
                got.append(b)
        out.append((sn, jd, got))
    return out


def read_ebv_host(d):
    src = u.fetch("https://arxiv.org/e-print/1707.07615",
                  os.path.join(d, "arXiv_1707.07615_src.tar.gz"))
    with tarfile.open(src, "r:gz") as tf:
        tex = tf.extractfile("ms.tex").read().decode("utf-8", "replace")
    i = tex.index(r"\label{tab:EVMX}")
    body = tex[tex.index(r"\startdata", i):tex.index(r"\enddata", i)]
    out = {}
    for ln in body.splitlines()[1:]:
        cells = [c.strip() for c in ln.replace("\\\\", "").split("&")]
        if len(cells) < 4:
            continue
        m = re.match(r"(\$-\$)?\s*([0-9.]+)\(", cells[3])  # columna E(V-B)_host
        if m:
            evb = float(m.group(2)) * (-1 if m.group(1) else 1)
            out[cells[0]] = -evb
    return out


def main():
    d = u.raw_dir(SID)
    files = ["ReadMe", "table1.dat"] + [f"table{i}.dat" for i in (4, 5, 6, 7, 8)]
    for f in files:
        u.fetch(CAT + f, os.path.join(d, f))

    objs = {}
    for ln in open(os.path.join(d, "table1.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 1, 6)
        objs[sn] = dict(
            ra=u.sexa_ra(u.fw(ln, 8, 9), u.fw(ln, 11, 12), u.fw(ln, 14, 18)),
            dec=u.sexa_dec(u.fw(ln, 20, 20), u.fw(ln, 21, 22), u.fw(ln, 24, 25),
                           u.fw(ln, 27, 30)),
            z=u.ffloat(u.fw(ln, 76, 81)),
            type=u.fw(ln, 113, 118), tmax=u.ffloat(u.fw(ln, 129, 135)),
            ph1=u.fw(ln, 120, 122), ph2=u.fw(ln, 124, 127),
        )

    meas = []
    for t in (4, 5):
        meas += read_phot(os.path.join(d, f"table{t}.dat"), OPT)
    for t in (6, 7, 8):
        meas += read_phot(os.path.join(d, f"table{t}.dat"), NIR)

    ebvh = read_ebv_host(d)
    rows = []
    for sn, o in objs.items():
        m = [x for x in meas if x[0] == sn]
        bands = set()
        n = 0
        for _, _, got in m:
            bands.update(got)
            n += len(got)
        row = dict(
            sn_name=f"SN {sn}", subclass=TYPE_MAP[o["type"]],
            ra=u.fmt(o["ra"], 5), dec=u.fmt(o["dec"], 5),
            bands=";".join(b for b in OPT + NIR if b in bands), n_phot=n,
            ebv_host=u.fmt(ebvh.get(sn), 3),
        )
        if o["z"] is not None:
            row["z"] = u.fmt(o["z"], 4)
            # NED (espectroscopico del host) o lineas del host en el espectro de la SN
            row["z_type"] = "host_spec"
        jds = [jd for _, jd, got in m if got]
        if jds and o["tmax"] is not None and o["z"] is not None:
            t0 = 2450000.0 + o["tmax"]
            ph = [(jd - t0) / (1 + o["z"]) for jd in jds]
            row.update(phase_min=u.fmt(min(ph), 1), phase_max=u.fmt(max(ph), 1),
                       phase_ref="peak")
            if "-v" in sys.argv:
                print(sn, row["phase_min"], row["phase_max"], "tabla1:", o["ph1"], o["ph2"])
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
