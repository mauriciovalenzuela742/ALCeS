"""Inventario por objeto de Nyholm+20 (42 SNe IIn de PTF/iPTF).

Fuentes:
- Fuente LaTeX de arXiv:1906.05812: tabla 'IInsummary' (coordenadas, z heliocentrico, mu,
  E(B-V)_MW, nombres alternativos) y tabla 'speclog' (un espectro de clasificacion por SN, con
  fase respecto del pico en dias de sistema en reposo).
- Fotometria: VizieR J/A+A/637/A73 (FTP de CDS). Si CDS no responde, el script escribe las
  filas sin bands/n_phot y avisa ('FOTOMETRIA NO DISPONIBLE'); al volver a correrlo con CDS
  accesible, las completa.

z: medido por los autores ajustando gaussianas a Halpha en sus espectros -> z_type=spec.
mu: a partir de z con LCDM (H0=70) y correccion por infall -> dist_method=hubble_flow.
"""
import os
import re
import sys
import tarfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, parse_sexa, raw_dir, write_part  # noqa: E402

SID = "ptf_iin_nyholm20"
ARXIV_SRC = "https://arxiv.org/src/1906.05812"
TEX = "IIn-sample-paper-v4-match-journal.tex"
CDS = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/637/A73/"
# CDS principal primero; si no responde, el espejo de IDIA (Sudafrica) sirve las mismas tablas.
VIZIER_MIRRORS = ["vizier.cds.unistra.fr", "vizier.idia.ac.za"]
BAND_ORDER =["B", "g", "R", "r", "i", "z"]


def strip_tex(s):
    s = re.sub(r"\\object\{([^}]*)\}", r"\1", s)
    s = s.replace("$", "").replace("~", " ").replace("{", "").replace("}", "")
    return s.strip()


def table_block(tex, label):
    return tex.split("label{" + label + "}")[1].split("enddata")[0]


def parse_summary(tex):
    out = {}
    for ln in table_block(tex, "tab:IInsummary").splitlines():
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) < 9 or "object" not in cells[0]:
            continue
        name = strip_tex(cells[0])
        ra, dec = parse_sexa(strip_tex(cells[1]), strip_tex(cells[2]))
        alt = strip_tex(cells[8]).replace(chr(92), "")
        alts = [] if alt in ("--", "-") else [a.strip().replace(" ", "") for a in alt.split(",")]
        out[name] = {"ra": round(ra, 6), "dec": round(dec, 6), "z": strip_tex(cells[3]),
                     "mu": strip_tex(cells[4]), "ebv": strip_tex(cells[6]), "alt": alts}
    return out


def parse_speclog(tex):
    out = defaultdict(list)
    for ln in table_block(tex, "tab:speclog").splitlines():
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) >= 5 and re.match(r"^i?PTF\d", cells[0]):
            m = re.match(r"^-?\d+(\.\d+)?$", cells[2])
            out[cells[0]].append(float(cells[2]) if m else None)
    return out


def cds_bytes(readme):
    """{archivo: [(ini, fin, label), ...]} a partir de las secciones Byte-by-byte."""
    out = {}
    for sec in re.split(r"Byte-by-byte Description of file:\s*", readme)[1:]:
        fname = sec.split()[0]
        cols = []
        for ln in sec.splitlines()[1:]:
            m = re.match(r"^\s*(\d+)-\s*(\d+)\s+\S+\s+\S+\s+(\S+)", ln) or \
                re.match(r"^\s*(\d+)()\s+\S+\s+\S+\s+(\S+)", ln)
            if m:
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else a
                cols.append((a, b, m.group(3)))
            if ln.startswith("---") and cols:
                break
        out[fname] = cols
    return out


