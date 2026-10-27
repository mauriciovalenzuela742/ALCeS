"""Inventario por objeto de Gutierrez+17 (espectros opticos de SNe II, CSP-I y previos).

Fuentes:
- Tablas del paper desde el fuente LaTeX de arXiv:1709.02487 (table_info.tex: velocidad de
  recesion, E(B-V)_MW de Schlafly+11, epoca de explosion, numero de espectros; table_spec.tex:
  fase de cada espectro en dias desde la explosion).
- Tarball de espectros de la pagina de datos de CSP (Gutierrez_et_al_2017.tar.gz, 8.7 MB):
  se cuentan los FITS por SN solo como control cruzado (no se usa para las columnas).

z = v_helio / c. z_type: 'host_spec' si la velocidad es de NED (sin superindice), 'spec' si
esta marcada como medida con espectros propios (^1), 'unknown' si viene del catalogo de Asiago
(^2). Fase: respecto de la explosion (phase_ref=explosion).
"""
import os
import re
import sys
import tarfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import C_KMS, fetch, raw_dir, write_part  # noqa: E402

SID = "csp_snii_spectra_gutierrez17"
ARXIV_SRC = "https://arxiv.org/src/1709.02487"
TARBALL = "https://csp.obs.carnegiescience.edu/data/Gutierrez_et_al_2017.tar.gz"


def tex_members(src_path):
    out = {}
    with tarfile.open(src_path, "r:*") as t:
        for m in t.getmembers():
            if m.isfile() and m.name.endswith(".tex"):
                out[os.path.basename(m.name)] = t.extractfile(m).read().decode("latin-1")
    return out


def strip_comments(text):
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("%"))


def parse_info(text):
    rows = {}
    for ln in strip_comments(text).splitlines():
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) != 10:
            continue
        name = cells[0]
        if not re.match(r"^(19|20)\d\d[A-Za-z]{1,2}$|^\d{3}$", name):
            continue
        vel = cells[2]
        vnum = re.match(r"^(\d+)", vel)
        if "$^1$" in vel:
            ztype = "spec"
        elif "$^2$" in vel:
            ztype = "unknown"
        else:
            ztype = "host_spec"
        nspec = re.match(r"^(\d+)", cells[8])
        rows[name] = {
            "v": float(vnum.group(1)) if vnum else None,
            "z_type": ztype,
            "ebv_mw": cells[4],
            "n_spec": int(nspec.group(1)) if nspec else None,
        }
    return rows


def parse_spec(text):
    phases = defaultdict(list)
    cur = None
    for ln in strip_comments(text).splitlines():
        m = re.search(r"multicolumn\{\d+\}\{c\}\{SN\s*([^}]+)\}", ln)
        if m:
            cur = m.group(1).strip()
            continue
        if cur is None:
            continue
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) >= 9 and re.match(r"^\d{4}-\d\d[-.]\d\d", cells[0]):  # 2008H trae "2008-01.17"
            ph = re.match(r"^[+-]?\d+(\.\d+)?", cells[2].replace("$", ""))
            phases[cur].append(float(ph.group(0)) if ph else None)
    return phases


def short(name):
    """'1986L' -> 'SN86L' (convencion de carpetas del tarball); '210' -> 'SN210'."""
    if re.match(r"^\d{4}", name):
        return "SN" + name[2:]
    return "SN" + name


def main():
    d = raw_dir(SID)
    src = fetch(ARXIV_SRC, os.path.join(d, "arxiv_1709.02487_src.tar.gz"))
    tb = fetch(TARBALL, os.path.join(d, "Gutierrez_et_al_2017.tar.gz"))
    tex = tex_members(src)
    info = parse_info(tex["table_info.tex"])
    spec = parse_spec(tex["table_spec.tex"])

    # Control: espectros por SN en el tarball (fechas distintas en el nombre del FITS).
    fits_files = Counter()
    fits_dates = defaultdict(set)
    with tarfile.open(tb, "r:gz") as t:
        for m in t.getmembers():
            if m.isfile() and m.name.endswith(".fits"):
                parts = m.name.split("/")
                fits_files[parts[1]] += 1
                dm = re.search(r"(\d\d[a-z]{3}\d\d)", parts[-1].lower())
                fits_dates[parts[1]].add(dm.group(1) if dm else parts[-1])

    rows = []
    for name, r in info.items():
        ph = [p for p in spec.get(name, []) if p is not None]
        rows.append({
            "sn_name": f"SN {name}",
            "source_id": SID,
            "subclass": "II",
            "z": round(r["v"] / C_KMS, 6) if r["v"] else "",
            "z_type": r["z_type"] if r["v"] else "",
            "ebv_mw": r["ebv_mw"],
            # Numero de filas de table_spec (suma 888, como el abstract); si la SN no aparece
            # alli, el 'N of spectra' de table_info.
            "n_spec": len(spec[name]) if spec.get(name) else r["n_spec"],
            "phase_min": min(ph) if ph else "",
            "phase_max": max(ph) if ph else "",
            "phase_ref": "explosion" if ph else "",
        })
    write_part(rows, SID)

    # Diagnostico.
    tot = sum(r["n_spec"] or 0 for r in info.values())
    print(f"SNe en table_info: {len(info)}; suma de 'N of spectra': {tot}")
    print(f"SNe en table_spec: {len(spec)}; filas de espectros: {sum(len(v) for v in spec.values())}")
    print(f"carpetas con FITS en el tarball: {len(fits_files)}; FITS: {sum(fits_files.values())}")
    only_spec = sorted(set(spec) - set(info))
    only_tar = sorted(set(fits_files) - {short(n) for n in info})
    print("en table_spec y no en table_info:", only_spec)
    print("en el tarball y no en table_info:", only_tar)
    diff = [(n, r["n_spec"], len(spec.get(n, [])), len(fits_dates.get(short(n), ())))
            for n, r in info.items() if r["n_spec"] != len(spec.get(n, []))]
    print("N distinto entre table_info y table_spec (SN, info, spec, fechas_tarball):", diff)


if __name__ == "__main__":
    main()
