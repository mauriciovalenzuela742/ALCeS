"""Inventario por objeto de Galbany+16 (UBVRIz de 51 SNe II: CTSS, C&T, SOIRS, CATS).

Fuentes:
- Repositorio de los autores github.com/lgalbany/51_SNeII_LC (tarball 51_SNII_LC.tar.gz, 55 kB,
  Zenodo 10.5281/zenodo.1172117): por SN un .info (tipo, zhel, RA, Dec, E(B-V)_MW, m-M) y un
  .out_<banda> por filtro con las fotometrias.
- Tabla 1 del paper (sn_table.tex del fuente LaTeX de arXiv:1511.08402) para el origen del
  redshift y de la distancia y para las notas de subtipo:
    z con '^*' = medido por los autores -> z_type=spec; si no, NED -> host_spec.
    DM con nota d o f = Tully-Fisher de NED -> independent; nota e = "medido con datos de SN II"
    -> unknown; sin nota = distancia de luminosidad por redshift (H0=68) -> hubble_flow.
    nota g = parecida a 1987A, nota h = IIb.

La banda sale del sufijo del archivo (.out_B, ...), no de la linea 'Filter:', porque un archivo
tiene esa linea mal. n_phot cuenta filas de datos (no la linea 'Npoints').
"""
import os
import re
import sys
import tarfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, raw_dir, write_part  # noqa: E402

SID = "galbany16_ubvriz"
TARBALL = "https://raw.githubusercontent.com/lgalbany/51_SNeII_LC/HEAD/51_SNII_LC.tar.gz"
ARXIV_SRC = "https://arxiv.org/src/1511.08402"
BAND_ORDER = ["U", "B", "V", "R", "I", "z"]
BS = chr(92)  # barra invertida (evita escapes en este archivo)


def short_to_name(s):
    """'sn1986l' -> '1986L'; 'sn2003bg' -> '2003bg'; 'sn200210' -> '200210'."""
    m = re.match(r"^sn(\d{4})([a-z]*)$", s)
    if not m:
        return s[2:] if s.startswith("sn") else s
    yr, suf = m.groups()
    return yr + (suf.upper() if len(suf) == 1 else suf)


def parse_sn_table(text):
    out = {}
    for ln in text.splitlines():
        if ln.lstrip().startswith("%"):
            continue
        ln = ln.split("%")[0]
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) < 9:
            continue
        name_cell = cells[0]
        m = re.match(r"^(\d{6}|\d{4}[A-Za-z]{0,2})", name_cell)
        if not m:
            continue
        notes = set(re.findall(r"tablenotemark\{(\w)\}", name_cell))
        dm_notes = set(re.findall(r"tablenotemark\{(\w)\}", cells[7]))
        out[m.group(1)] = {
            "z_star": "^*" in cells[5],
            "dm_note": "".join(sorted(dm_notes)),
            "notes": notes,
        }
    return out


def main():
    d = raw_dir(SID)
    tb = fetch(TARBALL, os.path.join(d, "51_SNII_LC.tar.gz"))
    src = fetch(ARXIV_SRC, os.path.join(d, "arxiv_1511.08402_src.tar.gz"))
    with tarfile.open(src, "r:*") as t:
        table = parse_sn_table(t.extractfile(t.getmember("sn_table.tex")).read().decode("latin-1"))

    info = {}
    phot = defaultdict(lambda: defaultdict(int))
    with tarfile.open(tb, "r:gz") as t:
        for m in t.getmembers():
            base = os.path.basename(m.name)
            if not m.isfile() or base.startswith("._") or base.startswith("."):
                continue
            sn = base.split(".")[0]
            text = t.extractfile(m).read().decode("latin-1")
            if base.endswith(".info"):
                kv = {}
                for ln in text.splitlines():
                    if ":" in ln:
                        k, v = ln.split(":", 1)
                        kv[k.strip().lower()] = v.strip()
                info[sn] = kv
            elif ".out_" in base:
                band = base.split(".out_")[1]
                band = "z" if band.upper() == "Z" else band.upper()
                for ln in text.splitlines():
                    if re.match(r"^\s*\d{5}(\.\d+)?\s+-?\d", ln):
                        phot[sn][band] += 1

    rows = []
    for sn, kv in sorted(info.items()):
        name = short_to_name(sn)
        tab = table.get(name, {})
        notes = tab.get("notes", set())
        typ = kv.get("type", "")
        if "h" in notes:
            sub = "IIb"
        elif "g" in notes:  # parecida a 1987A: se deja como II generica
            sub = "II"
        elif typ == "SNIIP":
            sub = "IIP"
        else:
            sub = "II"
        dm_note = tab.get("dm_note")
        if dm_note is None:
            dmeth = ""
        elif set(dm_note) & {"d", "f"}:
            dmeth = "independent"
        elif "e" in dm_note:
            dmeth = "unknown"
        else:
            dmeth = "hubble_flow"
        p = phot.get(sn, {})
        rows.append({
            "sn_name": f"SN {name}",
            "source_id": SID,
            "subclass": sub,
            "ra": kv.get("ra", ""),
            "dec": kv.get("dec", ""),
            "z": kv.get("zhel", ""),
            "z_type": ("spec" if tab.get("z_star") else "host_spec") if kv.get("zhel") and tab else "",
            "dist_mod": kv.get("distance(m-m)", ""),
            "dist_method": dmeth if kv.get("distance(m-m)") else "",
            "ebv_mw": kv.get("e(b-v)_mw", ""),
            "bands": ";".join(b for b in BAND_ORDER if p.get(b)),
            "n_phot": str(sum(p.values())) if p else "",
        })
    write_part(rows, SID)
    print(f"SNe con .info: {len(info)}; en tabla 1 del paper: {len(table)}")
    print("sin cruce con la tabla 1:", [short_to_name(s) for s in info if short_to_name(s) not in table])
    print(f"puntos totales (filas de datos): {sum(sum(p.values()) for p in phot.values())}")
    print("tipos en .info:", sorted({kv.get('type', '') for kv in info.values()}))


if __name__ == "__main__":
    main()