def count_photometry(d):
    readme = open(fetch(CDS + "ReadMe", os.path.join(d, "ReadMe")), encoding="latin-1").read()
    layout = cds_bytes(readme)
    counts = defaultdict(lambda: defaultdict(int))
    used = []
    for fname, cols in layout.items():
        labels = [c[2] for c in cols]
        name_col = next((c for c in cols if c[2] in ("SN", "Name", "ID")), None)
        filt_col = next((c for c in cols if c[2].lower() in ("filt", "filter", "band")), None)
        mag_col = next((c for c in cols if c[2].lower() in ("mag", "abmag", "magab")), None)
        if not (name_col and filt_col and mag_col):
            continue
        used.append((fname, labels))
        path = fetch(CDS + fname, os.path.join(d, fname))
        if path.endswith(".gz"):
            import gzip
            text = gzip.open(path, "rt", encoding="latin-1").read()
        else:
            text = open(path, encoding="latin-1").read()
        for ln in text.splitlines():
            sn = ln[name_col[0] - 1:name_col[1]].strip()
            band = ln[filt_col[0] - 1:filt_col[1]].strip()
            mag = ln[mag_col[0] - 1:mag_col[1]].strip()
            try:
                v = float(mag)
            except ValueError:
                continue
            if v < 90:  # 99 = no detectada (limite superior)
                counts[sn][band] += 1
    print("archivos de CDS usados:", used)
    return counts


def count_photometry_vizier(d):
    """Lo mismo desde la tabla J/A+A/637/A73/table2 de VizieR (asu-tsv), probando espejos."""
    last = None
    for host in VIZIER_MIRRORS:
        url = (f"https://{host}/viz-bin/asu-tsv?-source=J/A%2BA/637/A73/table2"
               "&-out=Name,Filter,mag&-out.max=unlimited")
        try:
            path = fetch(url, os.path.join(d, "table2.tsv"), timeout=120)
            break
        except Exception as e:
            last = e
    else:
        raise last
    counts = defaultdict(lambda: defaultdict(int))
    header = None
    for ln in open(path, encoding="utf-8").read().splitlines():
        if not ln or ln.startswith("#"):
            continue
        cells = ln.split("\t")
        if header is None:
            header = [c.strip() for c in cells]
            continue
        if set(ln.strip()) <= set("-\t ") or len(cells) != len(header):
            continue  # fila de unidades o separadores
        r = dict(zip(header, (c.strip() for c in cells)))
        try:
            float(r["mag"])  # vacio = limite superior (lmag)
        except ValueError:
            continue
        counts[r["Name"]][r["Filter"]] += 1
    print("fotometria desde VizieR:", path)
    return counts


def main():
    d = raw_dir(SID)
    with tarfile.open(fetch(ARXIV_SRC, os.path.join(d, "arxiv_1906.05812_src.tar.gz")), "r:*") as t:
        tex = t.extractfile(t.getmember(TEX)).read().decode("latin-1")
    summ = parse_summary(tex)
    spec = parse_speclog(tex)

    counts = {}
    for fn in (count_photometry_vizier, count_photometry):
        try:
            counts = fn(d)
            break
        except Exception as e:  # CDS caido o bloqueado
            print(f"{fn.__name__} fallo ({e.__class__.__name__}: {e})")
    else:
        print("FOTOMETRIA NO DISPONIBLE")

    rows = []
    for name, r in summ.items():
        c = counts.get(name, {})
        ph = [p for p in spec.get(name, []) if p is not None]
        rows.append({
            "sn_name": name,
            "alt_names": ";".join(r["alt"]),
            "source_id": SID,
            "subclass": "IIn",
            "ra": r["ra"], "dec": r["dec"],
            "z": r["z"], "z_type": "spec",
            "dist_mod": r["mu"], "dist_method": "hubble_flow",
            "ebv_mw": r["ebv"],
            "bands": ";".join([b for b in BAND_ORDER if c.get(b)] + [b for b in sorted(c) if b not in BAND_ORDER]),
            "n_phot": str(sum(c.values())) if c else "",
            "n_spec": str(len(spec.get(name, []))) if spec.get(name) else "",
            "phase_min": min(ph) if ph else "",
            "phase_max": max(ph) if ph else "",
            "phase_ref": "peak" if ph else "",
        })
    write_part(rows, SID)
    print(f"SNe en IInsummary: {len(summ)}; en speclog: {len(spec)}; con fotometria: {len(counts)}")
    if counts:
        print("puntos detectados:", sum(sum(v.values()) for v in counts.values()),
              "| SNe de fotometria fuera de la tabla:", sorted(set(counts) - set(summ)))


if __name__ == "__main__":
    main()
