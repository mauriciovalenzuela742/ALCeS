"""Valida y une los CSV de fuentes de templates escritos por el agente 1.

Uso:
    python validate_catalog.py parts/*.csv --out sources.csv

Revisa columnas, enums, unicidad de source_id, formato de URL y de referencia. No modifica el
contenido: si algo falla, lo informa y sale con código 1.
"""
import argparse
import re
import sys

import pandas as pd

COLUMNS = [
    "source_id", "name", "kind", "subclasses", "data_type", "n_objects", "bands",
    "phase_range_d", "wave_range_A", "redshift", "distance", "metallicity", "extinction",
    "access_url", "access_method", "license", "reference", "in_alces", "verified",
    "found_by", "notes",
]

SUBCLASSES = {
    "Ia", "Ia-91bg", "Ia-91T", "Iax", "Ia-CSM", "Ia-other",
    "II", "IIP", "IIL", "IIb", "IIn",
    "Ib", "Ic", "Ic-BL", "Ibn", "Icn", "Ca-rich",
    "SLSN-I", "SLSN-II", "PISN", "SN-other",
}

ENUMS = {
    "kind": {"template", "model_grid", "observed_dataset", "archive"},
    "data_type": {"spectra", "photometry", "both", "sed"},
    "redshift": {"spec", "photo", "mixed", "none", "unknown"},
    "distance": {"independent", "hubble_flow", "host", "none", "unknown"},
    "metallicity": {"host_global", "host_local", "model", "none", "unknown"},
    "extinction": {"mw_only", "mw_and_host", "none", "unknown"},
    "access_method": {"download", "api", "vizier", "paper_tables", "on_request", "unknown"},
    "in_alces": {"yes", "no"},
    "verified": {"yes", "partial", "no"},
}

REF_RE = re.compile(
    r"^(arXiv:(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})"  # arXiv nuevo o antiguo
    r"|\d{4}[A-Za-z&.]{5}[\d.]{4}[A-Za-z.][\d.]{4}[A-Z.]"    # bibcode ADS (19 caracteres)
    r"|10\.\d{4,9}/\S+)$"                                    # DOI
)
RANGE_RE = re.compile(r"^[+-]?\d+(\.\d+)?:[+-]?\d+(\.\d+)?$")


def check(df):
    errors = []
    missing = [c for c in COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in COLUMNS]
    if missing:
        errors.append(f"faltan columnas: {missing}")
    if extra:
        errors.append(f"columnas desconocidas: {extra}")
    if missing:
        return errors

    dup = df["source_id"][df["source_id"].duplicated()].tolist()
    if dup:
        errors.append(f"source_id repetidos: {dup}")

    for i, row in df.iterrows():
        tag = f"fila {i + 2} ({row['source_id']})"
        if not re.fullmatch(r"[a-z0-9_]+", str(row["source_id"])):
            errors.append(f"{tag}: source_id no es snake_case")
        for col, allowed in ENUMS.items():
            if row[col] not in allowed:
                errors.append(f"{tag}: {col}={row[col]!r} fuera de {sorted(allowed)}")
        subs = [s.strip() for s in str(row["subclasses"]).split(";") if s.strip()]
        bad = [s for s in subs if s not in SUBCLASSES]
        if not subs or bad:
            errors.append(f"{tag}: subclasses inválidas {bad or '(vacío)'}")
        if not str(row["access_url"]).startswith("https://") and not str(
            row["access_url"]
        ).startswith("http://"):
            errors.append(f"{tag}: access_url no es una URL")
        refs = [r.strip() for r in str(row["reference"]).split(";") if r.strip()]
        # Un archivo (TNS, por ejemplo) puede no tener paper de referencia.
        if (not refs and row["kind"] != "archive") or any(not REF_RE.match(r) for r in refs):
            errors.append(f"{tag}: reference con formato no reconocido: {row['reference']!r}")
        for col in ("phase_range_d", "wave_range_A"):
            v = row[col]
            if v and not RANGE_RE.match(str(v)):
                errors.append(f"{tag}: {col}={v!r} no tiene formato min:max")
        n = row["n_objects"]
        if n and not str(n).isdigit():
            errors.append(f"{tag}: n_objects={n!r} no es entero")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("parts", nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    frames = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in args.parts]
    df = pd.concat(frames, ignore_index=True)
    errors = check(df)
    for e in errors:
        print(e)
    if errors:
        print(f"{len(errors)} errores en {len(df)} filas")
        return 1
    if args.out:
        df[COLUMNS].sort_values("source_id").to_csv(args.out, index=False)
    print(f"OK: {len(df)} fuentes válidas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
