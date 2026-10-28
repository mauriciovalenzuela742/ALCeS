"""Inventario por objeto de CSP-II NIR de SESN (Shahbandeh+22, arXiv:2110.12083).

- Lista de objetos y n_spec: archivos FITS de SESNe_NIR_reduced_data.tgz (pagina de datos
  de CSP, CC BY 4.0). Un FITS = un espectro.
- Tipo: tabla tab:classification del paper (columna "This work").
- z heliocentrico: tablas tab:redshift_JD y tab:1specs (z de host o de ATel; el paper no
  distingue, se marca host_spec solo para los de tab:redshift_JD, que tiene columna Host).
- Fase: columna Phase de tab:journal (dias respecto del maximo en B; para LSQ13ddu respecto
  del maximo LSQ-gr y para SN 2013dk respecto de V, segun notas de la tabla).
  Los 8 SNe de tab:1specs no tienen fase fiable y quedan sin fase.
Las tablas se leen de la fuente LaTeX de arXiv. Las coordenadas de tab:redshift_JD estan en
columnas ocultas y desalineadas (SN 2012P en adelante), por eso no se usan.
"""
import collections
import os
import re
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stripped_util as u  # noqa: E402

SID = "csp2_sesn_nir_spectra"
DATA = "https://csp.obs.carnegiescience.edu/data/SESNe_NIR_reduced_data.tgz"
ARXIV = "https://arxiv.org/e-print/2110.12083"

TYPE_MAP = {"IIb": "IIb", "Ib": "Ib", "Ic": "Ic", "Ic-BL": "Ic-BL", "Ibn": "Ibn",
            "Ic/Ic-BL": "SN-other"}


def norm(name):
    """'SN2013ak' -> 'SN 2013ak'; 'SN~2013ak' -> 'SN 2013ak'; el resto igual."""
    name = name.replace("~", " ").strip()
    m = re.match(r"^SN\s*(\d{4}\w+)$", name)
    return f"SN {m.group(1)}" if m else name


def table_rows(tex, label, start=r"\startdata", end=r"\enddata"):
    i = tex.index(label)
    body = tex[tex.index(start, i) + len(start):tex.index(end, i)]
    body = "\n".join(ln.split("%")[0] for ln in body.splitlines())  # quita comentarios
    rows = []
    for r in body.split("\\\\"):
        cells = [c.strip() for c in r.replace("\n", " ").split("&")]
        if len(cells) > 1 and cells[0]:
            rows.append(cells)
    return rows


def main():
    d = u.raw_dir(SID)
    tgz = u.fetch(DATA, os.path.join(d, "SESNe_NIR_reduced_data.tgz"))
    src = u.fetch(ARXIV, os.path.join(d, "arXiv_2110.12083_src.tar.gz"))

    with tarfile.open(tgz, "r:gz") as tf:
        files = [n for n in tf.getnames() if n.endswith(".fits")]
    nspec = collections.Counter(norm(os.path.basename(f).split("_")[0]) for f in files)

    with tarfile.open(src, "r:gz") as tf:
        tex = tf.extractfile("main.tex").read().decode("utf-8", "replace")

    # Tipos (tabla con tabular, no deluxetable)
    i = tex.index(r"\label{tab:classification}")
    j = tex.index(r"\end{tabular}", i)
    typ = {}
    for r in tex[i:j].split("\\\\"):
        cells = [c.strip() for c in r.split("&")]
        if len(cells) == 5:
            name = cells[0].splitlines()[-1].strip() if cells[0] else ""
            if name and not name.startswith("\\"):
                typ[norm(name)] = cells[2]

    z, ztype = {}, {}
    for c in table_rows(tex, r"\label{tab:redshift_JD}"):
        z[norm(c[0])] = float(c[2])
        ztype[norm(c[0])] = "host_spec"
    for c in table_rows(tex, r"\label{tab:1specs}"):
        z[norm(c[0])] = float(re.match(r"[0-9.]+", c[2]).group(0))
        ztype[norm(c[0])] = "unknown"

    phases = collections.defaultdict(list)
    for c in table_rows(tex, r"\label{tab:journal}"):
        ph = c[3].replace("$-$", "-").replace("+", "")
        phases[norm(c[0])].append(float(ph))

    rows = []
    for sn, n in nspec.items():
        t = typ.get(sn)
        row = dict(sn_name=sn, subclass=TYPE_MAP.get(t, "SN-other"), n_spec=n)
        if t is None:
            print(f"aviso: {sn} sin tipo en tab:classification -> SN-other")
        if sn in z:
            row["z"] = u.fmt(z[sn], 4)
            row["z_type"] = ztype[sn]
        ph = phases.get(sn)
        if ph:
            if len(ph) != n:
                print(f"aviso: {sn} tiene {n} FITS y {len(ph)} filas en tab:journal")
            row.update(phase_min=u.fmt(min(ph), 1), phase_max=u.fmt(max(ph), 1),
                       phase_ref="peak")
        rows.append(row)
    missing = set(z) - set(nspec)
    if missing:
        print("aviso: en el paper pero sin FITS:", sorted(missing))
    u.write_part(SID, rows)


if __name__ == "__main__":
    main()
