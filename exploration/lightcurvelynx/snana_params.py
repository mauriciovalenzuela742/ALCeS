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
from lightcurvelynx.effects.extinction import ExtinctionEffect


class ClippedExtinctionEffect(ExtinctionEffect):
    """ExtinctionEffect que clampea las longitudes de onda al rango valido
    del modelo dust_extinction subyacente en vez de lanzar ValueError.

    Necesario para clases con GENRANGE_REDSHIFT alto (p.ej. TDE-MOSFIT,
    z hasta 2.9, host extinction en frame='rest'): a z~2.9 el borde azul
    de LSST-u (~3200 A observado) cae en rest-frame a ~820 A
    (obs_to_rest_times_waves divide por 1+z), por debajo del limite fisico
    real de 1000 A (x=10 1/micron) al que estan calibradas las leyes de
    extincion parametricas estandar (CCM89/O94/F99/...) -- no es un bug de
    LightCurveLynx ni nuestro, es el limite real de la calibracion
    empirica. Igual que la extrapolacion (ZeroPadding/LinearDecay) que
    LightCurveLynx ya usa para el SED fuera de RESTLAMBDA_RANGE, se
    clampea el input en vez de inventar una extrapolacion nueva -- la
    extincion se mantiene constante (igual al valor de borde) mas alla del
    rango calibrado, en vez de fallar toda la simulacion por un punado de
    objetos en la cola de mayor z.
    """

    def apply(self, flux_density, times=None, wavelengths=None, ebv=None, **kwargs):
        x_min, x_max = self._extinction_wrapper.ext_obj.x_range  # 1/micron
        lam_min_aa, lam_max_aa = 1e4 / x_max, 1e4 / x_min
        clipped = np.clip(wavelengths, lam_min_aa, lam_max_aa)
        return super().apply(flux_density, times=times, wavelengths=clipped, ebv=ebv, **kwargs)


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


def build_dndz_ccs15_cdf(
    scale: float,
    z_min: float,
    z_max: float,
    *,
    H0: float = 70.0,
    Om0: float = 0.3,
    n_grid: int = 2000,
) -> tuple[np.ndarray, np.ndarray]:
    """`DNDZ: CC_S15` de SNANA (tasa de core-collapse, Strolger 2015) --
    misma forma funcional que MD14 pero con los parametros A,B,C,D
    ajustados a R_CC(z) (Fig 6, Ec 9 de Strolger 2015), NO los de la
    tasa de formacion estelar general. Formula y constantes leidas
    directo del codigo fuente real de SNANA
    (~/github/SNANA_src/src/snlc_sim.c, bloque
    `INDEX_RATEMODEL_CCS15`) -- no una aproximacion:

        rate(z) = k * h^2 * SFR_MD14(z; A=0.015,B=1.50,C=5.00,D=6.10)
                  * DNDZ_ALLSCALE
        k = 0.0091, h = H0/100

    `scale` = DNDZ_ALLSCALE del .INPUT real de cada clase. La
    normalizacion absoluta no importa para el sampleo por CDF (se
    cancela), pero se mantiene por fidelidad con la fuente."""
    cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
    z_grid = np.linspace(z_min, z_max, n_grid)
    h = H0 / 100.0
    k = 0.0091
    A, B, C, D = 0.015, 1.50, 5.00, 6.10
    sfr = A * (1.0 + z_grid) ** C / (1.0 + ((1.0 + z_grid) / B) ** D)
    rate_z = k * (h ** 2) * sfr * scale

    dn_dz = np.array([
        rate_z[i] * _comoving_volume_element(z_grid[i], cosmo) / (1.0 + z_grid[i])
        for i in range(n_grid)
    ])
    cdf = np.cumsum(dn_dz)
    cdf -= cdf[0]
    if cdf[-1] <= 0:
        raise ValueError("CDF de DNDZ CC_S15 degenerada -- revisar scale/z_min/z_max.")
    cdf /= cdf[-1]
    return z_grid, cdf


