"""Inventario por objeto de Hicken+17 (CfA: curvas opticas/NIR y espectros de SNe II).

Fuentes (archivo CfA, lweb.cfa.harvard.edu/supernova/fmalcolm2017/):
- cfa_snII_lightcurvesndstars.june2017.tar (0.5 MB): CFA_SNII_NATSYSTEM_LC.txt (optico, sistema
  natural; el estandar tiene las mismas filas) y CFA_SNII_NIR_LC.txt.
- cfaspec_snII.tar.gz (12.6 MB): cfasnII_mjdspec.dat (un renglon por espectro).
- Tabla 1 del paper (fuente LaTeX de arXiv:1706.01030): tipo, z_helio, numero de espectros.

z_type: el paper dice que z_helio es del host (NED) salvo 2006at (CBET 441), 2006iw
(D'Andrea+) y 2008bx (CBET 1359): esas tres quedan 'unknown'. Sin fase (el paper no tabula
epoca de pico ni de explosion).
"""
import os
import re
import sys
import tarfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch, raw_dir, write_part  # noqa: E402

SID = "cfa_snii_hicken17"
BASE = "https://lweb.cfa.harvard.edu/supernova/fmalcolm2017/"
LC_TAR = "cfa_snII_lightcurvesndstars.june2017.tar"
SPEC_TAR = "cfaspec_snII.tar.gz"
ARXIV_SRC = "https://arxiv.org/src/1706.01030"
TEX = "CfA_Type_II_LC_Spectra_Paper_ToSubmit.tex"
Z_NOT_HOST = {"SN2006at", "SN2006iw", "SN2008bx"}
BAND_ORDER = ["u'", "U", "B", "V", "R", "r'", "I", "i'", "J", "H", "K"]
TYPES = {"II": "II", "IIP": "IIP", "IIn": "IIn", "IIb": "IIb", "Ibn": "Ibn"}


def member_text(tar_path, suffix):
    with tarfile.open(tar_path, "r:*") as t:
        for m in t.getmembers():
            if m.isfile() and m.name.endswith(suffix) and not os.path.basename(m.name).startswith("._"):
                return t.extractfile(m).read().decode("latin-1")
    raise KeyError(suffix)


def parse_table1(tex):
    block = tex.split("label{table_snlist}")[1].split("enddata")[0]
    out = {}
    for ln in block.splitlines():
        cells = [c.strip() for c in ln.split("&")]
        if len(cells) != 8 or not cells[0].startswith("SN"):
            continue
        typ = re.sub(r"tablenotemark\{\d\}", "", cells[1]).strip().strip(chr(92)).strip()
        nspec = re.match(r"\d+", cells[7])
        out[cells[0]] = {"type": typ, "z": cells[3], "n_spec_tab": int(nspec.group(0)) if nspec else None,
                         "opt": cells[5] == "y", "nir": cells[6] == "y"}
    return out


def count_phot(text, counts):
    for ln in text.splitlines():
        if ln.startswith("#"):
            continue
        p = ln.split()
        if len(p) >= 4:
            counts[p[0]][p[1]] += 1


def main():
    d = raw_dir(SID)
    lc = fetch(BASE + LC_TAR, os.path.join(d, LC_TAR))
    sp = fetch(BASE + SPEC_TAR, os.path.join(d, SPEC_TAR))
    src = fetch(ARXIV_SRC, os.path.join(d, "arxiv_1706.01030_src.tar.gz"))
    table = parse_table1(member_text(src, TEX))

    opt, nir = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    count_phot(member_text(lc, "CFA_SNII_NATSYSTEM_LC.txt"), opt)
    count_phot(member_text(lc, "CFA_SNII_NIR_LC.txt"), nir)
    nspec = defaultdict(int)
    for ln in member_text(sp, "cfasnII_mjdspec.dat").splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        name = ln.split("-")[0]
        nspec["SN" + name[2:]] += 1

    rows = []
    for sn, r in table.items():
        bands = {**opt.get(sn, {}), **{("K" if b.startswith("K") else b): n for b, n in nir.get(sn, {}).items()}}
        nphot = sum(opt.get(sn, {}).values()) + sum(nir.get(sn, {}).values())
        rows.append({
            "sn_name": sn,
            "source_id": SID,
            "subclass": TYPES.get(r["type"], "SN-other"),
            "z": r["z"],
            "z_type": "unknown" if sn in Z_NOT_HOST else "host_spec",
            "bands": ";".join(b for b in BAND_ORDER if bands.get(b)),
            "n_phot": str(nphot) if nphot else "",
            "n_spec": str(nspec.get(sn, 0)),
        })
    write_part(rows, SID)

    from collections import Counter
    print(f"SNe en tabla 1: {len(table)} {dict(Counter(r['type'] for r in table.values()))}")
    print(f"opticas: {len(opt)} SNe, {sum(sum(v.values()) for v in opt.values())} puntos; "
          f"NIR: {len(nir)} SNe, {sum(sum(v.values()) for v in nir.values())} puntos")
    print(f"espectros (mjdspec): {sum(nspec.values())} de {len(nspec)} SNe; "
          f"suma '# Spectra' tabla 1: {sum(r['n_spec_tab'] or 0 for r in table.values())}")
    print("SNe con fotometria/espectros fuera de tabla 1:", sorted((set(opt) | set(nir) | set(nspec)) - set(table)))
    diff = [(s, r["n_spec_tab"], nspec.get(s, 0)) for s, r in table.items() if r["n_spec_tab"] != nspec.get(s, 0)]
    print("# espectros distinto (SN, tabla1, archivo):", diff)


if __name__ == "__main__":
    main()
