"""
Fase 75 -- script generalizado de vendoring de plantillas SNANA reales a una
copia local propia. Reemplaza el patrón de "un script `setup_*_local.py` por
clase" (5 scripts casi idénticos ya existentes -- `setup_salt2_local.py`,
`setup_simsed_91bg_local.py`, `setup_knbulla19_local.py`,
`setup_bullansed_local.py`, `setup_tdebbfit_local.py` -- ninguno con su copia
generada llegada a commitear) por un único comando parametrizado. Agregar una
clase nueva al set portable es correr este script, no escribir código nuevo.

Corre en una máquina con acceso real a `run_SNANA/` (hoy solo NLHPC, vía
`ssh nlhpc` ya configurado) -- reusa `CLASS_CONFIGS` de `run_simsed_poc.py`
para saber de dónde copiar cada clase, no duplica ninguna ruta a mano. La
salida (`<clase>_local/`) se junta en un bundle (Fase 75, ver `NOTES.md`) y
se entrega a quien instale el proyecto localmente -- no se commitea al repo
(mismo criterio que `poc_output_*/`, son datos, no código).

Uso:
    python3 vendor_snana_class.py <clase>                     # copia genérica
    python3 vendor_snana_class.py <clase> --fix-sedinfo-dollar  # + fix real
                                                                 # conocido (ver
                                                                 # setup_simsed_91bg_local.py:
                                                                 # un '$' donde
                                                                 # debería ir '#'
                                                                 # en SED.INFO,
                                                                 # rompe el
                                                                 # parser YAML
                                                                 # de LightCurveLynx,
                                                                 # no el de SNANA)
    python3 vendor_snana_class.py --salt2                     # caso especial
                                                                 # SALT2 (formato
                                                                 # distinto, ver
                                                                 # vendor_salt2())
    python3 vendor_snana_class.py --searcheff                 # copia los 2
                                                                 # .DAT de
                                                                 # SEARCHEFF
                                                                 # (nunca tuvieron
                                                                 # vendoring)

No modifica ningún archivo real de SNANA en NLHPC -- solo copia.
"""
from __future__ import annotations

import argparse
import gzip
import shutil
import sys
from pathlib import Path

from local_env import SNANA_HOME

HERE = Path(__file__).resolve().parent

# de SALT2.INFO -> COLORCOR_PARAMS: <min_lambda> <max_lambda> <ncoeffs> <coef1> ... <coefN>
# (mismos valores reales que setup_salt2_local.py, Fase 1 -- ver NOTES.md)
COLORCOR_MIN_LAMBDA = 2800
COLORCOR_MAX_LAMBDA = 9500
COLORCOR_COEFFS = [-1.33154627, 0.61225710, -0.12117791, 0.00840832]


def _local_dir_name(class_key: str) -> str:
    # Convención real para clases NUEVAS que se vendorizan con este script
    # (prefijo "simsed_" + clave en minúsculas sin guiones -- p.ej.
    # "PISN-STELLA-HECORE" -> "simsed_pisnstellahecore_local", ya usado real
    # en CLASS_CONFIGS de run_simsed_poc.py). Las clases YA vendorizadas a
    # mano antes de este script (SNIa-91bg -> "simsed_91bg_local", sin
    # "snia" -- un nombre elegido a mano, no esta convención) mantienen su
    # nombre real existente sin cambios; esta función solo aplica a clases
    # nuevas.
    return f"simsed_{class_key.lower().replace('-', '')}_local"


