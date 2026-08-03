"""
hprep.py — Representacion Healpix, muestreo de campos y consulta de obs por campo.

Porta compute_hp_rep / sample_survey / get_survey_obs del notebook. `compute_hp_rep`
importa healpy de forma perezosa (solo se necesita al construir contra un .db real);
`sample_survey` y la construccion del BallTree son puro pandas/sklearn y si se pueden
probar sin healpy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ensure_radian_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza columnas _ra/_dec en radianes (OpSimSummary las agrega; por si no)."""
    if "_ra" not in df.columns:
        df = df.copy()
        df["_ra"] = np.radians(df["fieldRA"].to_numpy())
        df["_dec"] = np.radians(df["fieldDec"].to_numpy())
    return df


def build_tree(df: pd.DataFrame):
    """BallTree haversine sobre (_dec, _ra) en radianes."""
    from sklearn.neighbors import BallTree
    df = ensure_radian_coords(df)
    return BallTree(df[["_dec", "_ra"]].to_numpy(), leaf_size=50, metric="haversine")


def compute_hp_rep(df, tree, nside: int, min_visits: int,
                   max_visits: int | None = None, radius_deg: float = 1.75) -> pd.DataFrame:
    """Representacion Healpix del survey con n_visits por pixel (usa healpy)."""
    import healpy as hp
    ipix = np.arange(hp.nside2npix(nside))
    hp_ra, hp_dec = np.radians(hp.pix2ang(nside, ipix, lonlat=True))
    rep = pd.DataFrame(dict(ipix=ipix, hp_ra=hp_ra, hp_dec=hp_dec))
    rep["n_visits"] = tree.query_radius(
        rep[["hp_dec", "hp_ra"]].to_numpy(), r=np.radians(radius_deg), count_only=True,
    )
    mask = rep["n_visits"] >= min_visits
    if max_visits is not None:
        mask &= rep["n_visits"] <= max_visits
    rep = rep[mask].set_index("ipix")
    rep.attrs["nside"] = nside
    rep.attrs["survey_area_deg"] = hp.nside2pixarea(nside, degrees=True) * len(rep)
    return rep


def sample_survey(hp_rep: pd.DataFrame, n_fields: int, seed: int = 42) -> pd.DataFrame:
    """Muestrea n_fields campos del hp_rep (puro pandas, reproducible por seed)."""
    if n_fields > len(hp_rep):
        raise ValueError(f"n_fields ({n_fields}) > campos disponibles ({len(hp_rep)})")
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    out = hp_rep.sample(n=n_fields, replace=False, random_state=rng).reset_index()
    out.attrs = dict(hp_rep.attrs)
    out.attrs["n_fields"] = n_fields
    return out


def field_obs_indices(tree, hp_ra: np.ndarray, hp_dec: np.ndarray, radius_deg: float = 1.75):
    """Para cada campo (ra,dec en radianes) devuelve indices de obs dentro del radio."""
    return tree.query_radius(
        np.array([hp_dec, hp_ra]).T, r=np.radians(radius_deg),
        count_only=False, return_distance=False,
    )
