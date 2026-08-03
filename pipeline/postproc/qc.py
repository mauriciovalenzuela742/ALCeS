"""
qc.py — Control de calidad automatico (los 4 graficos del poster).

Cada funcion recibe head_df / phot_df y genera un grafico guardado en disco.
Usa matplotlib con el tema nocturno LSST y los colores de banda ugrizY.

    1. redshift_distribution    — z simulado vs z detectado, por clase
    2. magnitude_histograms     — histograma de mag A-B por banda
    3. detection_distribution   — nro de detecciones por objeto
    4. sample_lightcurves       — muestra aleatoria de curvas de luz

Ademas:
    5. run_all_qc               — corre los 4 y devuelve las rutas
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# lazy matplotlib (no se importa a nivel de modulo para no forzar backend)
_MPL_LOADED = False

# colores LSST por banda
BAND_COLORS = {
    "u": "#8a6df0", "g": "#38b6a0", "r": "#e0b23c",
    "i": "#e07b3c", "z": "#d9525f", "Y": "#a83a55", "y": "#a83a55",
}
_BG = "#070a18"
_PANEL = "#111834"
_LINE = "#24305c"
_INK = "#eaeefb"
_INK_DIM = "#9aa4cc"
_ACCENT = "#5ed6cd"


def _setup_style():
    global _MPL_LOADED
    if _MPL_LOADED:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": _BG,
        "axes.facecolor": _PANEL,
        "axes.edgecolor": _LINE,
        "axes.labelcolor": _INK_DIM,
        "text.color": _INK,
        "xtick.color": _INK_DIM,
        "ytick.color": _INK_DIM,
        "grid.color": _LINE,
        "grid.alpha": 0.5,
        "font.family": "sans-serif",
        "font.size": 10,
        "legend.facecolor": _PANEL,
        "legend.edgecolor": _LINE,
        "legend.fontsize": 8,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.facecolor": _BG,
    })
    _MPL_LOADED = True


# ------------------------------------------------------------------ 1. redshift
def redshift_distribution(
    head_df: pd.DataFrame,
    out_path: str | Path,
    *,
    z_sim_col: str = "REDSHIFT_HELIO",
    z_det_col: str = "REDSHIFT_CMB",
    type_col: str = "SNTYPE",
    bins: int = 40,
) -> Path:
    """Distribución de redshift simulado vs detectado (coloreado por clase)."""
    _setup_style()
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)

    for ax, col, label in zip(axes, [z_sim_col, z_det_col], ["z simulado", "z detectado"]):
        if col not in head_df.columns:
            ax.set_title(f"{label} (columna ausente)")
            continue
        types = sorted(head_df[type_col].unique()) if type_col in head_df.columns else [0]
        cmap = plt.cm.viridis(np.linspace(0.2, 0.9, len(types)))
        for t, c in zip(types, cmap):
            sub = head_df[head_df[type_col] == t][col] if type_col in head_df.columns else head_df[col]
            sub = sub.dropna()
            ax.hist(sub, bins=bins, alpha=0.65, color=c, label=f"tipo {t}", histtype="stepfilled")
        ax.set_xlabel(label)
        ax.set_title(label, fontsize=11)
        ax.legend(loc="upper right", fontsize=7)
    axes[0].set_ylabel("N objetos")
    fig.suptitle("Distribución de redshift", color=_ACCENT, fontsize=13, y=1.02)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# ------------------------------------------------------------------ 2. magnitudes
def magnitude_histograms(
    phot_df: pd.DataFrame,
    out_path: str | Path,
    *,
    mag_col: str = "MAG",
    band_col: str = "FLT",
    bands: list[str] | None = None,
    bins: int = 50,
) -> Path:
    """Histograma de magnitud A-B por banda."""
    _setup_style()
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    bands = bands or ["u", "g", "r", "i", "z", "Y"]
    present = [b for b in bands if b in phot_df[band_col].unique()]
    if not present:
        # intentar sin case sensitivity
        phot_df = phot_df.copy()
        phot_df[band_col] = phot_df[band_col].str.strip()
        present = [b for b in bands if b in phot_df[band_col].unique()]

    ncols = min(3, len(present)) or 1
    nrows = max(1, (len(present) + ncols - 1) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3.5 * nrows), squeeze=False)

    for idx, b in enumerate(present):
        ax = axes[idx // ncols][idx % ncols]
        sub = phot_df[phot_df[band_col] == b][mag_col].dropna()
        sub = sub[(sub > 15) & (sub < 30)]  # rango razonable
        ax.hist(sub, bins=bins, color=BAND_COLORS.get(b, _ACCENT), alpha=0.8, histtype="stepfilled")
        ax.set_xlabel("mag AB")
        ax.set_title(f"banda {b}  (N={len(sub):,})", fontsize=10)
        ax.grid(True, alpha=0.3)
    # ocultar ejes sobrantes
    for idx in range(len(present), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)
    fig.suptitle("Histogramas de magnitud A-B", color=_ACCENT, fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# ------------------------------------------------------------------ 3. detecciones
def detection_distribution(
    phot_df: pd.DataFrame,
    out_path: str | Path,
    *,
    snid_col: str = "SNID",
    bins: int = 50,
) -> Path:
    """Distribución del número de detecciones (épocas) por objeto."""
    _setup_style()
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    if snid_col not in phot_df.columns:
        # fallback: usar head_df.NOBS si se pasa como phot
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"columna '{snid_col}' no encontrada", transform=ax.transAxes,
                ha="center", color=_INK_DIM)
        fig.savefig(out_path); plt.close(fig); return out_path

    counts = phot_df.groupby(snid_col).size()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(counts, bins=bins, color=_ACCENT, alpha=0.85, histtype="stepfilled", edgecolor=_LINE)
    ax.axvline(counts.median(), color="#e0b23c", ls="--", lw=1.2, label=f"mediana = {counts.median():.0f}")
    ax.set_xlabel("Nº de épocas por objeto")
    ax.set_ylabel("N objetos")
    ax.set_title("Distribución de detecciones", color=_ACCENT, fontsize=13)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# ------------------------------------------------------------------ 4. curvas de muestra
def sample_lightcurves(
    phot_df: pd.DataFrame,
    head_df: pd.DataFrame,
    out_path: str | Path,
    *,
    n_samples: int = 6,
    snid_col: str = "SNID",
    mjd_col: str = "MJD",
    flux_col: str = "FLUXCAL",
    fluxerr_col: str = "FLUXCALERR",
    band_col: str = "FLT",
    seed: int = 42,
) -> Path:
    """Muestra aleatoria de curvas de luz (flujo vs MJD, multibanda)."""
    _setup_style()
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    if snid_col not in phot_df.columns:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, f"columna '{snid_col}' no encontrada", transform=ax.transAxes,
                ha="center", color=_INK_DIM)
        fig.savefig(out_path); plt.close(fig); return out_path

    rng = np.random.default_rng(seed)
    all_snids = phot_df[snid_col].unique()
    n = min(n_samples, len(all_snids))
    chosen = rng.choice(all_snids, size=n, replace=False)

    ncols = min(3, n)
    nrows = max(1, (n + ncols - 1) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows), squeeze=False)

    for idx, snid in enumerate(chosen):
        ax = axes[idx // ncols][idx % ncols]
        sub = phot_df[phot_df[snid_col] == snid].copy()
        # tipo del objeto
        label_extra = ""
        if snid_col in head_df.columns and "SNTYPE" in head_df.columns:
            match = head_df[head_df[snid_col] == snid]
            if len(match):
                label_extra = f"  tipo={match.iloc[0]['SNTYPE']}"

        for b in sub[band_col].unique():
            bsub = sub[sub[band_col] == b].sort_values(mjd_col)
            color = BAND_COLORS.get(b, _INK_DIM)
            ax.errorbar(bsub[mjd_col], bsub[flux_col],
                        yerr=bsub[fluxerr_col] if fluxerr_col in bsub else None,
                        fmt="o", ms=3, color=color, ecolor=color, alpha=0.8,
                        label=b, elinewidth=0.8, capsize=0)
        ax.set_title(f"SNID {snid}{label_extra}", fontsize=9)
        ax.set_xlabel("MJD")
        ax.set_ylabel("FLUXCAL")
        ax.legend(fontsize=7, ncol=3, loc="upper right")
        ax.grid(True, alpha=0.2)

    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)
    fig.suptitle("Curvas de luz de muestra", color=_ACCENT, fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# ------------------------------------------------------------------ run all
def run_all_qc(
    head_df: pd.DataFrame,
    phot_df: pd.DataFrame,
    out_dir: str | Path,
    genversion: str = "",
) -> dict[str, Path]:
    """Corre los 4 QC y devuelve las rutas generadas."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{genversion}_" if genversion else ""

    paths = {}
    paths["redshift"] = redshift_distribution(
        head_df, out_dir / f"{prefix}qc_redshift.png")
    paths["magnitudes"] = magnitude_histograms(
        phot_df, out_dir / f"{prefix}qc_magnitudes.png")
    paths["detections"] = detection_distribution(
        phot_df, out_dir / f"{prefix}qc_detections.png")
    paths["lightcurves"] = sample_lightcurves(
        phot_df, head_df, out_dir / f"{prefix}qc_lightcurves.png")

    return paths
