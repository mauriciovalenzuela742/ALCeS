"""
Fase 66: agrega los resultados de un sweep -- reemplaza el proceso manual
de leer `summary.json` de cada corrida a mano, fase a fase, que se ha
usado en toda esta investigacion (NOTES.md, tablas de Fase 59/60/62/64).

Para cada corrida del manifiesto: lee runs/<hash>/summary.json (si existe)
y runs/<hash>/run_hash.json (si existe), arma una fila con el run_hash
como columna real (no solo el nombre de directorio), y escribe una tabla
consolidada -- lista para seguir el analisis de la fase que corresponda,
o como insumo de sweep_publish_dataset.py.

Uso:
    python3 sweep_aggregate.py <sweep_name>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import sweep_hash
from sweep_compile import SWEEP_RUNS_DIR


def aggregate_sweep(sweep_name: str) -> Path:
    sweep_dir = SWEEP_RUNS_DIR / sweep_name
    manifest_path = sweep_dir / "manifest.json"
    manifest = sweep_hash.read_json(manifest_path)

    rows = []
    for r in manifest["runs"]:
        output_dir = sweep_dir / r["output_dir"]
        summary_path = output_dir / "summary.json"
        run_hash_path = output_dir / "run_hash.json"

        row = dict(
            run_hash=r["run_hash"], run_hash_full=r["run_hash_full"],
            class_key=r["class_key"], seed_index=r["seed_index"], wfd=r["wfd"],
            simsed_t0_mode=r["simsed_t0_mode"], ngentot=r["ngentot"], tier=r["tier"],
        )

        status = "no_run_hash_json"
        if run_hash_path.exists():
            try:
                info = sweep_hash.read_json(run_hash_path)
                status = info.get("status", "unknown")
                row["node"] = info.get("node")
                row["slurm_job_id"] = info.get("slurm_job_id")
                row["started_at"] = info.get("started_at")
                row["finished_at"] = info.get("finished_at")
            except Exception:  # noqa: BLE001 -- archivo corrupto no debe tumbar el agregado completo
                status = "run_hash_json_ilegible"
        row["status"] = status

        if summary_path.exists():
            try:
                summary = sweep_hash.read_json(summary_path)
                # todos los campos reales de summary.json (ver run_simsed_poc.py::main):
                # class_key/strategy/seed_index/ngentot_lc/n_with_obs/n_detected/
                # n_total_dump/sim_wall_time_s/detection_efficiency_pct/snr_median/snr_p90
                for k, v in summary.items():
                    row.setdefault(f"summary_{k}", v)
            except Exception:  # noqa: BLE001 -- idem, no tumbar el resto del agregado
                row["summary_read_error"] = True

        rows.append(row)

    df = pd.DataFrame(rows)
    out_path = sweep_dir / "aggregated_summary.parquet"
    sweep_hash.write_dataframe_atomic(out_path, df)
    print(f"  agregado: {out_path} ({len(df)} filas)")
    print(df[["run_hash", "class_key", "seed_index", "status"]].to_string(index=False))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python3 sweep_aggregate.py <sweep_name>")
        sys.exit(1)
    aggregate_sweep(sys.argv[1])
