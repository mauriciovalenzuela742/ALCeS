"""Inventario por objeto de Modjaz+14 (espectros CfA de SESN, J/AJ/147/99).

table2: tipo (SNID), cz heliocentrico del host, JD del maximo en V.
table1: diario de observaciones, un registro por espectro, con la fase en el sistema
en reposo respecto del maximo en V. Los espectros marcados con '@' tienen fase respecto
del primer espectro (no hay maximo fiable); si una SN tiene alguno, su rango de fase
queda vacio.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "cfa_sesn_spectra_modjaz14"
CAT = "https://cdsarc.cds.unistra.fr/ftp/J/AJ/147/99/"
C_KMS = 299792.458

TYPE_MAP = {
    "Ib": "Ib", "Ic": "Ic", "IIb": "IIb", "Ic-bl": "Ic-BL", "Ib-pec": "Ib",
    "Ib-n": "Ibn", "Ib-n/IIb-n": "Ibn",
    "Ib/c": "SN-other", "Ic/Ic-bl": "SN-other",  # ambiguos en la fuente
}


def main():
    d = u.raw_dir(SID)
    for f in ("ReadMe", "table1.dat", "table2.dat"):
        u.fetch(CAT + f, os.path.join(d, f))

    objs = {}
    for ln in open(os.path.join(d, "table2.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 1, 6)
        objs[sn] = dict(type=u.fw(ln, 8, 17), cz=u.ffloat(u.fw(ln, 73, 77)))

    spec = {}
    for ln in open(os.path.join(d, "table1.dat"), encoding="latin-1"):
        if not ln.strip():
            continue
        sn = u.fw(ln, 4, 9)
        flag = u.fw(ln, 36, 36)
        ph = u.ffloat(u.fw(ln, 37, 44))
        spec.setdefault(sn, []).append((flag, ph))

    rows = []
    for sn in sorted(set(objs) | set(spec)):
        o = objs.get(sn)
        if o is None:
            print(f"aviso: {sn!r} esta en table1 pero no en table2; se omite")
            continue
        s = spec.get(sn, [])
        row = dict(sn_name=f"SN {sn}", subclass=TYPE_MAP[o["type"]], n_spec=len(s))
        if o["cz"] is not None:
            row["z"] = u.fmt(o["cz"] / C_KMS, 5)
            row["z_type"] = "host_spec"
        good = [p for f, p in s if f != "@" and p is not None]
        if good and len(good) == len(s):
            row.update(phase_min=u.fmt(min(good), 1), phase_max=u.fmt(max(good), 1),
                       phase_ref="peak")
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
