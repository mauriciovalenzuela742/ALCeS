"""Informe de viabilidad por subclase a partir del inventario por objeto.

Uso:
    python viability.py [--parts objects/parts] [--out-md viability.md]
                        [--out-csv objects/merged.csv]

Une las filas de todas las fuentes por nombre (y por posición, si hay ra/dec) y cuenta por
subclase cuántos objetos cumplen cada nivel:

- `foto`:      redshift espectroscópico, >= MIN_BANDS bandas y >= MIN_PHOT puntos.
- `espectro`:  `foto` y >= MIN_SPEC espectros.
- `completo`:  `espectro`, metalicidad y distancia usable (independiente o z >= Z_HF).

Las sumas de espectros y puntos entre fuentes pueden contar dos veces los mismos datos si dos
fuentes publican lo mismo; por eso los umbrales son conservadores y el informe lo advierte.
"""
import argparse
import glob
import math
import os
import re
import sys
from collections import Counter, defaultdict

import pandas as pd

MIN_BANDS = 3
MIN_PHOT = 15
MIN_SPEC = 3
Z_HF = 0.01  # por debajo, las velocidades peculiares dominan la distancia por redshift
MATCH_ARCSEC = 3.0

REQUIRED = ["sn_name", "source_id", "subclass"]
OPTIONAL = [
    "alt_names", "ra", "dec", "z", "z_type", "dist_mod", "dist_method", "ebv_mw", "ebv_host",
    "bands", "n_phot", "n_spec", "phase_min", "phase_max", "phase_ref", "oh12", "oh12_type",
    "oh12_calib",
]

# Subclase -> clase de template. II, IIP y IIL se agrupan como en SNANA/PLAsTiCC.
TEMPLATE_CLASS = {"IIP": "II", "IIL": "II"}

# Orden de especificidad para resolver conflictos de tipo entre fuentes.
GENERIC = {"II", "Ia", "SN-other", "Ia-other"}


def norm_name(name):
    """'SN 2004et' -> '2004et'; 'AT2019abc' -> '2019abc'; 'ZTF19aaa' -> 'ztf19aaa'."""
    s = str(name).strip().lower().replace(" ", "").replace("_", "")
    s = re.sub(r"^(sn|at|psn)(?=\d{4})", "", s)
    return s


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def load_parts(parts_dir):
    files = sorted(glob.glob(os.path.join(parts_dir, "*.csv")))
    if not files:
        sys.exit(f"no hay CSV en {parts_dir}")
    frames = []
    for f in files:
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        missing = [c for c in REQUIRED if c not in d.columns]
        if missing:
            sys.exit(f"{f}: faltan columnas {missing}")
        for c in OPTIONAL:
            if c not in d.columns:
                d[c] = ""
        frames.append(d[REQUIRED + OPTIONAL])
    return pd.concat(frames, ignore_index=True)


