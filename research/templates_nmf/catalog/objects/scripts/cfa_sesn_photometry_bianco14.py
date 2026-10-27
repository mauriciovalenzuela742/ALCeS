"""Inventario por objeto de Bianco+14 (CfA SESN, J/ApJS/213/19).

Tablas: table1 (tipo, coordenadas, fecha de descubrimiento), table2 (host: cz NED,
m-M NED/HyperLEDA, E(B-V) MW de Schlafly & Finkbeiner 2011), table6 (fotometria en
sistema estandar, una fila por medida).
Fase: respecto de la fecha de descubrimiento de table1 (el ReadMe de VizieR no trae
fecha de maximo), en dias del observador. Si el ano de la fecha de descubrimiento no
coincide con el nombre de la SN (error de transcripcion, p. ej. SN 2009jf) la fase
queda vacia.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "cfa_sesn_photometry_bianco14"
CAT = "https://cdsarc.cds.unistra.fr/ftp/J/ApJS/213/19/"
C_KMS = 299792.458

TYPE_MAP = {
    "Ib": "Ib", "Ic": "Ic", "IIb": "IIb", "Ic-BL": "Ic-BL", "Ib-pec": "Ib",
    "Ib-n": "Ibn", "Ib-n/IIb-n": "Ibn", "Ib (Ca rich)": "Ca-rich",
    "Ic/Ic-BL": "SN-other",  # ambiguo en la fuente
}


def main():
    d = u.raw_dir(SID)
    for f in ("ReadMe", "table1.dat", "table2.dat", "table6.dat"):
        u.fetch(CAT + f, os.path.join(d, f))

    objs = {}
    for ln in open(os.path.join(d, "table1.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 4, 9)
        typ = u.fw(ln, 45, 56)
        ra = u.sexa_ra(u.fw(ln, 24, 25), u.fw(ln, 27, 28), u.fw(ln, 30, 31))
        dec = u.sexa_dec(u.fw(ln, 33, 33), u.fw(ln, 34, 35), u.fw(ln, 37, 38),
                         u.fw(ln, 40, 43).rstrip(".") or "0")
        disc = dt.datetime.strptime(u.fw(ln, 58, 68), "%Y %b %d")
        objs[sn] = dict(type=typ, ra=ra, dec=dec, disc=disc)

    for ln in open(os.path.join(d, "table2.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 4, 9)
        o = objs[sn]
        o["cz"] = u.ffloat(u.fw(ln, 42, 46))
        o["mu"] = u.ffloat(u.fw(ln, 70, 74))
        o["ebv"] = u.ffloat(u.fw(ln, 105, 110))

    phot = {}
    for ln in open(os.path.join(d, "table6.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 1, 6)
        band = u.fw(ln, 8, 9)
        mjd = float(u.fw(ln, 11, 21))
        phot.setdefault(sn, []).append((band, mjd))

    mjd0 = dt.datetime(1858, 11, 17)
    rows = []
    for sn, o in objs.items():
        pts = phot.get(sn, [])
        bands = sorted({b for b, _ in pts})
        row = dict(
            sn_name=f"SN {sn}", subclass=TYPE_MAP[o["type"]],
            ra=u.fmt(o["ra"], 5), dec=u.fmt(o["dec"], 5),
            ebv_mw=u.fmt(o.get("ebv"), 4),
            bands=";".join(bands), n_phot=len(pts),
        )
        if o.get("cz") is not None:
            row["z"] = u.fmt(o["cz"] / C_KMS, 5)
            row["z_type"] = "host_spec"  # cz heliocentrico del host segun NED
        if o.get("mu") is not None:
            row["dist_mod"] = u.fmt(o["mu"], 2)
            row["dist_method"] = "unknown"  # NED/HyperLEDA, metodo no especificado
        if pts and o["disc"].year == int(sn[:4]):
            t0 = (o["disc"] - mjd0).days
            ph = [m - t0 for _, m in pts]
            row.update(phase_min=u.fmt(min(ph), 1), phase_max=u.fmt(max(ph), 1),
                       phase_ref="discovery")
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