# Fase 75: rutas reales de origen en NLHPC para clases cuyo `simsed_dir` en
# `CLASS_CONFIGS` YA apunta a la copia local (una vez vendorizada una clase,
# `run_simsed_poc.py` se actualiza para leer de ahí -- mismo patrón que
# SNIa-91bg/KN-BULLA19 ya tenían -- así que `CLASS_CONFIGS` deja de ser una
# fuente confiable de "dónde estaba el dato real en NLHPC" para esas clases).
# Solo necesario para clases que YA se migraron a copia local; para una
# clase nueva que todavía lee directo de `run_SNANA/`, `vendor_generic()`
# puede seguir usando `CLASS_CONFIGS` tal cual (rama de abajo).
KNOWN_SOURCE_OVERRIDES = {
    "PISN-STELLA-HECORE": "run_SNANA/elastic/model_libs_updates/SIMSED.PISN-STELLA-HECORE",
    "PISN-STELLA-HYDROGENIC": "run_SNANA/elastic/model_libs_updates/SIMSED.PISN-STELLA-HYDROGENIC",
}


def vendor_generic(class_key: str, fix_sedinfo_dollar: bool = False) -> Path:
    """Copia genérica: determina el `simsed_dir` real de origen (desde
    `KNOWN_SOURCE_OVERRIDES` si la clase ya migró a copia local, si no desde
    `CLASS_CONFIGS` de `run_simsed_poc.py`) y copia `SED.INFO` + todos los
    `*.SED*` a una carpeta local `<clase>_local/`. Cubre el caso común
    (SIMSED sin problemas de dato conocidos) -- para quirks reales de dato ya
    encontrados (ZIP mal etiquetado como gzip en KN-BULLA19, línea suelta
    inválida en TDE-MOSFIT) seguir usando los scripts `setup_*_local.py`
    existentes hasta que se necesite generalizar también esos casos."""
    if class_key in KNOWN_SOURCE_OVERRIDES:
        src = SNANA_HOME / KNOWN_SOURCE_OVERRIDES[class_key]
    else:
        from run_simsed_poc import CLASS_CONFIGS

        if class_key not in CLASS_CONFIGS:
            print(f"clase desconocida: {class_key!r}. Claves válidas: {sorted(CLASS_CONFIGS)}")
            sys.exit(1)
        src = Path(CLASS_CONFIGS[class_key]["simsed_dir"])
        if not src.is_absolute():
            src = SNANA_HOME / src
    if not src.exists():
        print(f"! {src} no existe -- ¿corriendo en una máquina con run_SNANA/ real? (NLHPC)")
        sys.exit(1)

    dst = HERE / _local_dir_name(class_key)
    dst.mkdir(exist_ok=True)

    info_src = src / "SED.INFO"
    if info_src.exists():
        info_text = info_src.read_text()
        if fix_sedinfo_dollar:
            n_fixed = info_text.count("\n$ ")
            info_text = info_text.replace("\n$ ", "\n# ")
            print(f"SED.INFO: {n_fixed} línea(s) con '$' corregida(s) a '#' (fix real conocido, "
                  f"ver setup_simsed_91bg_local.py)")
        (dst / "SED.INFO").write_text(info_text)
    else:
        print(f"! {info_src} no existe -- revisar CLASS_CONFIGS[{class_key!r}]['simsed_dir']")
        sys.exit(1)

    # Fase 75: los nombres de archivo real que declara SED.INFO ("SED: <nombre> ...")
    # no siempre coinciden con el nombre real en disco -- confirmado que algunas
    # clases (p.ej. PISN-STELLA-HECORE, convención "<algo>_SED.dat") solo existen
    # comprimidas ("...dat.gz") aunque SED.INFO declare el nombre sin comprimir.
    # SIMSEDModel de LightCurveLynx ya tolera esto (intenta el nombre exacto, si
    # no existe agrega ".gz") -- se replica la misma lógica acá para copiar el
    # archivo real que efectivamente existe, sea cual sea su nombre en disco.
    declared_names = [
        line.split()[1] for line in info_text.splitlines()
        if line.strip().upper().startswith("SED:")
    ]
    n_copied, n_missing = 0, 0
    for name in declared_names:
        candidate = src / name
        if not candidate.exists():
            candidate = src / (name + ".gz")
        if not candidate.exists():
            print(f"  ! no encontrado (ni {name} ni {name}.gz): revisar manualmente")
            n_missing += 1
            continue
        shutil.copy2(candidate, dst / candidate.name)
        n_copied += 1
    print(f"{class_key}: SED.INFO + {n_copied}/{len(declared_names)} archivo(s) de template "
          f"copiados a {dst}" + (f" ({n_missing} faltante(s))" if n_missing else ""))
    return dst


