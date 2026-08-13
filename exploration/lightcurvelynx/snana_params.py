"""
Samplers custom que replican dos piezas de SNIa-SALT2.INPUT (SNANA) que
LightCurveLynx no trae nativo (ver Fase 0 NOTES.md):

1. DNDZ: POWERLAW2 -- tasa volumetrica de SNIa vs redshift (no uniforme).
2. Gaussianas bifurcadas para SALT2 x1/c (sigma distinto a cada lado del pico).

Se envuelven en lightcurvelynx.base_models.FunctionNode (la clase base que
usa NumpyRandomFunc internamente -- confirmado leyendo
math_nodes/np_random.py: NumpyRandomFunc.__init__ hace
`super().__init__(func, **kwargs)` con `func = getattr(rng, func_name)`, o
sea que FunctionNode acepta cualquier callable, no solo funciones de
numpy.random). Cada sampler de aqui expone la firma `func(size=None, **kw)`
para calzar con como FunctionNode invoca a su `func`.
"""
from __future__ import annotations

import numpy as np
from scipy.integrate import quad
from astropy.cosmology import FlatLambdaCDM

from lightcurvelynx.base_models import FunctionNode


class SizeAwareFunctionNode(FunctionNode):
    """FunctionNode que SI pasa `size=graph_state.num_samples` a la funcion
    envuelta -- la base FunctionNode.compute() llama `self.func(**args)` sin
    `size` en absoluto (confirmado leyendo base_models.py), asi que una
    funcion con firma `func(size=None, **kw)` recibe siempre size=None y
    devuelve UN solo valor que el grafo termina difundiendo (broadcast) a
    los N samples -- bug real encontrado en la Fase 1: los primeros PoC
    tenian TODOS los objetos con el mismo z/x1/c (un solo valor repetido).
    Mismo patron que usa NumpyRandomFunc.compute() internamente, aplicado a
    un callable arbitrario en vez de una funcion de numpy.random."""

    def compute(self, graph_state, rng_info=None, **kwargs):
        args = self._build_inputs(graph_state, **kwargs)
        results = self.func(size=graph_state.num_samples, **args)
        self._save_results(results, graph_state)
        return results


# ------------------------------------------------------------------ DNDZ
def _comoving_volume_element(z: float, cosmo: FlatLambdaCDM) -> float:
    """dV_c/dz (Mpc^3) -- shell de volumen comovil por unidad de z."""
    return cosmo.differential_comoving_volume(z).value  # Mpc^3/sr, luego *4pi si hiciera falta


def _md14_sfr(z: np.ndarray) -> np.ndarray:
    """Madau & Dickinson 2014 (ApJ, arXiv:1403.0007) cosmic star-formation-
    rate density, Msun/yr/Mpc^3 -- formula estandar y ampliamente citada,
    usada por SNANA como `DNDZ: MD14 <rate0>` (rate0 = tasa en z=0, la
    forma se normaliza a SFR_MD14(0))."""
    return 0.015 * (1.0 + z) ** 2.7 / (1.0 + ((1.0 + z) / 2.9) ** 5.6)


def build_dndz_md14_cdf(
    rate0: float,
    z_min: float,
    z_max: float,
    *,
    H0: float = 70.0,
    Om0: float = 0.3,
    n_grid: int = 2000,
) -> tuple[np.ndarray, np.ndarray]:
    """Como build_dndz_powerlaw2_cdf pero con `DNDZ: MD14 <rate0>` de SNANA
    -- tasa proporcional a la forma de Madau&Dickinson 2014 en vez de una
    ley de potencia simple, normalizada para que rate(0) = rate0."""
    cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
    z_grid = np.linspace(z_min, z_max, n_grid)
    sfr0 = _md14_sfr(np.array([0.0]))[0]
    rate_z = rate0 * _md14_sfr(z_grid) / sfr0

    dn_dz = np.array([
        rate_z[i] * _comoving_volume_element(z_grid[i], cosmo) / (1.0 + z_grid[i])
        for i in range(n_grid)
    ])
    cdf = np.cumsum(dn_dz)
    cdf -= cdf[0]
    if cdf[-1] <= 0:
        raise ValueError("CDF de DNDZ MD14 degenerada -- revisar rate0/z_min/z_max.")
    cdf /= cdf[-1]
    return z_grid, cdf


