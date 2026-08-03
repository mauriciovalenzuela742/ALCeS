'''
Pipeline config-driven para simulaciones de curvas de luz (Vera C. Rubin / SNANA).
'''

__version__ = "0.1.0"

from .registry import Registry, OpSimRun, RegistryError  # noqa: F401

__all__ = ["Registry", "OpSimRun", "RegistryError", "__version__"]
