"""Inventario por objeto de Anderson+16 (metalicidad local de regiones HII de hosts de SNe II).

Fuente: fuente LaTeX de arXiv:1602.00011 (A&A 589, A110). No hay catalogo VizieR; se leen las
tablas del apendice:
- Tabla A.1 ('SN and host galaxy data'): velocidad de recesion del host (NED) y tipo
  ('*' = IIn, '**' = IIb; sin marca = II).
- Tabla B.2 ('hiilist'): abundancias de O de la region HII (M13 N2, M13 O3N2, PP04 N2, PP04 O3N2).
  Aqui '*' significa abundancia tomada de Anderson+10.

oh12 = M13 N2 (el diagnostico que usa el paper; disponible para todas). oh12_type=host_local.
z = V_r / c con z_type=host_spec (NED). Sin fotometria ni espectros de la SN (n_phot/n_spec
vacios): la fuente aporta la metalicidad.
"""
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import C_KMS, fetch, raw_dir, write_part  # noqa: E402

SID = "anderson16_snii_hii_metallicity"
ARXIV_SRC = "https://arxiv.org/src/1602.00011"
TEX = "SNII_Z_EWs_refv_proof.tex"
NAME_RE = re.compile(r"^((?:19|20)\d\d[A-Za-z]{1,2})(\*{0,2})$")


def read_tex(path):
    with tarfile.open(path, "r:*") as t:
        return t.extractfile(t.getmember(TEX)).read().decode("latin-1")


def tabulars(text):
    return re.findall(r"\\begin\{tabular\}(.*?)\\end\{tabular\}", text, re.S)


def rows_of(block):
    body = "\n".join(ln.split("%")[0] for ln in block.splitlines())
    for chunk in body.split("\\\\"):
        chunk = chunk.replace("\\hline", " ")  # la primera fila de cada bloque va tras \hline
        cells = [c.strip() for c in chunk.split("&")]
        if len(cells) < 3:
            continue
        m = NAME_RE.match(cells[0].replace(" ", ""))
        if m:
            yield m.group(1), m.group(2), cells


def num(cell):
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", cell)
    return float(m.group(1)) if m else None


def main():
    d = raw_dir(SID)
    text = read_tex(fetch(ARXIV_SRC, os.path.join(d, "arxiv_1602.00011_src.tar.gz")))
    hosts, hii = {}, {}
    for b in tabulars(text):
        if "V_{\\rm r}" in b:
            for name, mark, cells in rows_of(b):
                sub = {"*": "IIn", "**": "IIb"}.get(mark, "II")
                hosts[name] = (num(cells[2]), sub)
        elif "M13 N2" in b:
            for name, mark, cells in rows_of(b):
                hii[name] = (num(cells[2]), mark == "*")

    rows = []
    for name in sorted(set(hosts) | set(hii)):
        v, sub = hosts.get(name, (None, "II"))
        oh, _ = hii.get(name, (None, False))
        rows.append({
            "sn_name": f"SN {name}",
            "source_id": SID,
            "subclass": sub,
            "z": round(v / C_KMS, 6) if v else "",
            "z_type": "host_spec" if v else "",
            "oh12": oh if oh is not None else "",
            "oh12_type": "host_local" if oh is not None else "",
            "oh12_calib": "N2_M13" if oh is not None else "",
        })
    write_part(rows, SID)
    from collections import Counter
    print(f"Tabla A.1: {len(hosts)} SNe {dict(Counter(s for _, s in hosts.values()))}")
    print(f"Tabla B.2: {len(hii)} SNe con abundancia ({sum(1 for _, a in hii.values() if a)} de Anderson+10)")
    print("en B.2 y no en A.1:", sorted(set(hii) - set(hosts)))
    print("en A.1 y no en B.2:", sorted(set(hosts) - set(hii)))


if __name__ == "__main__":
    main()
