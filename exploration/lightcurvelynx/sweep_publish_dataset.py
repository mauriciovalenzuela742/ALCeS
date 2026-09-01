"""
Fase 66: punto de enganche para un futuro entrenamiento de clasificador --
SIN implementar el conector real (el formato que espera ALeRCE/el equipo
del profesor todavia no esta definido, confirmado con el usuario).

Junta el `aggregated_summary.parquet` de uno o mas sweeps ya corridos
(solo corridas con status="done") en un directorio de dataset versionado
por su propio hash (`datasets/<hash>/`), con un manifiesto propio y un
`consolidated.parquet` (tabla agregada POR CORRIDA -- no fotometria cruda,
esa ya se borra por diseno de sweep_worker.py). El manifiesto incluye
`ingestion_format: null` a proposito: un futuro conversor debe leer desde
aca sin tocar sweep_runs/ ni el resto del sistema, y el campo null deja
explicito en el propio dato que ese paso sigue pendiente.

Uso:
    python3 sweep_publish_dataset.py --sweeps <sweep1> [<sweep2> ...]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import sweep_hash
from run_simsed_poc import HERE
from sweep_compile import SWEEP_RUNS_DIR

DATASETS_DIR = HERE / "datasets"
DATASET_SCHEMA_VERSION = 1


def load_sweep_done_rows(sweep_name: str) -> tuple[pd.DataFrame, str]:
    """Corre (o reusa, si ya existe) el aggregated_summary.parquet de un
    sweep, y devuelve (filas con status=done, code_hash del sweep)."""
    sweep_dir = SWEEP_RUNS_DIR / sweep_name
    manifest = sweep_hash.read_json(sweep_dir / "manifest.json")
    agg_path = sweep_dir / "aggregated_summary.parquet"
    if not agg_path.exists():
        from sweep_aggregate import aggregate_sweep
        aggregate_sweep(sweep_name)
    df = pd.read_parquet(agg_path)
    df_done = df[df["status"] == "done"].copy()
    df_done["source_sweep"] = sweep_name
    return df_done, manifest["code_hash"]


def publish_dataset(sweep_names: list[str]) -> Path:
    frames = []
    code_hash_by_sweep: dict[str, str] = {}
    for sweep_name in sweep_names:
        df_done, code_hash_value = load_sweep_done_rows(sweep_name)
        print(f"  {sweep_name}: {len(df_done)} corridas con status=done (de {sweep_name})")
        frames.append(df_done)
        code_hash_by_sweep[sweep_name] = code_hash_value

    if not frames or all(f.empty for f in frames):
        raise ValueError("ninguna corrida con status=done en los sweeps dados -- nada que publicar")

    consolidated = pd.concat(frames, ignore_index=True)
    run_hashes_full = sorted(consolidated["run_hash_full"].tolist())

    # dataset_hash: determinista dado el mismo conjunto de corridas + el
    # code_hash de cada sweep que las produjo -- publicar dos veces el
    # mismo conjunto de resultados da el MISMO dataset_hash (idempotente).
    payload = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "source_sweeps": sorted(sweep_names),
        "run_hashes_full": run_hashes_full,
        "code_hash_by_sweep": code_hash_by_sweep,
    }
    dataset_hash_full = sweep_hash.sha256_hex(
        sweep_hash.canonical_json(payload).encode("utf-8")
    )
    dataset_hash = dataset_hash_full[:12]

    out_dir = DATASETS_DIR / dataset_hash
    table_path = out_dir / "consolidated.parquet"
    manifest_path = out_dir / "manifest.json"
    readme_path = out_dir / "README.md"

    sweep_hash.write_dataframe_atomic(table_path, consolidated)

    manifest = dict(
        dataset_hash=dataset_hash,
        dataset_hash_full=dataset_hash_full,
        schema_version=DATASET_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source_sweeps=sorted(sweep_names),
        code_hash_by_sweep=code_hash_by_sweep,
        n_runs=len(consolidated),
        table_file="consolidated.parquet",
        # Deliberadamente null -- el formato de ingesta al entrenamiento de
        # ALeRCE aun no esta definido (confirmado con el usuario). Este
        # campo queda como evidencia explicita, en el propio dato, de que
        # ese paso sigue pendiente -- no se adivina un formato.
        ingestion_format=None,
    )
    sweep_hash.write_json_atomic(manifest_path, manifest)

    readme_path.write_text(
        "# Dataset publicado (Fase 66)\n\n"
        f"`dataset_hash`: `{dataset_hash}` (`{dataset_hash_full}`)\n\n"
        f"Sweeps de origen: {', '.join(sorted(sweep_names))}\n\n"
        f"{len(consolidated)} corridas (solo status=done).\n\n"
        "**El formato de ingesta al entrenamiento de ALeRCE aun no esta definido.** "
        "Este directorio es el punto de enganche -- un futuro conversor debe leer "
        "`manifest.json` + `consolidated.parquet` desde aca, sin tocar `sweep_runs/` "
        "ni el resto del sistema de automatizacion. `consolidated.parquet` es la tabla "
        "agregada POR CORRIDA (metricas de `summary.json` + `run_hash`), no fotometria "
        "cruda -- esa se borra por diseno despues de cada corrida (ver `sweep_worker.py`). "
        "Si el formato real de ALeRCE necesita fotometria cruda por objeto, es una "
        "decision de una fase posterior que cambiaria la politica de borrado.\n",
        encoding="utf-8",
    )

    print(f"\n  dataset publicado: {out_dir} ({len(consolidated)} corridas, hash={dataset_hash})")
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweeps", nargs="+", required=True)
    args = parser.parse_args()
    publish_dataset(args.sweeps)
