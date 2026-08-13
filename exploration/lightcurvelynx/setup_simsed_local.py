"""
Fase 2 parte B -- version generalizada de setup_simsed_91bg_local.py.

SIMSED.TDE-MOSFIT/SED.INFO tiene una linea suelta ("tde_384.json", sin
prefijo "SED:" ni "#", sin ':') intercalada entre entradas SED: reales
(confirmado en NLHPC: linea 254, entre tde239.dat y tde241.dat) -- rompe
yaml.safe_load() igual que el typo de SNIa-91bg en Fase 2B round 1, pero
esta vez es una linea entera fuera de formato, no un solo caracter. El
parser propio de SNANA (snlc_sim.exe) la tolera porque no usa un parser
YAML estricto; lightcurvelynx.models.sed_template_model.SIMSEDModel si
la usa y falla.

A diferencia de setup_simsed_91bg_local.py (35 templates, copia
completa), SIMSED.TDE-MOSFIT tiene 745 templates / 144M -- copiar todo
seria un desperdicio. Esta version symlinkea los archivos de datos y
solo reescribe SED.INFO, eliminando lineas que no matchean ninguno de
los formatos validos conocidos (comentario, blank, o keyword real).
No se toca el archivo original en NLHPC.

Uso:
    python3 setup_simsed_local.py <clase> <simsed_dir_absoluto>
    (corre en NLHPC, mismo patron que setup_simsed_91bg_local.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

KNOWN_KEYS = (
    "FLUX_SCALE:", "MAG_ERR:", "RESTLAMBDA_RANGE:", "NPAR:", "PARNAMES:",
    "SED:", "GENFILTER:", "SIMSED_REDCOR:", "SIMSED_GRIDONLY:",
    "SIMSED_USE_BINARY:",
)


def sanitize_info(src_dir: Path, dst_dir: Path) -> int:
    lines = (src_dir / "SED.INFO").read_text().splitlines()
    kept = []
    n_dropped = 0
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(KNOWN_KEYS):
            kept.append(line)
        else:
            n_dropped += 1
            print(f"  descartada (formato invalido): {line!r}")
    (dst_dir / "SED.INFO").write_text("\n".join(kept) + "\n")
    return n_dropped


def main():
    if len(sys.argv) != 3:
        raise SystemExit("uso: setup_simsed_local.py <clase> <simsed_dir_absoluto>")
    class_key, src = sys.argv[1], Path(sys.argv[2])
    dst = Path(__file__).resolve().parent / f"simsed_{class_key.lower().replace('-', '')}_local"
    dst.mkdir(exist_ok=True)

    n_dropped = sanitize_info(src, dst)
    print(f"SED.INFO saneado, {n_dropped} linea(s) descartada(s)")

    n_linked = 0
    for f in src.iterdir():
        if f.name == "SED.INFO":
            continue
        link = dst / f.name
        if not link.exists():
            link.symlink_to(f)
            n_linked += 1
    print(f"{n_linked} archivo(s) symlinkeado(s) a {dst}")


if __name__ == "__main__":
    main()