def build_dndz_powerlaw2_cdf(
    segments: list[tuple[float, float, float, float]],
    z_min: float,
    z_max: float,
    *,
    H0: float = 70.0,  # SNANA default (ver Fase 2 parte A) -- antes 73.0 sin
    Om0: float = 0.3,  # verificar, mismo placeholder que ya se corrigio en
    n_grid: int = 2000,  # el calculo de distancia/flujo.
) -> tuple[np.ndarray, np.ndarray]:
    """Construye la CDF de dN/dz = DNDZ(z) * dVc/dz / (1+z) para redshift.

    `segments`: lista de (rate0, beta, z_lo, z_hi) -- exactamente el formato
    de las lineas `DNDZ: POWERLAW2 <rate0> <beta> <z_lo> <z_hi>` de SNANA,
    donde la tasa en ese tramo es `rate0 * (1+z)**beta`. El .INPUT real de
    SNIa tiene 2 tramos (ver SIMGEN_INCLUDE_SNIa-SALT2.INPUT):
        POWERLAW2 2.5E-5  1.5  0.0 1.0
        POWERLAW2 9.7E-5 -0.5  1.0 3.0
    El factor `/(1+z)` es dilucion temporal cosmologica (SNANA la aplica
    tambien -- tasa observada vs tasa en el marco de reposo del evento).

    Devuelve (z_grid, cdf) listos para sampleo por inversion.
    """
    cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
    z_grid = np.linspace(z_min, z_max, n_grid)

    def rate_at(z):
        for rate0, beta, z_lo, z_hi in segments:
            if z_lo <= z < z_hi or (z == z_max and z_hi == z_max):
                return rate0 * (1.0 + z) ** beta
        return 0.0

    dn_dz = np.array([
        rate_at(z) * _comoving_volume_element(z, cosmo) / (1.0 + z) for z in z_grid
    ])
    cdf = np.cumsum(dn_dz)
    cdf -= cdf[0]
    if cdf[-1] <= 0:
        raise ValueError("CDF de DNDZ degenerada -- revisar segments/z_min/z_max.")
    cdf /= cdf[-1]
    return z_grid, cdf


def make_dndz_sampler(z_grid: np.ndarray, cdf: np.ndarray, *, seed: int | None = None):
    """Devuelve una funcion `sampler(size=None)` que samplea redshift por
    inversion de la CDF precomputada (interpolacion lineal)."""
    rng = np.random.default_rng(seed)

    def sampler(size=None, **_kwargs):
        n = 1 if size is None else (size if np.isscalar(size) else size[0])
        u = rng.uniform(0.0, 1.0, size=n)
        z = np.interp(u, cdf, z_grid)
        return z if size is not None else float(z[0])

    sampler.__name__ = "dndz_redshift_sampler"
    return sampler


# ------------------------------------------------------------------ bifurcated gaussian
def make_bifurcated_normal_sampler(
    peak: float, sigma_lo: float, sigma_hi: float, lo: float, hi: float, *, seed: int | None = None
):
    """Gaussiana con sigma distinto a cada lado del pico (bifurcada), con
    corte duro en [lo, hi] via rechazo -- replica el patron
    GENPEAK/GENSIGMA (dos valores)/GENRANGE de SNANA para SALT2c y SALT2x1."""
    rng = np.random.default_rng(seed)

    def sampler(size=None, **_kwargs):
        n = 1 if size is None else (size if np.isscalar(size) else size[0])
        out = np.empty(n)
        filled = 0
        while filled < n:
            batch = max(n - filled, 16)
            side = rng.uniform(size=batch) < 0.5
            sigma = np.where(side, sigma_lo, sigma_hi)
            # sigma_lo va del lado izquierdo del pico (draw < peak), sigma_hi
            # del lado derecho -- misma convencion que GENSIGMA de SNANA.
            magnitude = np.abs(rng.standard_normal(batch)) * sigma
            draw = np.where(side, peak - magnitude, peak + magnitude)
            valid = draw[(draw >= lo) & (draw <= hi)]
            take = min(len(valid), n - filled)
            out[filled:filled + take] = valid[:take]
            filled += take
        return out if size is not None else float(out[0])

    sampler.__name__ = "bifurcated_normal_sampler"
    return sampler


if __name__ == "__main__":
    # sanity check standalone (sin LightCurveLynx) -- corridas rapidas para
    # confirmar que las formas son razonables antes de conectarlas al grafo.
    z_grid, cdf = build_dndz_powerlaw2_cdf(
        segments=[(2.5e-5, 1.5, 0.0, 1.0), (9.7e-5, -0.5, 1.0, 3.0)],
        z_min=0.011, z_max=1.2,
    )
    print("CDF sample (every 200th grid point, should climb smoothly 0->1, not "
          "sit near 0 then jump at the end):")
    print("  ", np.round(cdf[::200], 4))

    z_sampler = make_dndz_sampler(z_grid, cdf, seed=42)
    zs = z_sampler(size=5000)
    pct = np.percentile(zs, [10, 25, 50, 75, 90])
    print(f"z: min={zs.min():.3f} max={zs.max():.3f} mean={zs.mean():.3f} "
          f"p10={pct[0]:.3f} p25={pct[1]:.3f} p50={pct[2]:.3f} p75={pct[3]:.3f} p90={pct[4]:.3f}")
    hist, edges = np.histogram(zs, bins=10, range=(0.011, 1.2))
    print("  histograma (10 bins, 0.011-1.2):", hist.tolist())

    c_sampler = make_bifurcated_normal_sampler(-0.054, 0.043, 0.101, -0.3, 0.5, seed=1)
    cs = c_sampler(size=5000)
    print(f"c: min={cs.min():.3f} max={cs.max():.3f} mean={cs.mean():.3f}")

    x1_sampler = make_bifurcated_normal_sampler(0.973, 1.472, 0.222, -3.0, 2.0, seed=2)
    x1s = x1_sampler(size=5000)
    print(f"x1: min={x1s.min():.3f} max={x1s.max():.3f} mean={x1s.mean():.3f}")