def build_dndz_tde_cdf(
    rate0: float,
    z_min: float,
    z_max: float,
    *,
    H0: float = 70.0,
    Om0: float = 0.3,
    n_grid: int = 2000,
) -> tuple[np.ndarray, np.ndarray]:
    """`DNDZ: TDE` de SNANA -- decaimiento exponencial simple en z, leido
    directo de snlc_sim.c (bloque `INDEX_RATEMODEL_TDE`):
        rate(z) = rate0 * 10^(-0.5*z/0.6)
    """
    cosmo = FlatLambdaCDM(H0=H0, Om0=Om0)
    z_grid = np.linspace(z_min, z_max, n_grid)
    rate_z = rate0 * 10.0 ** (-0.5 * z_grid / 0.6)

    dn_dz = np.array([
        rate_z[i] * _comoving_volume_element(z_grid[i], cosmo) / (1.0 + z_grid[i])
        for i in range(n_grid)
    ])
    cdf = np.cumsum(dn_dz)
    cdf -= cdf[0]
    if cdf[-1] <= 0:
        raise ValueError("CDF de DNDZ TDE degenerada -- revisar rate0/z_min/z_max.")
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


# ------------------------------------------------------------------ AV exponencial (host)
def make_exp_av_sampler(tau: float, av_max: float, *, seed: int | None = None):
    """Extincion de galaxia anfitriona `dN/dAV = exp(-AV/tau)` truncada en
    [0, av_max] -- el caso "solo componente exponencial, sin nucleo
    Gaussiano" que declaran TDE-MOSFIT (`GENTAU_AV: 0.4`) y SNIax
    (`GENTAU_AV: 1.7`) en vez del modelo WV07 mixto (que sí se omitio en
    esta fase, ver NOTES.md Fase 2 parte B -- ese es un modelo distinto,
    con un historial de bugs documentado en el codigo real de SNANA que
    hizo preferible no reimplementarlo de memoria). Esta version pura
    exponencial es la formula estandar de inversion de CDF truncada, sin
    esa complejidad -- CDF(AV) = (1-exp(-AV/tau)) / (1-exp(-av_max/tau))."""
    rng = np.random.default_rng(seed)
    norm = 1.0 - np.exp(-av_max / tau)

    def sampler(size=None, **_kwargs):
        n = 1 if size is None else (size if np.isscalar(size) else size[0])
        u = rng.uniform(0.0, 1.0, size=n)
        av = -tau * np.log(1.0 - u * norm)
        return av if size is not None else float(av[0])

    sampler.__name__ = "exp_av_sampler"
    return sampler


# ------------------------------------------------------------------ N-dim correlated normal
def make_correlated_normal_weights(
    values: dict[str, np.ndarray],
    peaks: dict[str, float],
    sigmas: dict[str, float],
    redcor: dict[tuple[str, str], float],
) -> np.ndarray:
    """Generaliza el peso de `SIMSED_REDCOR` a N parametros (no solo los 2
    de SALT2 c/x1) -- evalua la PDF de la normal multivariada
    correlacionada (covarianza construida desde sigmas + REDCOR
    pareados) en el valor propio de cada template, igual criterio que
    `template_weights_from_redcor` en run_simsed_91bg_ddf_poc.py pero
    para cualquier numero de parametros (p.ej. pc1/pc2/pc3 de SNII-NMF).

    `values`: {nombre_param: array de valores por template}.
    `peaks`/`sigmas`: {nombre_param: GENPEAK/GENSIGMA (simetrica)}.
    `redcor`: {(param_i, param_j): SIMSED_REDCOR(param_i,param_j)} -- solo
    los pares declarados, el resto se asume no correlacionado (0)."""
    names = list(values.keys())
    n_par = len(names)
    n_tmpl = len(next(iter(values.values())))

    cov = np.zeros((n_par, n_par))
    for i, ni in enumerate(names):
        cov[i, i] = sigmas[ni] ** 2
    for (a, b), rc in redcor.items():
        i, j = names.index(a), names.index(b)
        cov[i, j] = cov[j, i] = rc * sigmas[a] * sigmas[b]

    inv_cov = np.linalg.inv(cov)
    d = np.stack([values[n] - peaks[n] for n in names], axis=1)  # (n_tmpl, n_par)
    exponent = -0.5 * np.einsum("ni,ij,nj->n", d, inv_cov, d)
    return np.exp(exponent)


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
