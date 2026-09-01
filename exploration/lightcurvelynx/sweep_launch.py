"""
Fase 66: somete a SLURM los arrays de un sweep ya compilado -- el "deploy
de un click" pedido por el profesor (un solo comando lanza toda la matriz
clase x semilla x modo del sweep). Mismo patron real de
`pipeline/orchestrate/launcher.py` (subprocess.run(["sbatch", ...]),
parseo de "Submitted batch job (\\d+)") -- solo lectura de ese archivo
como referencia, no se importa ni se modifica nada de pipeline/.

Uso:
    python3 sweep_launch.py sweeps/<archivo>.yaml [--dry-run]

Si el manifiesto de ese sweep todavia no existe, compila primero
(mismo criterio que pipeline/orchestrate/launcher.py::launch_campaign()).
Si ya existe, se usa tal cual -- para recompilar (p.ej. tras editar el
YAML) hay que correr `sweep_compile.py --force` a mano primero; lanzar
nunca recompila algo que ya existe, para no invalidar en silencio
corridas que ya estan corriendo bajo el manifiesto viejo.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

import sweep_hash
from run_simsed_poc import HERE
from sweep_compile import SWEEP_RUNS_DIR, compile_sweep

# ~/AUTOSIM: raiz real desde donde SLURM resuelve los paths relativos de
# -o/-e de los .sbatch generados (ver sweep_compile.py -- la convencion
# real de este proyecto, confirmada en todas las rondas de investigacion
# anteriores, es correr `sbatch` desde aca, no desde exploration/lightcurvelynx/).
AUTOSIM_ROOT = HERE.parent.parent


def launch_sweep(yaml_path: Path, dry_run: bool = False) -> int:
    yaml_path = Path(yaml_path)
    sweep_name = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))["sweep_name"]
    manifest_path = SWEEP_RUNS_DIR / sweep_name / "manifest.json"

    if not manifest_path.exists():
        print(f"» compilando {yaml_path} (manifiesto no existe todavia) ...")
        compile_sweep(yaml_path)

    manifest = sweep_hash.read_json(manifest_path)
    array_scripts = manifest.get("array_scripts") or []
    if not array_scripts:
        print("error: el manifiesto no tiene ningun array_script -- nada que lanzar", file=sys.stderr)
        return 2

    if dry_run:
        print("» dry-run: no se somete nada a SLURM")
        for a in array_scripts:
            rel = f"exploration/lightcurvelynx/sweep_runs/{sweep_name}/{a['script']}"
            print(f"    (cwd={AUTOSIM_ROOT}) sbatch {rel}   # tier={a['tier']} array={a['array_range']}")
        return 0

    print(f"» sometiendo {len(array_scripts)} array(s) (cwd={AUTOSIM_ROOT}) ...\n")
    rc_total = 0
    for a in array_scripts:
        rel_script = f"exploration/lightcurvelynx/sweep_runs/{sweep_name}/{a['script']}"
        try:
            proc = subprocess.run(
                ["sbatch", rel_script], cwd=str(AUTOSIM_ROOT),
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            print("error: sbatch no encontrado en $PATH (¿estas en un login node de SLURM?)", file=sys.stderr)
            return 2

        job_id = None
        if proc.returncode == 0:
            m = re.search(r"Submitted batch job (\d+)", proc.stdout)
            job_id = m.group(1) if m else None
            print(f"  ✓ tier={a['tier']:<30} array={a['array_range']:<12} job={job_id or '?'}")
        else:
            rc_total = 1
            print(f"  ✗ tier={a['tier']:<30} FALLO: {proc.stderr.strip()[:200]}")

        a["slurm_array_job_id"] = job_id
        if job_id:
            for r in manifest["runs"]:
                if r["tier"] == a["tier"]:
                    r["status"] = "submitted"
                    r["slurm_job_id"] = f"{job_id}_{r['index']}"

    sweep_hash.write_json_atomic(manifest_path, manifest)
    n_ok = sum(1 for a in array_scripts if a.get("slurm_array_job_id"))
    print(f"\n  {n_ok}/{len(array_scripts)} arrays sometidos correctamente")
    print(f"  monitorear con: python3 sweep_monitor.py {sweep_name}")
    return rc_total


if __name__ == "__main__":
    _args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(_args) != 1:
        print("uso: python3 sweep_launch.py sweeps/<archivo>.yaml [--dry-run]")
        sys.exit(1)
    sys.exit(launch_sweep(Path(_args[0]), dry_run="--dry-run" in sys.argv))