def group_objects(df):
    """Asigna un id de objeto uniendo nombres y posiciones."""
    uf = UnionFind()
    for i, row in df.iterrows():
        key = ("row", i)
        uf.find(key)
        names = [row["sn_name"]] + [n for n in row["alt_names"].split(";") if n.strip()]
        for n in names:
            uf.union(key, ("name", norm_name(n)))

    # Cruce por posición con una grilla de celdas del tamaño del radio.
    cell = MATCH_ARCSEC / 3600.0
    buckets = defaultdict(list)
    pos = {}
    for i, row in df.iterrows():
        try:
            ra, dec = float(row["ra"]), float(row["dec"])
        except ValueError:
            continue
        pos[i] = (ra, dec)
        buckets[(int(ra // cell), int(dec // cell))].append(i)
    for i, (ra, dec) in pos.items():
        cx, cy = int(ra // cell), int(dec // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in buckets.get((cx + dx, cy + dy), []):
                    if j <= i:
                        continue
                    ra2, dec2 = pos[j]
                    dra = (ra - ra2) * math.cos(math.radians(dec))
                    if math.hypot(dra, dec - dec2) * 3600.0 <= MATCH_ARCSEC:
                        uf.union(("row", i), ("row", j))
    return [uf.find(("row", i)) for i in df.index]


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def merge(df):
    df = df.copy()
    df["obj"] = group_objects(df)
    rows = []
    for _, g in df.groupby("obj", sort=False):
        subs = [TEMPLATE_CLASS.get(s, s) for s in g["subclass"]]
        counts = Counter(subs)
        specific = [s for s in counts if s not in GENERIC]
        if len(specific) == 1:
            sub = specific[0]
        else:
            sub = counts.most_common(1)[0][0]
        conflict = len(set(specific)) > 1
        bands = sorted({b for v in g["bands"] for b in v.split(";") if b.strip()})
        zs = g[g["z_type"].isin(["spec", "host_spec"])]["z"].map(to_float).dropna()
        z_any = g["z"].map(to_float).dropna()
        oh = g["oh12"].map(to_float).dropna()
        indep = (g["dist_method"] == "independent").any()
        rows.append({
            "name": g["sn_name"].iloc[0],
            "subclass": sub,
            "type_conflict": ";".join(sorted(set(specific))) if conflict else "",
            "sources": ";".join(sorted(set(g["source_id"]))),
            "n_sources": g["source_id"].nunique(),
            "z": zs.iloc[0] if len(zs) else (z_any.iloc[0] if len(z_any) else math.nan),
            "spec_z": len(zs) > 0,
            "indep_dist": indep,
            "n_bands": len(bands),
            "bands": ";".join(bands),
            "n_phot": int(g["n_phot"].map(to_float).fillna(0).sum()),
            "n_spec": int(g["n_spec"].map(to_float).fillna(0).sum()),
            "oh12": oh.iloc[0] if len(oh) else math.nan,
            "has_oh12": len(oh) > 0,
        })
    m = pd.DataFrame(rows)
    m["foto"] = m["spec_z"] & (m["n_bands"] >= MIN_BANDS) & (m["n_phot"] >= MIN_PHOT)
    m["espectro"] = m["foto"] & (m["n_spec"] >= MIN_SPEC)
    m["dist_ok"] = m["indep_dist"] | (m["spec_z"] & (m["z"] >= Z_HF))
    m["completo"] = m["espectro"] & m["has_oh12"] & m["dist_ok"]
    return m


def report(m, df):
    t = m.groupby("subclass").agg(
        objetos=("name", "size"),
        spec_z=("spec_z", "sum"),
        foto=("foto", "sum"),
        espectro=("espectro", "sum"),
        metalicidad=("has_oh12", "sum"),
        completo=("completo", "sum"),
        conflictos=("type_conflict", lambda s: (s != "").sum()),
    ).sort_values("objetos", ascending=False)
    lines = [
        "# Viabilidad de templates NMF por subclase",
        "",
        "Generado por `viability.py`. No editar a mano.",
        "",
        f"- Filas de entrada: {len(df)} de {df['source_id'].nunique()} fuentes; "
        f"objetos únicos tras cruzar nombres y posiciones (≤{MATCH_ARCSEC:g}\"): {len(m)}.",
        f"- `foto`: z espectroscópico, ≥{MIN_BANDS} bandas y ≥{MIN_PHOT} puntos.",
        f"- `espectro`: `foto` y ≥{MIN_SPEC} espectros.",
        f"- `completo`: `espectro`, metalicidad y distancia usable "
        f"(independiente o z ≥ {Z_HF}).",
        "- Los conteos de puntos y espectros suman entre fuentes: si dos fuentes publican los "
        "mismos datos, se cuentan dos veces.",
        "",
        "| Subclase | Objetos | z espec. | foto | espectro | Metalicidad | completo | Conflictos de tipo |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sub, r in t.iterrows():
        lines.append(
            f"| {sub} | {r.objetos} | {r.spec_z} | {r.foto} | {r.espectro} | "
            f"{r.metalicidad} | {r.completo} | {r.conflictos} |"
        )
    lines += ["", "## Fuentes incluidas", ""]
    for sid, n in df["source_id"].value_counts().items():
        lines.append(f"- `{sid}`: {n} filas")
    return "\n".join(lines) + "\n", t


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default=os.path.join(here, "objects", "parts"))
    ap.add_argument("--out-md", default=os.path.join(here, "viability.md"))
    ap.add_argument("--out-csv", default=os.path.join(here, "objects", "merged.csv"))
    args = ap.parse_args(argv)

    df = load_parts(args.parts)
    m = merge(df)
    md, table = report(m, df)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(md)
    m.to_csv(args.out_csv, index=False)
    print(table.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
