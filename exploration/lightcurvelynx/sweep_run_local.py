"""
Fase 76 -- reemplaza SLURM por un runner local para el sistema de sweeps
(Fase 66): el "deploy de un click" sin cluster, para instalaciones locales
(el pedido real del profesor -- correr esto en su propio computador, sin
acceso a SLURM). Mismo `manifest.json`/`run_hash.json`/esquema de hash de
siempre -- no se toca `sweep_hash.py`/`sweep_compile.py`, el manifiesto ya
es agnóstico de backend (fue diseñado en Fase 66 para que `sweep_worker.py`
resuelva su fila por índice, sin asumir SLURM en la lógica de negocio, solo
en cómo se invoca).

`sweep_monitor.py` YA funciona sin cambios para sweeps locales -- lee
`run_hash.json` primero (fuente autoritativa, la escribe el worker), y
`sacct` es solo un fallback que en una máquina local simplemente no
encuentra el binario y sigue (`sacct_states()` ya atrapa
`FileNotFoundError`). No hace falta un script de estado nuevo.

Uso:
    python3 sweep_run_local.py sweeps/<archivo>.yaml
    python3 sweep_run_local.py sweeps/<archivo>.yaml --workers 2

Compila el sweep si el manifiesto no existe todavía (mismo criterio que
`sweep_launch.py`). Corre cada TIER del manifiesto por separado, respetando
`max_concurrent` de ese tier (mismo campo, mismo significado que ya tiene
para el throttle `--array=lo-hi%K` de SLURM) -- salvo que se pase
`--workers N`, que sobreescribe el número de workers para TODOS los tiers
por igual (en una máquina local no existe la noción real de "nodo aparte"
para un tier "heavy" con más memoria, así que el override es deliberadamente
simple, no por-tier). Bloquea hasta terminar -- sin `sacct` que consultar
después, el progreso real se ve en la propia terminal.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

import sweep_hash
from sweep_compile import SWEEP_RUNS_DIR, compile_sweep
from sweep_worker import run_one


def run_sweep_local(yaml_path: Path, workers_override: int | None = None) -> int:
    yaml_path = Path(yaml_path)
    sweep_name = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))["sweep_name"]
    manifest_path = SWEEP_RUNS_DIR / sweep_name / "manifest.json"

    if not manifest_path.exists():
        print(f"» compilando {yaml_path} (manifiesto no existe todavía) ...")
        compile_sweep(yaml_path)

    manifest = sweep_hash.read_json(manifest_path)
    max_concurrent = manifest.get("max_concurrent") or {"default": 4}

    by_tier: dict[str, list[int]] = defaultdict(list)
    for r in manifest["runs"]:
        by_tier[r["tier"]].append(r["index"])

    print(f"» {manifest['n_runs']} corrida(s) real(es), {len(by_tier)} tier(s), sin SLURM "
          f"(runner local)\n")

    n_ok, n_fail = 0, 0
    for tier, indices in sorted(by_tier.items()):
        if workers_override is not None:
            n_workers = workers_override
        elif tier == "default":
            n_workers = max_concurrent.get("default", 4)
        else:
            n_workers = max_concurrent.get("override", max_concurrent.get("default", 4))
        n_workers = max(1, n_workers)
        print(f"» tier={tier} ({len(indices)} corrida(s), {n_workers} en paralelo) ...")

        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(run_one, manifest_path, idx): idx for idx in indices}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    rc = fut.result()
                except Exception as e:  # noqa: BLE001 -- fallo real de un worker no debe tumbar el resto
                    print(f"  ! index={idx} excepción no capturada por el worker: {e}")
                    rc = 1
                if rc == 0:
                    n_ok += 1
                else:
                    n_fail += 1

    print(f"\n  {n_ok}/{manifest['n_runs']} corridas terminaron 'done', {n_fail} con fallo")
    print(f"  ver detalle: python3 sweep_monitor.py {sweep_name}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sweep_yaml", type=Path)
    parser.add_argument("--workers", type=int, default=None,
                         help="sobreescribe max_concurrent para TODOS los tiers (default: usa el YAML)")
    args = parser.parse_args()
    sys.exit(run_sweep_local(args.sweep_yaml, workers_override=args.workers))
