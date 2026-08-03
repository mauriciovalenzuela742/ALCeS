"""
classify.py — Aislamiento de la sensibilidad al esquema OpSim.

TODA la diferencia entre v5.0 y v5.3 que afecta la separacion WFD/DDF vive aqui:
la clasificacion se basa en `scheduler_note`, cuyas familias cambiaron en v5.3
(aparecen 'templates ...' y 'pair_33 ... bs NN'). En vez de listas fijas por
version, clasificamos por PREFIJO configurable, de modo que la misma regla sirve
para v5.0 y v5.3 (y probablemente para versiones futuras).

Prioridad de asignacion:  DDF  >  WFD  >  twilight  >  Other
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd


@dataclasses.dataclass(frozen=True)
class ClassificationRules:
    """Reglas por prefijo de `scheduler_note`."""

    ddf_prefixes: tuple[str, ...] = ("DD:",)
    wfd_prefixes: tuple[str, ...] = (
        "pair_", "blob_long", "blob", "long", "greedy", "templates",
    )
    twilight_prefixes: tuple[str, ...] = ("twilight_near_sun",)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ClassificationRules":
        d = d or {}
        return cls(
            ddf_prefixes=tuple(d.get("ddf_prefixes", cls.ddf_prefixes)),
            wfd_prefixes=tuple(d.get("wfd_prefixes", cls.wfd_prefixes)),
            twilight_prefixes=tuple(d.get("twilight_prefixes", cls.twilight_prefixes)),
        )


def _startswith_mask(notes: pd.Series, prefixes: tuple[str, ...]) -> np.ndarray:
    if not prefixes:
        return np.zeros(len(notes), dtype=bool)
    # tuple -> startswith de cualquiera de los prefijos; NaN -> ""
    return notes.fillna("").astype(str).str.startswith(tuple(prefixes)).to_numpy()


def classify_field_type(notes: pd.Series, rules: ClassificationRules | None = None) -> pd.Series:
    """Devuelve una Serie 'field_type' con valores WFD / DDF / twilight / Other.

    Parameters
    ----------
    notes : pd.Series
        Columna `scheduler_note` del DataFrame OpSim.
    rules : ClassificationRules, optional
        Reglas por prefijo; por defecto las que cubren v5.0 y v5.3.
    """
    rules = rules or ClassificationRules()
    ddf = _startswith_mask(notes, rules.ddf_prefixes)
    wfd = _startswith_mask(notes, rules.wfd_prefixes)
    twi = _startswith_mask(notes, rules.twilight_prefixes)
    out = np.select(
        [ddf, wfd & ~ddf, twi & ~ddf & ~wfd],
        ["DDF", "WFD", "twilight"],
        default="Other",
    )
    return pd.Series(out, index=notes.index, name="field_type")


def classification_summary(field_type: pd.Series) -> dict[str, int]:
    """Conteo por tipo, util para el log y para detectar notas 'Other' sospechosas."""
    return field_type.value_counts().to_dict()
