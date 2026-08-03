'''Capa 4 — Post-proceso: lectura de FITS en memoria + control de calidad automatico.'''

from .converter import read_genversion, read_head, read_phot  # noqa: F401
from .qc import run_all_qc  # noqa: F401

__all__ = ["read_genversion", "read_head", "read_phot", "run_all_qc"]
