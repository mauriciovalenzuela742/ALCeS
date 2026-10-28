"""Inventario por objeto de los hosts de SNe Ia de SNfactory (Childress+13, ApJ 770, 107).

Tabla VizieR J/ApJ/770/107/galaxies (une tablas 1, 4, 5 y 6 del paper), bajada por asu-tsv.
Una fila por SN. Columnas usadas:
- z: redshift heliocéntrico del host (sección 2.3.2) -> z_type=host_spec.
- ZT04: metalicidad gaseosa final en la escala de Tremonti+04; n_ZT04 dice el indicador
  original (N2 PP04, O3N2 PP04, R23 KK04) -> oh12_calib = '<indicador>-><T04>'.
No se copian las coordenadas (son del host, no de la SN) ni E(B-V) (es del host entero,
no la extinción de la SN).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ia_common import fmt, raw_dir, viz_tsv, write_part  # noqa: E402

SID = "snfactory_hosts"
COLS = ["SN", "z", "r_z", "f_logM*", "Class", "n_ZT04", "ZT04"]


def calib(n):
    m = re.match(r"^(\S+)\s*\((\w+)\)$", n.strip())
    return f"{m.group(1)}_{m.group(2)}->T04" if m else ""


def name(sn):
    m = re.match(r"^SN\s*(\d{4}\w+)$", sn)
    return f"SN {m.group(1)}" if m else sn


def main():
    d = raw_dir(SID)
    g = viz_tsv("J/ApJ/770/107/galaxies", COLS, os.path.join(d, "galaxies.tsv"))
    rows = []
    for _, r in g.iterrows():
        oh = fmt(r.ZT04, 2)
        rows.append({
            "sn_name": name(r.SN), "subclass": "Ia",
            "z": fmt(r.z, 5), "z_type": "host_spec" if r.z else "",
            "oh12": oh, "oh12_type": "host_global" if oh else "",
            "oh12_calib": calib(r.n_ZT04) if oh else "",
        })
    df = write_part(SID, rows)
    print("con oh12:", (df.oh12 != "").sum(), df.oh12_calib.value_counts().to_dict())
    print("f_logM*=d (masa con z de la SN):", g[g["f_logM*"] == "d"][["SN", "z"]].values.tolist())


if __name__ == "__main__":
    main()
