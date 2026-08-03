"""
config.py — Config declarativa del constructor de SIMLIB (Capa 1).

Lee pipeline/simlib.yaml y lo materializa en dataclasses. Todo lo que cambia
entre estrategias (WFD/DDF) o entre versiones (clasificacion, recorte temporal)
es dato, no codigo.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from .classify import ClassificationRules
from .writer import WriterParams


@dataclasses.dataclass(frozen=True)
class StrategyConfig:
    n_fields: int
    min_visits: int


@dataclasses.dataclass(frozen=True)
class TemporalCut:
    date_min: str | None = None   # ISO; None = inicio del survey
    date_max: str | None = None   # ISO; None = fin del survey
    mjd_min: float | None = None  # tiene prioridad sobre date_min si se da
    mjd_max: float | None = None


@dataclasses.dataclass
class SimlibConfig:
    nside: int
    pixsize: float
    seed: int
    author: str
    bands: str
    radius_deg: float
    strategies: dict[str, StrategyConfig]
    rules: ClassificationRules
    cut: TemporalCut
    writer: WriterParams

    def strategy(self, name: str) -> StrategyConfig:
        key = name.upper()
        if key not in self.strategies:
            raise KeyError(f"estrategia '{name}' no definida (hay: {list(self.strategies)})")
        return self.strategies[key]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SimlibConfig":
        path = Path(path) if path else Path(__file__).resolve().parent.parent / "simlib.yaml"
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        d = raw.get("defaults", {}) or {}
        strategies = {
            k.upper(): StrategyConfig(n_fields=v["n_fields"], min_visits=v["min_visits"])
            for k, v in (raw.get("strategies", {}) or {}).items()
        }
        cut_raw = raw.get("temporal_cut", {}) or {}
        writer = WriterParams(
            pixsize=d.get("pixsize", 0.2),
            ccd_gain=d.get("ccd_gain", 1.0),
            ccd_noise=d.get("ccd_noise", 0.25),
            zpt_err=d.get("zpt_err", 0.005),
            filters=d.get("bands", "ugrizY"),
            author=d.get("author", "pipeline"),
        )
        return cls(
            nside=d.get("nside", 256),
            pixsize=d.get("pixsize", 0.2),
            seed=d.get("seed", 42),
            author=d.get("author", "pipeline"),
            bands=d.get("bands", "ugrizY"),
            radius_deg=d.get("radius_deg", 1.75),
            strategies=strategies,
            rules=ClassificationRules.from_dict(raw.get("classification")),
            cut=TemporalCut(
                date_min=cut_raw.get("date_min"),
                date_max=cut_raw.get("date_max"),
                mjd_min=cut_raw.get("mjd_min"),
                mjd_max=cut_raw.get("mjd_max"),
            ),
            writer=writer,
        )
