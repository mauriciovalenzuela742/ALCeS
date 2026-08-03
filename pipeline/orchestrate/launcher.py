"""
launcher.py — Lanzamiento de campaña: un sbatch por GENVERSION.

REDISEÑO: ya no se invoca submit_batch_jobs.sh (herramienta que el usuario
nunca uso en la practica y cuyo formato CONFIG/GENVERSION_LIST + archivo de
plantilla SLURM no estaba disponible). En su lugar, se lanza directamente
un `sbatch` por cada script generado en Capa 2 (slurm/run_<GENVERSION>.sh),
que a su vez invoca `snlc_sim.exe <archivo>.INPUT` — exactamente el patron
ya probado con exito por el usuario en NLHPC.

Flujo:
    1. Si no existe build_dir, compila desde campaign.yaml (Capa 2)
    2. Corre preflight checks (Capa 3)
    3. `sbatch` por cada slurm/run_<GENVERSION>.sh (o via submit_all.sh)
    4. Registra procedencia del lanzamiento (launch.json), con los job IDs
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .preflight import preflight_check, preflight_summary


def launch_campaign(
    build_dir: str | Path,
    *,
    campaign_yaml: str | Path | None = None,
    skip_preflight: bool = False,
    dry_run: bool = False,
) -> int:
    """Lanza una campaña compilada: un sbatch por GENVERSION.

    Parameters
    ----------
    build_dir : path al directorio generado por compile_campaign
    campaign_yaml : si build_dir no existe, compila desde este .yaml
    skip_preflight : salta los checks (para debugging)
    dry_run : solo valida, no lanza
    """
    build_dir = Path(build_dir)

    # --- paso 1: compilar si falta ---
    if not build_dir.exists():
        if not campaign_yaml:
            print(f"error: {build_dir} no existe. Pasa --campaign-yaml para compilar, "
                  f"o corre compile_campaign.py primero.", file=sys.stderr)
            return 2
        print(f"» compilando desde {campaign_yaml} …")
        from pipeline.campaign.compiler import compile_campaign
        plan = compile_campaign(campaign_yaml, out_dir=build_dir)
        print(f"  ✓ {plan.manifest['n_root_inputs']} .INPUT generados\n")

    manifest_path = build_dir / "campaign_manifest.json"
    if not manifest_path.exists():
        print(f"error: no existe {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())
    combos = manifest.get("combos", [])
    if not combos:
        print("error: la campaña no tiene GENVERSION alguna", file=sys.stderr)
        return 2

    # --- paso 2: preflight ---
    if not skip_preflight:
        print("» pre-flight checks …")
        results = preflight_check(build_dir)
        ok, summary = preflight_summary(results)
        print(summary)
        if not ok:
            print("\n  ✗ corregir los errores antes de lanzar.", file=sys.stderr)
            return 2
        print()

    # --- paso 3: lanzar (un sbatch por GENVERSION) ---
    if dry_run:
        print(f"» dry-run: no se lanza ningun sbatch")
        print(f"  se lanzarian {len(combos)} jobs, ej.:")
        for c in combos[:3]:
            print(f"    (cwd={build_dir}) sbatch {c['slurm_script']}")
        if len(combos) > 3:
            print(f"    … y {len(combos) - 3} mas")
        return 0

    print(f"» lanzando {len(combos)} jobs (cwd={build_dir}) …\n")
    launches = []
    rc_total = 0
    for c in combos:
        script = c["slurm_script"]
        try:
            proc = subprocess.run(
                ["sbatch", script], cwd=str(build_dir),
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            print("error: sbatch no encontrado en $PATH (¿estas en un login node de SLURM?)",
                  file=sys.stderr)
            return 2

        job_id = None
        if proc.returncode == 0:
            m = re.search(r"Submitted batch job (\d+)", proc.stdout)
            job_id = m.group(1) if m else None
            print(f"  ✓ {c['genversion']:<55} job={job_id or '?'}")
        else:
            rc_total = 1
            print(f"  ✗ {c['genversion']:<55} FALLO: {proc.stderr.strip()[:150]}")

        launches.append({
            "genversion": c["genversion"], "script": script,
            "job_id": job_id, "return_code": proc.returncode,
        })

    # --- paso 4: procedencia ---
    launch_record = {
        "campaign": build_dir.name,
        "n_genversions": len(combos),
        "n_submitted_ok": sum(1 for x in launches if x["return_code"] == 0),
        "launched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": os.environ.get("USER", "unknown"),
        "host": os.environ.get("HOSTNAME", os.environ.get("HOST", "unknown")),
        "jobs": launches,
    }
    launch_path = build_dir / "launch.json"
    existing = []
    if launch_path.exists():
        try:
            existing = json.loads(launch_path.read_text())
            if isinstance(existing, dict):
                existing = [existing]
        except (json.JSONDecodeError, ValueError):
            existing = []
    existing.append(launch_record)
    launch_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    n_ok = launch_record["n_submitted_ok"]
    print(f"\n  {n_ok}/{len(combos)} jobs enviados a SLURM correctamente")
    print(f"  procedencia registrada en {launch_path.name}")
    print(f"  monitorear con:  squeue -u $USER   o   python -m pipeline.run_campaign --status {build_dir}")

    return rc_total
