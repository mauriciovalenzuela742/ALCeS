import time
import sqlite3
import numpy as np
import pandas as pd

from lightcurvelynx.astro_utils.passbands import PassbandGroup
from lightcurvelynx.astro_utils.snia_utils import DistModFromRedshift, X0FromDistMod
from lightcurvelynx.math_nodes.np_random import NumpyRandomFunc
from lightcurvelynx.models.sncosmo_models import SncosmoWrapperModel
from lightcurvelynx.obstable.opsim import OpSim
from lightcurvelynx.simulate import simulate_lightcurves
from lightcurvelynx.survey_info import SurveyInfo
from lightcurvelynx.utils.extrapolate import LinearDecay

t_start = time.time()

con = sqlite3.connect("/home/mvalenzuela/AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db")
df = pd.read_sql_query("SELECT * FROM observations", con)
obs_table = OpSim(df)
print(f"[{time.time()-t_start:.1f}s] OpSim loaded: {len(obs_table)} obs")

passband_group = PassbandGroup.from_preset(preset="LSST")
print(f"[{time.time()-t_start:.1f}s] passbands loaded")

redshift_sampler = NumpyRandomFunc("uniform", low=0.01, high=0.6)
distmod_func = DistModFromRedshift(redshift_sampler, H0=73.0, Omega_m=0.3)
x1_func = NumpyRandomFunc("normal", loc=0, scale=2.0)
c_func = NumpyRandomFunc("normal", loc=0, scale=0.02)
m_abs_func = NumpyRandomFunc("normal", loc=-19.3, scale=0.1)
x0_func = X0FromDistMod(
    distmod=distmod_func, x1=x1_func, c=c_func, alpha=0.14, beta=3.1, m_abs=m_abs_func,
)

ra_func = NumpyRandomFunc("uniform", low=0.0, high=360.0)
dec_func = NumpyRandomFunc("uniform", low=-70.0, high=10.0)
t0_func = NumpyRandomFunc(
    "uniform", low=float(obs_table["time"].min()), high=float(obs_table["time"].max())
)

source = SncosmoWrapperModel(
    "salt2-h17",
    t0=t0_func,
    x0=x0_func,
    x1=x1_func,
    c=c_func,
    ra=ra_func,
    dec=dec_func,
    redshift=redshift_sampler,
    node_label="source",
    time_extrapolation=LinearDecay(50.0),
)

survey_info = SurveyInfo(obstable=obs_table, passbands=passband_group, survey_name="LSST")

for n in (200, 1000):
    t0 = time.time()
    lightcurves = simulate_lightcurves(
        source, n, survey_info, rest_time_window_offset=(-20, 50),
    )
    dt = time.time() - t0
    n_out = len(lightcurves)
    print(f"N={n}: {dt:.2f}s total, {dt/n*1000:.2f} ms/event, {n_out} objects returned")

print(f"[{time.time()-t_start:.1f}s] TOTAL WALL TIME")
