"""
Fase 6: soporte NON1ASED para el PoC de LightCurveLynx -- primera clase de
modelo fuera de SIMSED/SALT2 (14 clases SIMSED + 1 SALT2 ya cubiertas,
ver NOTES.md Fase 0-5). Complementa el bloque NON1A_KEYS:/NON1A: que
pipeline/tools/generate_non1a_block.py ya genera del lado SNANA, leyendo
el mismo formato real del lado LightCurveLynx.

SIMSEDModel.from_dir() (usado por run_simsed_poc.py) exige un SED.INFO
(yaml.safe_load sobre el archivo completo) -- confirmado que los
directorios NON1ASED reales NO lo traen (NON1ASED.SNIa-91bg/ en NLHPC solo
tiene *.SED.gz + NON1A.LIST, verificado via ssh nlhpc). En su lugar se usa
el constructor directo heredado de MultiSEDTemplateModel(templates, *,
weights=None, **kwargs) -- confirmado via inspect.signature() en el venv
real de NLHPC que es publico/estable, y es exactamente lo que
SIMSEDModel.from_dir() llama internamente tras parsear SED.INFO
(cls(templates, flux_scale=flux_scale, **kwargs), ver fuente real de
sed_template_model.py). Los templates se construyen con
SIMSEDModel._read_simsed_data_file(), el mismo staticmethod que from_dir()
usa (incluye el fallback ".SED" -> ".SED.gz"); no se reimplementa el
parseo del grid de flujo.

Los pesos se leen del bloque real NON1A_KEYS:/NON1A: en el .INPUT (fuente
de verdad de lo que SNANA realmente usa), no se re-derivan como 1/N --
GivenValueSampler normaliza internamente (weights /= weights.sum()), asi
que no hace falta que sumen 1.
"""
from __future__ import annotations

import re
from pathlib import Path

from lightcurvelynx.models.sed_template_model import SIMSEDModel

NON1A_LIST_RE = re.compile(r"^NON1A:\s+(\d+)\s+(\S+)\s+(\S+)")
FLUX_SCALE_RE = re.compile(r"^FLUX_SCALE:\s+([\d.eE+-]+)")
NON1A_WEIGHT_RE = re.compile(
    r"^NON1A:\s+(\d+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+(\d+)"
)


def parse_non1a_list(path: Path) -> list[tuple[int, str]]:
    """Lee NON1A.LIST real: lineas 'NON1A: <index> <name> <filename>'.

    Devuelve [(index, filename), ...] en el orden del archivo. <name>
    (segunda columna) se ignora -- es el nombre de la clase, igual en
    todas las filas, no un identificador por template.
    """
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = NON1A_LIST_RE.match(line)
            if m:
                entries.append((int(m.group(1)), m.group(3)))
    return entries


def parse_flux_scale(non1a_list_path: Path) -> float:
    """Lee la linea suelta 'FLUX_SCALE: <valor>' de NON1A.LIST (no es YAML,
    a diferencia del FLUX_SCALE de SED.INFO que SIMSEDModel.from_dir() lee)."""
    with open(non1a_list_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = FLUX_SCALE_RE.match(line)
            if m:
                return float(m.group(1))
    return 1.0


def parse_non1a_weights_from_input(input_path: Path) -> dict[int, float]:
    """Lee el bloque real NON1A_KEYS:/NON1A: <idx> <WGT> <MAGOFF> <MAGSMEAR>
    <SNTYPE> del .INPUT real ya generado (por generate_non1a_block.py o a
    mano) -- referencia de lo que SNANA de verdad usa, no una re-derivacion.

    MAGOFF/MAGSMEAR se ignoran (confirmado 0.0 en las clases NON1ASED de
    este proyecto -- sin precedente de calibracion observacional, ver
    NEXT_SESSION.md). Si alguna clase futura los declara != 0 esto falla
    ruidosamente en vez de ignorarlos en silencio -- SIMSEDModel no tiene
    un hook equivalente para aplicar magnitude offset/smear por template.
    """
    weights: dict[int, float] = {}
    with open(input_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = NON1A_WEIGHT_RE.match(line)
            if not m:
                continue
            idx, wgt, magoff, magsmear, _sntype = m.groups()
            if float(magoff) != 0.0 or float(magsmear) != 0.0:
                raise NotImplementedError(
                    f"NON1A index {idx} en {input_path}: MAGOFF/MAGSMEAR != 0 "
                    "no soportado por este loader (ver docstring de non1ased.py)."
                )
            weights[int(idx)] = float(wgt)
    return weights


def load_non1ased_model(non1ased_dir: Path, input_path: Path, **kwargs) -> SIMSEDModel:
    """Construye un SIMSEDModel real (misma clase, mismo grid de flujo por
    template) desde un directorio NON1ASED real, sin pasar por SED.INFO
    (que no existe ahi) -- via NON1A.LIST + el bloque NON1A_KEYS del
    .INPUT real en vez de SED.INFO.

    kwargs se pasan tal cual al constructor de SIMSEDModel (ra, dec,
    redshift, distance, t0, ...), igual que en run_simsed_poc.py.
    """
    non1ased_dir = Path(non1ased_dir)
    list_path = non1ased_dir / "NON1A.LIST"
    entries = parse_non1a_list(list_path)
    if not entries:
        raise ValueError(f"no se encontraron lineas 'NON1A:' en {list_path}")
    flux_scale = parse_flux_scale(list_path)
    weight_by_index = parse_non1a_weights_from_input(input_path)

    templates = []
    weights = []
    for idx, file_name in entries:
        templates.append(SIMSEDModel._read_simsed_data_file(non1ased_dir / file_name))
        weights.append(weight_by_index[idx])

    return SIMSEDModel(templates, flux_scale=flux_scale, weights=weights, **kwargs)
