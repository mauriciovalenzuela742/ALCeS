"""
Valida el patron de orquestacion propuesto para Fase 2: un unico job SLURM
(nunca el login node) que levanta un `dask.distributed.LocalCluster` interno
y paraleliza el trabajo entre sus cores -- sin `dask_jobqueue` (no instalado,
innecesario a esta escala: Fase 0 ya midio que el throughput de un solo core
alcanza y sobra) ni `ray` (tampoco instalado).

No es Fase 2 real (cobertura de clases, wrapper SIMSED) -- es una prueba de
que el patron de paralelizacion funciona, usando simulate_lightcurves() real
(no una tarea de prueba/proxy) para que la medicion de speedup sea genuina.

Estrategia: 4 chunks independientes de NGEN=500 (mismo total que
NGENTOT_LC=2000 del PoC de Fase 1), cada uno con su propio seed, corridos
(a) secuencial en un solo proceso y (b) en paralelo via dask LocalCluster --
comparando wall time real de la parte que si escala con cores (la
simulacion), no la carga inicial de modelos (SALT2/OpSim/passbands, que solo
ocurre una vez, fuera del bloque cronometrado).

Uso (dentro de un job sbatch, nunca en el login node):
    python3 run_dask_poc.py
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sncosmo
from dask.distributed import Client, LocalCluster

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.astro_utils.snia_utils import DistModFromRedshift, X0FromDistMod
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.math_nodes.ra_dec_sampler import ObsTableRADECSampler
from lightcurvelynx.models.sncosmo_models import SncosmoWrapperModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
from lightcurvelynx.utils.extrapolate import LinearDecay, ZeroPadding

from snana_params import build_dndz_powerlaw2_cdf, make_dndz_sampler, make_bifurcated_normal_sampler, SizeAwareFunctionNode

HERE = Path(__file__).resolve().parent
SNANA_HOME = Path("/home/mvalenzuela")
OPSIM_DB = SNANA_HOME / "AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db"
SALT2_LOCAL_DIR = HERE / "salt2_h17_local"

GENRANGE_REDSHIFT = (0.011, 1.2)
SALT2C = dict(peak=-0.054, sigma_lo=0.043, sigma_hi=0.101, lo=-0.3, hi=0.5)
SALT2X1 = dict(peak=0.973, sigma_lo=1.472, sigma_hi=0.222, lo=-3.0, hi=2.0)
ALPHA, BETA = 0.14, 3.1
SIGMA_INT = 0.090
DNDZ_SEGMENTS = [(2.5e-5, 1.5, 0.0, 1.0), (9.7e-5, -0.5, 1.0, 3.0)]

N_CHUNKS = 4
NGEN_PER_CHUNK = 500  # 4 x 500 = 2000, igual al total de Fase 1


def build_survey_info():
    """Carga OpSim + passbands una sola vez -- se reusa entre chunks (no se
    puede pickle/enviar a workers de dask sin costo, asi que cada worker la
    reconstruye una vez via _survey_info() dentro del propio task, no aqui)."""
    con = sqlite3.connect(str(OPSIM_DB))
    df = pd.read_sql_query("SELECT * FROM observations", con)
    df_ddf = df[df["target_name"].str.contains("ddf_", na=False)].reset_index(drop=True)
    df_ddf["field"] = df_ddf["target_name"].str.extract(r"ddf_(\w+)")
    obs_table = OpSim(df_ddf, zp_err_mag=0.005)
    passband_group = PassbandGroup.from_preset(preset="LSST")
    survey_info = SurveyInfo(obstable=obs_table, passbands=passband_group, survey_name="LSST")
    return survey_info, obs_table


def simulate_chunk(seed_base: int, n_objects: int) -> int:
    """Simula un chunk independiente (su propio grafo de samplers, mismo
    patron que run_snia_ddf_poc.py) y devuelve el numero de objetos
    generados -- funcion top-level (no closure) para que dask pueda
    serializarla y mandarla a los workers."""
    survey_info, obs_table = build_survey_info()
    local_src = sncosmo.SALT2Source(modeldir=str(SALT2_LOCAL_DIR), name=f"salt2-h17-local-{seed_base}")

    z_grid, cdf = build_dndz_powerlaw2_cdf(
        segments=DNDZ_SEGMENTS, z_min=GENRANGE_REDSHIFT[0], z_max=GENRANGE_REDSHIFT[1],
    )
    redshift_func = SizeAwareFunctionNode(make_dndz_sampler(z_grid, cdf, seed=seed_base + 1), node_label="redshift")
    c_func = SizeAwareFunctionNode(make_bifurcated_normal_sampler(**SALT2C, seed=seed_base + 2), node_label="c")
    x1_func = SizeAwareFunctionNode(make_bifurcated_normal_sampler(**SALT2X1, seed=seed_base + 3), node_label="x1")
    distmod_func = DistModFromRedshift(redshift_func, H0=73.0, Omega_m=0.3)
    m_abs_func = NumpyRandomFunc("normal", loc=-19.3, scale=SIGMA_INT, seed=seed_base + 4)
    x0_func = X0FromDistMod(distmod=distmod_func, x1=x1_func, c=c_func, alpha=ALPHA, beta=BETA, m_abs=m_abs_func)
    radec_sampler = ObsTableRADECSampler(obs_table, seed=seed_base + 5)
    t0_func = NumpyRandomFunc(
        "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max()), seed=seed_base + 6,
    )
    source = SncosmoWrapperModel(
        local_src, t0=t0_func, x0=x0_func, x1=x1_func, c=c_func,
        ra=radec_sampler.ra, dec=radec_sampler.dec, redshift=redshift_func,
        node_label="source", time_extrapolation=LinearDecay(50.0), wave_extrapolation=ZeroPadding(),
    )
    lc = simulate_lightcurves(source, n_objects, survey_info, rest_time_window_offset=(-30, 100))
    return len(lc)


def main():
    print("=== Fase 2 (prep): validacion de orquestacion con dask LocalCluster ===")

    # --- (a) secuencial, 1 proceso, 4 chunks uno tras otro ---
    t0 = time.time()
    seq_results = [simulate_chunk(20260813_000 + i, NGEN_PER_CHUNK) for i in range(N_CHUNKS)]
    t_seq = time.time() - t0
    print(f"secuencial: {N_CHUNKS} chunks x {NGEN_PER_CHUNK} = {sum(seq_results)} objetos "
          f"en {t_seq:.1f}s")

    # --- (b) paralelo, LocalCluster dentro de este mismo job SLURM ---
    n_workers = min(N_CHUNKS, 4)
    cluster = LocalCluster(n_workers=n_workers, threads_per_worker=1, processes=True)
    client = Client(cluster)
    print(f"LocalCluster: {n_workers} workers, {len(client.scheduler_info()['workers'])} "
          f"confirmados por el scheduler")

    t0 = time.time()
    futures = [client.submit(simulate_chunk, 20260813_100 + i, NGEN_PER_CHUNK) for i in range(N_CHUNKS)]
    par_results = client.gather(futures)
    t_par = time.time() - t0
    print(f"paralelo (dask): {N_CHUNKS} chunks x {NGEN_PER_CHUNK} = {sum(par_results)} objetos "
          f"en {t_par:.1f}s")
    print(f"speedup: {t_seq / t_par:.2f}x (ideal con {n_workers} workers: {n_workers:.1f}x)")

    client.close()
    cluster.close()
    print("=== fin ===")


if __name__ == "__main__":
    main()