def vendor_salt2() -> Path:
    """Reproduce exactamente la lógica real de `setup_salt2_local.py`
    (Fase 1) -- caso especial porque el formato que espera
    `sncosmo.SALT2Source` difiere del que trae SNANA (archivos
    comprimidos con gzip real, y `salt2_color_correction.dat` en un
    formato de texto distinto -- ver docstring de ese archivo para el
    detalle completo)."""
    src = SNANA_HOME / "run_SNANA/plasticc_models/SALT2.WFIRST-H17"
    dst = HERE / "salt2_h17_local"
    if not src.exists():
        print(f"! {src} no existe -- ¿corriendo en una máquina con run_SNANA/ real? (NLHPC)")
        sys.exit(1)
    dst.mkdir(exist_ok=True)

    for gz_file in src.glob("*.dat.gz"):
        out_path = dst / gz_file.stem  # quita el .gz
        with gzip.open(gz_file, "rb") as f_in, open(out_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        print(f"  descomprimido: {out_path.name}")

    info_src = src / "SALT2.INFO"
    if info_src.exists():
        shutil.copy(info_src, dst / "SALT2.INFO")

    clfile = dst / "salt2_color_correction.dat"
    lines = [str(len(COLORCOR_COEFFS))]
    lines.append(" ".join(f"{c:.8f}" for c in COLORCOR_COEFFS))
    lines.append("Salt2ExtinctionLaw.version 1")
    lines.append(f"Salt2ExtinctionLaw.min_lambda {COLORCOR_MIN_LAMBDA}")
    lines.append(f"Salt2ExtinctionLaw.max_lambda {COLORCOR_MAX_LAMBDA}")
    clfile.write_text("\n".join(lines) + "\n")
    print(f"  reescrito (formato sncosmo, coefs reales de SALT2.INFO): {clfile.name}")
    print(f"SALT2: listo en {dst}")
    return dst


def vendor_searcheff() -> Path:
    """Los 2 `.DAT` reales de `SEARCHEFF` nunca tuvieron vendoring -- son
    texto plano chico, se copian tal cual."""
    dst = HERE / "searcheff_local"
    dst.mkdir(exist_ok=True)
    for name in ("LSST_SEARCHEFF_PIPELINE.DAT", "LSST_PIPELINE_LOGIC.DAT"):
        src = SNANA_HOME / "run_SNANA" / name
        if not src.exists():
            print(f"! {src} no existe -- ¿corriendo en una máquina con run_SNANA/ real? (NLHPC)")
            sys.exit(1)
        shutil.copy2(src, dst / name)
        print(f"  copiado: {name}")
    print(f"SEARCHEFF: listo en {dst}")
    return dst


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("class_key", nargs="?", help="clave real de CLASS_CONFIGS (run_simsed_poc.py)")
    parser.add_argument("--fix-sedinfo-dollar", action="store_true",
                         help="corrige '$' -> '#' en SED.INFO (typo real conocido, ver SNIa-91bg)")
    parser.add_argument("--salt2", action="store_true", help="vendoriza SALT2.WFIRST-H17 (caso especial)")
    parser.add_argument("--searcheff", action="store_true", help="copia los 2 .DAT de SEARCHEFF")
    args = parser.parse_args()

    if args.salt2:
        vendor_salt2()
    elif args.searcheff:
        vendor_searcheff()
    elif args.class_key:
        vendor_generic(args.class_key, fix_sedinfo_dollar=args.fix_sedinfo_dollar)
    else:
        parser.print_help()
        sys.exit(1)
