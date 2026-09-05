import sqlite3
# Fase 74: REPO_ROOT resuelto por local_env.py (portabilidad).
from local_env import REPO_ROOT

con = sqlite3.connect(str(REPO_ROOT / "data/opsim/baseline_v5.3.1_10yrs.db"))
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("TABLES:", tables)

for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = [r[1] for r in cur.fetchall()]
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    print(f"\n== {t} ({n} rows) ==")
    print(cols[:30])
