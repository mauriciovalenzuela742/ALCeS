import sqlite3
import pandas as pd
from lightcurvelynx.obstable.opsim import OpSim
# Fase 74: REPO_ROOT resuelto por local_env.py (portabilidad).
from local_env import REPO_ROOT

con = sqlite3.connect(str(REPO_ROOT / "data/opsim/baseline_v5.3.1_10yrs.db"))
df = pd.read_sql_query("SELECT * FROM observations", con)
print("raw rows:", len(df))
print("columns:", list(df.columns)[:15])

ops = OpSim(df)
print("OpSim loaded OK, n obs:", len(ops))
print(ops.table.columns.tolist()[:15])
print(ops.table[["ra", "dec", "time", "filter"]].head())
