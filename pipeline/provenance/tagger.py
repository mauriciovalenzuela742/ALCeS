"""
tagger.py — Etiquetado de procedencia por corrida.

Cada GENVERSION completada recibe un RunTag con:
    - version OpSim (release, family, filename, sha256)
    - version SNANA (via snlc_sim.exe --version)
    - hash del config (campaign.yaml + models.yaml + simlib.yaml)
    - hash del .INPUT raiz que se uso
    - timestamps (simulacion, conversion, QC)
    - inventario de inputs y outputs
    - entorno de ejecucion (OS, Python, paquetes)

Los tags se guardan como JSON junto a cada GENVERSION y se consolidan
en un manifiesto de campanha.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .environment import capture_environment


@dataclass
class RunTag:
    """Tag de procedencia para un GENVERSION."""

    # identidad
    genversion: str
    run: str                     # nombre del registro Capa 0
    strategy: str                # WFD o DDF
    model: str                   # clave del modelo

    # versiones
    opsim_release: str = ""
    opsim_filename: str = ""
    opsim_sha256: str = ""
    snana_version: str = ""

    # hashes de config
    config_hash: str = ""        # sha256 de campaign.yaml + models.yaml + simlib.yaml
    input_hash: str = ""         # sha256 del .INPUT raiz

    # timestamps
    tagged_at: str = ""
    simulated_at: str = ""       # del launch.json si existe
    postprocessed_at: str = ""   # del postprocess_manifest si existe

    # inventario
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)

    # entorno
    environment: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        return path


# ------------------------------------------------------------------ builder
def _hash_files(*paths: Path) -> str:
    """SHA256 combinado de multiples archivos (para el config hash)."""
    h = hashlib.sha256()
    for p in sorted(paths):
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def _hash_file(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory_dir(d: Path, suffixes: set[str] | None = None) -> dict[str, int]:
    """Lista archivos con tamanho (opcionalmente filtrados por sufijo)."""
    inv = {}
    if not d.is_dir():
        return inv
    for f in sorted(d.rglob("*")):
        if f.is_file():
            if suffixes and f.suffix.lower() not in suffixes:
                continue
            inv[str(f.relative_to(d))] = f.stat().st_size
    return inv


def tag_run(
    genversion: str,
    build_dir: Path,
    *,
    combo: dict | None = None,
    opsim_meta: dict | None = None,
    config_paths: list[Path] | None = None,
    sim_output_dir: Path | None = None,
    postproc_dir: Path | None = None,
) -> RunTag:
    """Construye el RunTag para un GENVERSION."""
    combo = combo or {}
    opsim_meta = opsim_meta or {}

    # hash del .INPUT raiz
    root_input = build_dir / f"sim_{genversion}.INPUT"
    input_hash = _hash_file(root_input)

    # hash de configs
    config_hash = ""
    if config_paths:
        config_hash = _hash_files(*[Path(p) for p in config_paths])

    # entorno
    env = capture_environment()

    # timestamps
    simulated_at = ""
    launch_file = build_dir / "launch.json"
    if launch_file.exists():
        try:
            launches = json.loads(launch_file.read_text())
            if isinstance(launches, list) and launches:
                simulated_at = launches[-1].get("launched_at", "")
            elif isinstance(launches, dict):
                simulated_at = launches.get("launched_at", "")
        except Exception:
            pass

    postprocessed_at = ""
    if postproc_dir:
        pp_manifest = postproc_dir / "postprocess_manifest.json"
        if pp_manifest.exists():
            try:
                postprocessed_at = json.loads(pp_manifest.read_text()).get("processed_at", "")
            except Exception:
                pass

    # inventario de outputs
    outputs = {}
    if sim_output_dir and sim_output_dir.is_dir():
        outputs["simulation"] = _inventory_dir(sim_output_dir, {".fits", ".gz", ".dump", ".log"})
    if postproc_dir and postproc_dir.is_dir():
        outputs["qc"] = _inventory_dir(postproc_dir / genversion / "qc", {".png"})

    # inputs
    inputs = {}
    if root_input.exists():
        inputs["root_input"] = str(root_input.name)
    inputs["includes"] = [
        f.name for f in sorted((build_dir / "includes").glob("*.INPUT"))
    ] if (build_dir / "includes").is_dir() else []

    tag = RunTag(
        genversion=genversion,
        run=combo.get("run", ""),
        strategy=combo.get("strategy", ""),
        model=combo.get("model", ""),
        opsim_release=opsim_meta.get("release", ""),
        opsim_filename=opsim_meta.get("filename", ""),
        opsim_sha256=opsim_meta.get("sha256", ""),
        snana_version=env.get("snana_version") or "",
        config_hash=config_hash,
        input_hash=input_hash,
        tagged_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        simulated_at=simulated_at,
        postprocessed_at=postprocessed_at,
        inputs=inputs,
        outputs=outputs,
        environment=env,
    )
    return tag


# ------------------------------------------------------------------ campanha
def collect_campaign_tags(
    build_dir: str | Path,
    *,
    postproc_dir: str | Path | None = None,
) -> list[RunTag]:
    """Genera tags para todos los GENVERSION de una campanha compilada."""
    build_dir = Path(build_dir)
    manifest_path = build_dir / "campaign_manifest.json"
    if not manifest_path.exists():
        return []

    manifest = json.loads(manifest_path.read_text())
    combos = manifest.get("combos", [])

    # cargar metadatos OpSim del registro si disponible
    opsim_cache: dict[str, dict] = {}
    try:
        from pipeline.registry import Registry
        reg = Registry.load()
        for combo in combos:
            run = combo["run"]
            if run not in opsim_cache:
                try:
                    r = reg.get(run)
                    opsim_cache[run] = {
                        "release": r.release, "filename": r.filename, "sha256": r.sha256 or "",
                    }
                except Exception:
                    opsim_cache[run] = {}
    except Exception:
        pass

    # config paths para el hash combinado
    config_paths = []
    for name in ("campaigns/" + manifest.get("campaign", "") + ".yaml",
                 "pipeline/models.yaml", "pipeline/simlib.yaml"):
        p = build_dir.parent / name
        if not p.exists():
            # intentar relativo al repo root
            from pipeline import paths as _paths
            p = _paths.repo_root() / name
        if p.exists():
            config_paths.append(p)

    pp_dir = Path(postproc_dir) if postproc_dir else build_dir / "postproc"

    tags = []
    for combo in combos:
        gv = combo["genversion"]
        tag = tag_run(
            gv, build_dir,
            combo=combo,
            opsim_meta=opsim_cache.get(combo.get("run", ""), {}),
            config_paths=config_paths,
            postproc_dir=pp_dir,
        )
        tags.append(tag)

    return tags


def save_campaign_manifest(tags: list[RunTag], out_path: str | Path) -> Path:
    """Guarda el manifiesto consolidado de procedencia."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "provenance_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_runs": len(tags),
        "runs": [t.to_dict() for t in tags],
    }
    out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out_path
