"""
environment.py — Captura del entorno de ejecucion para reproducibilidad.

Registra: Python, OS, SNANA version, paquetes clave, variables de entorno
relevantes, y hardware basico. Todo serializable a JSON.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def capture_environment() -> dict:
    """Snapshot del entorno. Seguro: no falla si falta algo."""
    env = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
    }

    # SNANA
    env["snana_version"] = _snana_version()
    env["snana_dir"] = os.environ.get("SNANA_DIR", "")
    env["sndata_root"] = os.environ.get("SNDATA_ROOT", "")

    # SLURM
    env["slurm_job_id"] = os.environ.get("SLURM_JOB_ID")
    env["slurm_cluster"] = os.environ.get("SLURM_CLUSTER_NAME")
    env["slurm_partition"] = os.environ.get("SLURM_JOB_PARTITION")

    # paquetes clave
    env["packages"] = _key_packages()

    return env


def _snana_version() -> str | None:
    """Intenta obtener la version de SNANA via snlc_sim.exe --version."""
    exe = shutil.which("snlc_sim.exe")
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "version" in line.lower() or "SNANA" in line:
                return line.strip()
        return result.stdout.strip()[:200] if result.stdout else None
    except Exception:
        return None


def _key_packages() -> dict[str, str]:
    """Versiones de paquetes clave del stack."""
    pkgs = {}
    for name in ("numpy", "pandas", "astropy", "healpy", "sklearn",
                 "opsimsummaryv2", "rubin_sim", "fitsio", "pyarrow",
                 "matplotlib", "yaml", "tqdm"):
        try:
            mod = __import__(name)
            pkgs[name] = getattr(mod, "__version__", "installed")
        except ImportError:
            pass
    return pkgs
