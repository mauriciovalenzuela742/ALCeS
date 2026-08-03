"""
converter.py — Lectura PHOT.FITS + HEAD.FITS → phot_df / head_df (en memoria).

Lee los archivos FITS que genera snlc_sim y los materializa como DataFrames
pandas SOLO en memoria, para alimentar el QC de la Capa 4. Los .FITS de
SNANA ya son la fuente de verdad del dataset — este pipeline no escribe
CSV/Parquet a disco (decision explicita: evita duplicar los datos y
mantiene un unico formato canonico, el que ya usan los pasos rio abajo).

Columnas principales conservadas:
    head_df: SNID, SNTYPE, RA, DEC, REDSHIFT_HELIO, REDSHIFT_CMB,
             MWEBV, PEAKMJD, NOBS, ...
    phot_df: SNID, MJD, FLT, FLUXCAL, FLUXCALERR, MAG, MAGERR,
             PHOTFLAG, ...

Dependencias FITS (lazy):
    - intenta `fitsio` (mas rapido, lo prefiere SNANA)
    - fallback a `astropy.io.fits`
    - si ninguno esta disponible, levanta ImportError claro
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ lectura FITS
def _to_native_byteorder(arr: np.ndarray) -> np.ndarray:
    """FITS es big-endian por estandar; numpy/pandas asumen nativo (little-endian
    en x86-64) para varias operaciones (p.ej. np.histogram) — sin esto fallan con
    'Big-endian buffer not supported on little-endian compiler'."""
    if arr.dtype.byteorder not in ("=", "|"):
        return arr.byteswap().view(arr.dtype.newbyteorder("="))
    return arr


def _read_fits_table(path: Path, hdu: int = 1) -> pd.DataFrame:
    """Lee un HDU de un FITS como DataFrame, intentando fitsio luego astropy."""
    try:
        import fitsio
        data = fitsio.read(str(path), ext=hdu)
        return pd.DataFrame({col: _to_native_byteorder(data[col]) for col in data.dtype.names})
    except ImportError:
        pass
    try:
        from astropy.io import fits
        with fits.open(str(path), memmap=True) as hdul:
            arr = np.array(hdul[hdu].data)
            return pd.DataFrame({name: _to_native_byteorder(arr[name]) for name in arr.dtype.names})
    except ImportError:
        raise ImportError(
            "Se necesita fitsio o astropy para leer FITS. "
            "Instala con:  pip install fitsio  o  pip install astropy"
        )


def _clean_bytes(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas bytes (b'x') a str — comun en FITS."""
    for col in df.columns:
        if df[col].dtype == object:
            try:
                sample = df[col].dropna().iloc[0] if len(df[col].dropna()) else None
                if isinstance(sample, (bytes, np.bytes_)):
                    df[col] = df[col].apply(
                        lambda x: x.decode("utf-8", errors="replace").strip()
                        if isinstance(x, (bytes, np.bytes_)) else x
                    )
            except Exception:
                pass
    return df


# ------------------------------------------------------------------ conversion
def read_head(path: str | Path) -> pd.DataFrame:
    """Lee un HEAD.FITS y devuelve head_df limpio."""
    df = _read_fits_table(Path(path))
    df = _clean_bytes(df)
    if "SNID" in df.columns:
        df["SNID"] = df["SNID"].astype(str).str.strip()
    return df


def read_phot(path: str | Path) -> pd.DataFrame:
    """Lee un PHOT.FITS y devuelve phot_df limpio.

    La columna de banda es BAND en esta version de SNANA (11.05p), no FLT
    (nombre mas antiguo/generico del manual) — se normaliza a FLT aqui para
    que el resto del pipeline (QC) tenga un nombre estable sin importar la
    version de SNANA.
    """
    df = _read_fits_table(Path(path))
    df = _clean_bytes(df)
    if "BAND" in df.columns and "FLT" not in df.columns:
        df = df.rename(columns={"BAND": "FLT"})
    if "FLT" in df.columns:
        df["FLT"] = df["FLT"].astype(str).str.strip()
    if "MAG" not in df.columns and {"FLUXCAL", "ZEROPT"} <= set(df.columns):
        flux = df["FLUXCAL"]
        positive = flux > 0
        df["MAG"] = np.where(positive, df["ZEROPT"] - 2.5 * np.log10(flux.where(positive)), np.nan)
        if "FLUXCALERR" in df.columns:
            df["MAGERR"] = np.where(
                positive, (2.5 / np.log(10)) * (df["FLUXCALERR"] / flux.where(positive)), np.nan
            )
    return df


def link_phot_head(phot_df: pd.DataFrame, head_df: pd.DataFrame) -> pd.DataFrame:
    """Asocia cada fila de phot con su SNID usando PTROBS_MIN/MAX de head."""
    if "PTROBS_MIN" in head_df.columns and "PTROBS_MAX" in head_df.columns:
        snids = []
        for _, row in head_df.iterrows():
            lo, hi = int(row["PTROBS_MIN"]) - 1, int(row["PTROBS_MAX"])  # 1-indexed
            snids.extend([row["SNID"]] * (hi - lo))
        if len(snids) == len(phot_df):
            phot_df = phot_df.copy()
            phot_df["SNID"] = snids
    return phot_df


# ------------------------------------------------------------------ lectura
def read_genversion(genversion_dir: str | Path) -> dict:
    """Lee todos los FITS de un directorio GENVERSION a DataFrames en memoria.

    Busca pares *HEAD.FITS.gz / *PHOT.FITS.gz (o sin .gz). Si hay varios
    (split por jobid), los concatena. No escribe nada a disco — los DataFrames
    devueltos se usan directo para QC (ver pipeline.postprocess).

    Returns dict con estadisticas y los DataFrames (head_df, phot_df).
    """
    gdir = Path(genversion_dir)

    # buscar FITS
    head_files = sorted(gdir.glob("*HEAD.FITS*"))
    phot_files = sorted(gdir.glob("*PHOT.FITS*"))
    if not head_files:
        raise FileNotFoundError(f"no se encontraron HEAD.FITS en {gdir}")
    if not phot_files:
        raise FileNotFoundError(f"no se encontraron PHOT.FITS en {gdir}")

    heads, phots = [], []
    for hf in head_files:
        heads.append(read_head(hf))
    for pf in phot_files:
        phots.append(read_phot(pf))

    head_df = pd.concat(heads, ignore_index=True)
    phot_df = pd.concat(phots, ignore_index=True)

    # link si es posible
    if "SNID" not in phot_df.columns and len(head_files) == 1:
        phot_df = link_phot_head(phot_df, head_df)

    return {
        "genversion_dir": str(gdir),
        "n_objects": len(head_df),
        "n_observations": len(phot_df),
        "columns_head": list(head_df.columns),
        "columns_phot": list(phot_df.columns),
        "fits_files": {
            "head": [str(f) for f in head_files],
            "phot": [str(f) for f in phot_files],
        },
        "head_df": head_df,
        "phot_df": phot_df,
    }
