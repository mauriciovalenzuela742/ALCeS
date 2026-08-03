"""
monitor.py — Monitoreo de estado de una campanha lanzada.

REDISEÑO: ya no se pasa por submit_batch_jobs.sh, asi que no hay MERGE.LOG ni
un .LOG por GENVERSION con formato conocido. En su lugar, cada GENVERSION
corre via su propio sbatch (slurm/run_<GENVERSION>.sh), que redirige stdout/
stderr a run_<GENVERSION>_<jobid>.out/.err en build_dir. El estado se arma
combinando:

    1. squeue (PENDING/RUNNING mientras el job este en cola)
    2. la salida FITS real bajo $SNDATA_ROOT/SIM/<GENVERSION>/ (señal DONE
       mas confiable que parsear texto de log, ya que no conocemos el string
       exacto que imprime snlc_sim.exe al terminar en invocacion directa)
    3. el .out/.err de SLURM (para detectar ABORT/FATAL/Error si algo fallo)

    GENVERSION                               STATUS    NGEN     TIME    SLURM
    SNIa_WFD_baseline_v5.3.1_10yrs           DONE     50000     3m12s   —
    SNII_WFD_baseline_v5.3.1_10yrs           RUNNING      —       —    12345
    TDE_DDF_baseline_v5.3.1_10yrs            FAILED       —       —    12346
    AGN_WFD_baseline_v5.3.1_10yrs            PENDING      —       —      —
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VersionStatus:
    genversion: str
    run: str
    strategy: str
    model: str
    ngen_requested: int
    status: str = "UNKNOWN"    # PENDING | RUNNING | DONE | FAILED | UNKNOWN
    ngen_done: int | None = None
    elapsed: str | None = None
    slurm_id: str | None = None
    log_path: str | None = None
    error_msg: str | None = None


@dataclass
class CampaignStatus:
    campaign: str
    build_dir: Path
    versions: list[VersionStatus] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        from collections import Counter
        return dict(Counter(v.status for v in self.versions))


def campaign_status(build_dir: str | Path) -> CampaignStatus:
    """Construye el estado actual de la campanha."""
    build_dir = Path(build_dir)
    manifest_path = build_dir / "campaign_manifest.json"
    if not manifest_path.exists():
        return CampaignStatus(campaign="?", build_dir=build_dir)

    manifest = json.loads(manifest_path.read_text())
    name = manifest.get("campaign", "?")
    combos = manifest.get("combos", [])

    # intentar leer job IDs de SLURM si hay squeue
    slurm_jobs = _get_slurm_jobs()

    # buscar logs en build_dir y en $SNDATA_ROOT/SIM/
    sim_root = Path(os.environ.get("SNDATA_ROOT", "")) / "SIM"

    versions = []
    for c in combos:
        gv = c["genversion"]
        vs = VersionStatus(
            genversion=gv,
            run=c["run"],
            strategy=c["strategy"],
            model=c["model"],
            ngen_requested=c.get("ngen", 0),
        )

        # buscar log SLURM (.out/.err) en build_dir
        log = _find_log(gv, build_dir)
        if log:
            vs.log_path = str(log)
            _parse_log(vs, log)

        # buscar DUMP para ngen_done
        dump = _find_file(gv, ".DUMP", build_dir, sim_root / gv)
        if dump:
            vs.ngen_done = _count_dump(dump)

        # senhal DONE mas confiable: existe el output FITS real
        if _output_exists(gv, sim_root):
            vs.status = "DONE"

        # SLURM status (solo si aun no se confirmo DONE)
        if slurm_jobs and vs.status != "DONE":
            for jid, jname, jstate in slurm_jobs:
                if gv in jname:
                    vs.slurm_id = jid
                    if vs.status not in ("FAILED",):
                        vs.status = {"PENDING": "PENDING", "RUNNING": "RUNNING",
                                     "COMPLETING": "RUNNING"}.get(jstate, vs.status)
                    break

        if vs.status == "UNKNOWN" and log:
            # No esta en squeue (o no se pudo consultar), no hay FITS, y el
            # log no tiene ABORT/FATAL: estado genuinamente ambiguo. Dejarlo
            # como UNKNOWN (no PENDING) es mas honesto, y se agrega un hint
            # para que el usuario revise el log a mano.
            vs.status = "UNKNOWN"
            if not vs.error_msg:
                vs.error_msg = ("sin senhal clara: no esta en squeue, no hay FITS en "
                                "$SNDATA_ROOT/SIM/, y el log no tiene ABORT/FATAL — "
                                f"revisar a mano: {log}")

        versions.append(vs)

    return CampaignStatus(campaign=name, build_dir=build_dir, versions=versions)


def format_status(cs: CampaignStatus) -> str:
    """Tabla legible del estado."""
    lines = [
        f"campanha: {cs.campaign}  ({cs.build_dir})",
        f"resumen:  {cs.summary}",
        "",
    ]
    # header
    hdr = f"  {'GENVERSION':<52} {'STATUS':<10} {'NGEN':>8} {'ELAPSED':>10} {'SLURM':>8}"
    lines.append(hdr)
    lines.append("  " + "-" * (len(hdr) - 2))
    for v in cs.versions:
        ngen = f"{v.ngen_done:,}" if v.ngen_done is not None else "—"
        elapsed = v.elapsed or "—"
        slurm = v.slurm_id or "—"
        icon = {"DONE": "✓", "FAILED": "✗", "RUNNING": "▶", "PENDING": "◌"}.get(v.status, "?")
        lines.append(
            f"  {icon} {v.genversion:<50} {v.status:<10} {ngen:>8} {elapsed:>10} {slurm:>8}"
        )
        if v.error_msg:
            lines.append(f"    └─ {v.error_msg}")
    return "\n".join(lines)


# ------------------------------------------------------------------ internos
def _get_slurm_jobs() -> list[tuple[str, str, str]] | None:
    """Lista (job_id, name, state) del usuario actual via squeue."""
    try:
        result = subprocess.run(
            ["squeue", "-u", os.environ.get("USER", ""), "-h",
             "-o", "%i %j %T"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        jobs = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3:
                jobs.append(tuple(parts))
        return jobs or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _find_log(gv: str, *dirs: Path) -> Path | None:
    for d in dirs:
        if not d.is_dir():
            continue
        for pattern in (f"run_{gv}_*.out", f"run_{gv}_*.err"):
            hits = list(d.glob(pattern))
            if hits:
                return max(hits, key=lambda p: p.stat().st_mtime)
    return None


def _output_exists(gv: str, sim_root: Path) -> bool:
    """Senhal DONE mas confiable: existe el directorio de salida con FITS reales."""
    gdir = sim_root / gv
    if not gdir.is_dir():
        return False
    return any(gdir.glob("*.FITS*")) or any(gdir.glob("*HEAD.FITS*"))


def _find_file(gv: str, suffix: str, *dirs: Path) -> Path | None:
    for d in dirs:
        if not d.is_dir():
            continue
        for pattern in (f"{gv}/*{suffix}", f"{gv}{suffix}", f"*{suffix}"):
            hits = list(d.glob(pattern))
            if hits:
                return hits[0]
    return None


def _parse_log(vs: VersionStatus, log: Path) -> None:
    """Parsea el .out/.err de SLURM buscando ABORT/FATAL/Error (senhal FAILED).

    No se busca un string de 'exito' especifico porque no esta confirmado que
    imprima snlc_sim.exe en invocacion directa (sin submit_batch_jobs.sh); el
    DONE definitivo lo da _output_exists() con el FITS real, no este parseo.
    """
    try:
        text = log.read_text(errors="replace")
        tail = "\n".join(text.splitlines()[-80:])
    except Exception:
        return

    if re.search(r"ABORT|FATAL|Segmentation fault", tail, re.IGNORECASE):
        vs.status = "FAILED"
        for line in tail.splitlines():
            if re.search(r"ABORT|FATAL|Segmentation fault", line, re.IGNORECASE):
                vs.error_msg = line.strip()[:120]
                break
    # NOTA: ya NO se asume RUNNING por defecto si no hay ABORT/FATAL. Un log
    # sin senhal clara puede significar tanto "sigue corriendo" como "termino
    # hace rato y el patron de exito no matcheaba" — asumir RUNNING aca genera
    # falsos positivos (ej. reportar RUNNING con squeue vacio). Se deja
    # vs.status como esta (UNKNOWN si nada mas lo cambio) y que la
    # confirmacion real venga de squeue o de la existencia del FITS.

    # elapsed time (si snlc_sim lo imprime; formato variable, best-effort)
    m = re.search(r"Elapsed.*?time[:\s]*([\d.]+)\s*(sec|min|hr)", tail, re.IGNORECASE)
    if m:
        val, unit = float(m.group(1)), m.group(2).lower()
        if unit == "sec":
            vs.elapsed = f"{val:.0f}s"
        elif unit == "min":
            vs.elapsed = f"{val:.1f}m"
        elif unit == "hr":
            vs.elapsed = f"{val:.2f}h"


def _count_dump(dump: Path) -> int | None:
    """Cuenta líneas de datos en el .DUMP (cada línea = un evento generado)."""
    try:
        text = dump.read_text(errors="replace")
        # la cabecera del DUMP empieza con VARNAMES:; los datos son las líneas SN:
        return sum(1 for line in text.splitlines() if line.startswith("SN:"))
    except Exception:
        return None
