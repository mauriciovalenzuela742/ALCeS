"""Inventario por objeto de Perley+16 (hosts de 32 SLSN de PTF, arXiv:1604.08207).

Sin tabla en VizieR: se baja la fuente LaTeX de arXiv y se leen
- tab:slsne (tabla 1): coordenadas de la SN, clase (I, II, I-R), z, E(B-V) galactico
  (Schlafly & Finkbeiner 2011) y notas con el nombre IAU.
- tab:linediagnostics (tabla 6): 12+log(O/H) en varias calibraciones. Se usa la columna
  "PP04 O3" (O3N2 de Pettini & Pagel 2004 calculado con el codigo de Bianco+16), para
  ser comparable con Modjaz+20. Las cotas superiores ("<") se dejan vacias.
oh12_type = host_global: la extraccion incluye todo el flujo nebular del host (seccion 3.4);
excepcion PTF10tpz, cuyo espectro es solo de la region nuclear -> unknown.
Clase I-R (tipo R, lento) se asigna a SLSN-I. z_type queda 'unknown' porque la tabla 1
no dice si el z es del host o de la SN.
"""
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "ptf_slsn_hosts_perley16"
ARXIV = "https://arxiv.org/e-print/1604.08207"
CLASS = {"I": "SLSN-I", "I-R": "SLSN-I", "II": "SLSN-II"}
NUCLEAR_ONLY = {"PTF10tpz"}


def rows_of(tex, label):
    j = tex.index(label)
    i = tex.rindex(r"\startdata", 0, j) + len(r"\startdata")
    b = tex.index(r"\enddata", i)
    out = []
    for ln in tex[i:b].splitlines():
        s = ln.split("%")[0].strip()
        if not s or s.startswith("\\"):
            continue
        s = s.rstrip().rstrip("\\").strip()
        out.append([c.strip() for c in s.split("&")])
    return out


def first_num(cell):
    if "<" in cell:
        return None
    m = re.search(r"([0-9]+\.[0-9]+)", cell)
    return float(m.group(1)) if m else None


def main():
    d = u.raw_dir(SID)
    src = u.fetch(ARXIV, os.path.join(d, "arXiv_1604.08207_src.tar.gz"))
    with tarfile.open(src, "r:gz") as tf:
        tex = tf.extractfile("slsnhosts.tex").read().decode("utf-8", "replace")

    oh = {}
    for c in rows_of(tex, r"\label{tab:linediagnostics}"):
        oh["PTF" + c[0]] = first_num(c[9])  # PTF ID, SFR, AV, Best, Te, N06N2, N06R23, D02, PP04N2, PP04O3

    rows = []
    for c in rows_of(tex, r"\label{tab:slsne}"):
        name = "PTF" + c[0]
        ra = c[1].split(":")
        de = c[2].replace("$", "").split(":")
        sign = "-" if de[0].startswith("-") else "+"
        alt = ";".join(f"SN {m}" for m in re.findall(r"SN\\,(\d{4}\w+)", c[8]))
        row = dict(
            sn_name=name, alt_names=alt, subclass=CLASS[c[3]],
            ra=u.fmt(u.sexa_ra(*ra), 5),
            dec=u.fmt(u.sexa_dec(sign, de[0].lstrip("+-"), de[1], de[2]), 5),
            z=c[4], z_type="unknown", ebv_mw=c[7],
        )
        v = oh.get(name)
        if v is not None:
            row.update(oh12=u.fmt(v, 2), oh12_calib="O3N2_PP04",
                       oh12_type="unknown" if name in NUCLEAR_ONLY else "host_global")
        if name not in oh:
            print(f"aviso: {name} sin fila en la tabla 6")
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
