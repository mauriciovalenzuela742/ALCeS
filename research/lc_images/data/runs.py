"""Carga de corridas de ALCeS y features por objeto para los experimentos.

Lee el mismo layout que exploration/lightcurvelynx/kn_confusion_diag.py (`<class_key>_seed<N>/`
con head_df.parquet y phot_df.parquet) y usa sus mismas funciones, importadas sin copiarlas:
`load_runs` (solo objetos DETECTED) y `object_features` (n_det_nights, colores, pendiente...).
Asi los resultados son comparables con el diagnostico KN. Nada de aqui escribe en exploration/.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
LCL = REPO / "exploration" / "lightcurvelynx"
sys.path.insert(0, str(LCL))
import kn_confusion_diag as diag  # noqa: E402

# Rasgos de curva del diagnostico KN (run_observed); REDSHIFT_HELIO se agrega aparte.
LC_COLS = ["n_det", "n_det_nights", "n_snr3", "n_det_bands", "det_span_d", "max_snr",
           "mag_brightest", "decline_mag_per_d"] + [f"obs_{a}-{b}" for a, b in diag.COLOR_PAIRS]
# Mismos bins de noches con deteccion que accuracy_by_n_det del diagnostico.
NIGHT_BINS = [0, 1, 2, 3, 5, 1e9]
NIGHT_LABELS = ["1", "2", "3", "4-5", "6+"]


def load(runs_dir: Path, classes: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """head y phot de los objetos detectados. Exige TEMPLATE_INDEX (Fase 98 o posterior)."""
    head, phot = diag.load_runs(Path(runs_dir))
    if classes:
        head = head[head["class_key"].isin(classes)]
        phot = phot[phot["run"].isin(head["run"].unique())]
    if "TEMPLATE_INDEX" not in head:
        raise SystemExit("head_df sin TEMPLATE_INDEX: las corridas son anteriores a la Fase 98. "
                         "Hay que regenerarlas (ver README, contrato de datos).")
    return head.reset_index(drop=True), phot


def features(head: pd.DataFrame, phot: pd.DataFrame) -> pd.DataFrame:
    """Una fila por objeto detectado: id, clase, grupo de template, z y rasgos de curva."""
    rows = []
    for (run, snid), p in phot.groupby(["run", "SNID"], sort=False):
        f = diag.object_features(p.sort_values("MJD"))
        f["run"], f["SNID"] = run, snid
        rows.append(f)
    df = head[["run", "SNID", "class_key", "REDSHIFT_HELIO", "TEMPLATE_INDEX"]].merge(
        pd.DataFrame(rows), on=["run", "SNID"], how="left")
    df["group"] = template_groups(df)
    df["night_bin"] = pd.cut(df["n_det_nights"], NIGHT_BINS, labels=NIGHT_LABELS).astype(str)
    return df


def template_groups(df: pd.DataFrame) -> np.ndarray:
    """Grupo para particionar: clase + TEMPLATE_INDEX en clases SIMSED.

    En clases sin template (SALT2, NON1ASED: TEMPLATE_INDEX vacio) cada objeto es su propio
    grupo, o sea que la particion agrupada se reduce a la aleatoria; `has_template` lo marca.
    """
    t = pd.to_numeric(df["TEMPLATE_INDEX"], errors="coerce")
    own = df["run"].astype(str) + ":" + df["SNID"].astype(str)
    grp = df["class_key"].astype(str) + ":T" + t.astype("Int64").astype(str)
    return np.where(t.notna(), grp, "obj:" + own)


def input_hashes(runs_dir: Path, runs: list[str]) -> dict[str, str]:
    """SHA256 de cada parquet usado (contrato del protocolo: se guarda con cada corrida)."""
    out = {}
    for run in sorted(runs):
        for name in ("head_df.parquet", "phot_df.parquet"):
            path = Path(runs_dir) / run / name
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[f"{run}/{name}"] = h.hexdigest()
    return out
