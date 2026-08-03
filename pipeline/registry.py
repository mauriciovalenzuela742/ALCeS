"""
registry.py — Capa 0: el registro de bases OpSim.

Fuente de verdad = dos archivos YAML que se fusionan al cargar:

    pipeline/opsims.yaml         (curado, versionado en git)
    pipeline/opsims.local.yaml   (auto-gestionado: checksums observados y altas
                                  locales; va en .gitignore)

Regla de fusion: por cada `run`, los campos definidos en el local sobrescriben
a los del curado. Asi el `record_sha256` y el `add_run` nunca tocan el YAML
curado (que tiene comentarios) — solo escriben el local con yaml.safe_dump.

Construccion de URL (indice S3DF/SLAC):
    {s3df_base}/sims_featureScheduler_runs{release}/{family}/{filename}

Ejemplo:
    https://s3df.slac.stanford.edu/data/rubin/sim-data/
        sims_featureScheduler_runs5.3/baseline/baseline_v5.3.1_10yrs.db
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
from pathlib import Path
from typing import Any, Iterator

import yaml

from . import paths as _paths


class RegistryError(RuntimeError):
    """Error de validacion o de acceso al registro."""


# Campos obligatorios que debe tener cada entrada `run`.
_REQUIRED_FIELDS = ("release", "family", "filename")

# Estados validos de una entrada.
_VALID_STATUS = {"verified", "registered", "archived"}


@dataclasses.dataclass
class OpSimRun:
    """Una entrada del registro: una base OpSim descargable."""

    name: str
    release: str                 # "5.0", "5.3", ...  -> sims_featureScheduler_runs{release}
    family: str                  # "baseline", "ddf_sd", "roll_mash", ...
    filename: str                # "baseline_v5.3.1_10yrs.db"
    survey_years: int | None = None
    label: str | None = None
    footprint: str | None = None
    status: str = "registered"
    n_obs: int | None = None     # opcional, para chequeo de sanidad post-descarga
    size_bytes: int | None = None  # tamanho esperado del .db (confirmado en el indice S3DF)
    sha256: str | None = None    # si se fija aqui, se exige en la verificacion
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUS:
            raise RegistryError(
                f"run '{self.name}': status '{self.status}' invalido "
                f"(use uno de {sorted(_VALID_STATUS)})"
            )

    # --- helpers ---
    def url(self, s3df_base: str) -> str:
        base = s3df_base.rstrip("/")
        return f"{base}/sims_featureScheduler_runs{self.release}/{self.family}/{self.filename}"


class Registry:
    """Carga, valida y consulta el registro de bases OpSim."""

    def __init__(self, config: dict[str, Any]):
        self._defaults: dict[str, Any] = config.get("defaults", {}) or {}
        raw_runs: dict[str, Any] = config.get("runs", {}) or {}
        self._runs: dict[str, OpSimRun] = {}
        for name, spec in raw_runs.items():
            self._runs[name] = self._build_run(name, spec)

    # ------------------------------------------------------------------ carga
    @classmethod
    def load(cls) -> "Registry":
        """Carga el registro curado y fusiona el local si existe."""
        curated = _read_yaml(_paths.curated_registry_path(), required=True)
        local = _read_yaml(_paths.local_registry_path(), required=False)
        merged = _deep_merge(curated, local)
        return cls(merged)

    @staticmethod
    def _build_run(name: str, spec: dict[str, Any]) -> OpSimRun:
        if not isinstance(spec, dict):
            raise RegistryError(f"run '{name}': la entrada debe ser un mapping")
        missing = [k for k in _REQUIRED_FIELDS if k not in spec]
        if missing:
            raise RegistryError(f"run '{name}': faltan campos obligatorios {missing}")
        known = {f.name for f in dataclasses.fields(OpSimRun)} - {"name"}
        unknown = set(spec) - known
        if unknown:
            raise RegistryError(f"run '{name}': campos desconocidos {sorted(unknown)}")
        return OpSimRun(name=name, **spec)

    # --------------------------------------------------------------- consulta
    @property
    def s3df_base(self) -> str:
        base = self._defaults.get("s3df_base")
        if not base:
            raise RegistryError("falta 'defaults.s3df_base' en opsims.yaml")
        return base

    def data_dir(self) -> Path:
        return _paths.data_dir(self._defaults.get("data_dir"))

    def __iter__(self) -> Iterator[OpSimRun]:
        return iter(self._runs.values())

    def __contains__(self, name: str) -> bool:
        return name in self._runs

    def names(self) -> list[str]:
        return list(self._runs)

    def get(self, name: str) -> OpSimRun:
        try:
            return self._runs[name]
        except KeyError:
            raise RegistryError(
                f"run '{name}' no esta en el registro. "
                f"Disponibles: {', '.join(self.names()) or '(ninguno)'}"
            ) from None

    def url_for(self, name: str) -> str:
        return self.get(name).url(self.s3df_base)

    def local_path(self, name: str) -> Path:
        """Ruta local del .db (exista o no). Las capas superiores usan esto."""
        return self.data_dir() / self.get(name).filename

    def is_downloaded(self, name: str) -> bool:
        return self.local_path(name).exists()

    # ----------------------------------------------------------- escritura local
    def record_sha256(self, name: str, value: str) -> None:
        """Guarda el sha256 observado en opsims.local.yaml (no toca el curado)."""
        self.get(name)  # valida existencia
        local = _read_yaml(_paths.local_registry_path(), required=False)
        local.setdefault("runs", {}).setdefault(name, {})["sha256"] = value
        _write_local_yaml(local)
        self._runs[name].sha256 = value

    def add_run(self, name: str, spec: dict[str, Any]) -> OpSimRun:
        """Registra una base nueva escribiendo en opsims.local.yaml.

        Para altas 'oficiales', el usuario luego mueve la entrada al opsims.yaml
        curado a mano; el local es para experimentar rapido.
        """
        if name in self._runs:
            raise RegistryError(f"run '{name}' ya existe en el registro")
        run = self._build_run(name, spec)      # valida antes de escribir
        local = _read_yaml(_paths.local_registry_path(), required=False)
        local.setdefault("runs", {})[name] = spec
        _write_local_yaml(local)
        self._runs[name] = run
        return run


# ============================================================== utilidades I/O
def _read_yaml(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise RegistryError(f"no existe el registro requerido: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise RegistryError(f"{path}: el YAML raiz debe ser un mapping")
    return data


def _write_local_yaml(data: dict[str, Any]) -> None:
    path = _paths.local_registry_path()
    header = (
        "# ARCHIVO AUTO-GESTIONADO por fetch_opsim.py — NO editar a mano ni versionar.\n"
        "# Contiene checksums observados y altas locales. Ver pipeline/opsims.yaml.\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Fusion recursiva: `over` gana sobre `base` a nivel de hoja."""
    out = copy.deepcopy(base)
    for key, val in (over or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    """sha256 en streaming (archivos de ~700 MB sin cargar en RAM)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()