"""Inventario por objeto de Modjaz+20 (hosts de PTF Ic e Ic-BL, arXiv:1901.00872).

No hay tabla en VizieR; se baja la fuente LaTeX de arXiv y se leen:
- tab:emission (tabla 2): region de la apertura (SNsite, nuc, HII o SDSS) y z del host.
- tab:PTFZ (tabla 4): tipo y 12+log(O/H) (pyMCZ) en D13_N2S2_O3S2, KD02_COMB, PP04_O3N2
  y M08_N2Halpha.
oh12 usa PP04_O3N2; si falta, M08_N2Halpha (oh12_calib dice cual).
oh12_type: host_local si la apertura es 'SNsite' (centrada en la region HII mas cercana al
sitio de la SN, seccion 3 del paper); 'unknown' para nuc/HII (lejos del sitio) y para los
dos hosts con espectro de fibra SDSS (PTF12gzk, PTF12hvv).
E(B-V)_host de la tabla 4 es el enrojecimiento del gas del host (decremento de Balmer),
no el de la linea de vision de la SN: no se copia a ebv_host.
No hay fotometria ni espectros de la SN en esta fuente (n_phot/n_spec vacios).
"""
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "ptf_ic_icbl_hosts_modjaz20"
ARXIV = "https://arxiv.org/e-print/1901.00872"

TYPE_MAP = {"Ic-bl": "Ic-BL", "Ic": "Ic", "Ic-peculiar": "Ic",
            "Ic/Ic-bl": "SN-other", "SLSN/Ic-bl": "SN-other", "Ib/c": "SN-other"}

# Erratas de la tabla del paper. PTF12gzk: tab:emission dice 0.148 (fila insertada a mano, ver
# comentario del .tex); Schulze+21 (fuente ptf_ccsn_hosts_schulze21) da z=0.01377, coherente con un host
# enano de M*=10^6.95 que el mismo paper llama el menos luminoso. Se usa 0.0138.
Z_FIX = {"PTF12gzk": 0.0138}


def rows_of(tex, label):
    i = tex.index(label)
    a = tex.index(r"\startdata", i) + len(r"\startdata")
    b = tex.index(r"\enddata", i)
    out = []
    for ln in tex[a:b].splitlines():
        s = ln.strip()
        if not s or s.startswith("%") or s.startswith("\\"):
            continue
        s = s.split("%")[0].rstrip().rstrip("\\").strip()
        cells = [c.strip() for c in s.split("&")]
        if len(cells) >= 3:
            out.append(cells)
    return out


def val(cell):
    m = re.match(r"^\s*([0-9]+\.[0-9]+)", cell)
    return float(m.group(1)) if m else None


def names(cell):
    """'10bzf/SN10ah' -> ('PTF10bzf', ['SN 2010ah'])."""
    cell = re.sub(r"\\tablenotemark\{\w\}", "", cell).strip()
    parts = cell.split("/")
    alt = []
    for p in parts[1:]:
        m = re.match(r"SN(\d\d)(\w+)", p)
        if m:
            alt.append(f"SN 20{m.group(1)}{m.group(2)}")
    return "PTF" + parts[0].strip(), alt


def main():
    d = u.raw_dir(SID)
    src = u.fetch(ARXIV, os.path.join(d, "arXiv_1901.00872_src.tar.gz"))
    with tarfile.open(src, "r:gz") as tf:
        tex = tf.extractfile("ms.tex").read().decode("utf-8", "replace")

    region, zhost = {}, {}
    for c in rows_of(tex, r"\label{tab:emission}"):
        n, _ = names(c[0])
        region[n] = c[1]
        zhost[n] = Z_FIX.get(n, val(c[2]))

    rows = []
    for c in rows_of(tex, r"\label{tab:PTFZ}"):
        n, alt = names(c[0])
        typ = c[1]
        pp04, m08 = val(c[5]), val(c[6])
        row = dict(sn_name=n, alt_names=";".join(alt), subclass=TYPE_MAP[typ])
        if zhost.get(n) is not None:
            row["z"] = u.fmt(zhost[n], 3)
            row["z_type"] = "host_spec"
        if pp04 is not None:
            row.update(oh12=u.fmt(pp04, 3), oh12_calib="O3N2_PP04")
        elif m08 is not None:
            row.update(oh12=u.fmt(m08, 3), oh12_calib="N2_M08")
        if "oh12" in row:
            row["oh12_type"] = "host_local" if region.get(n) == "SNsite" else "unknown"
        if n not in region:
            print(f"aviso: {n} sin fila en tab:emission")
        rows.append(row)
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
