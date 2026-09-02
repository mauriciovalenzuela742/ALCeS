"""
Fase 68/69 -- panel de curvas de luz al estilo real del notebook oficial de
LightCurveLynx (`verificacion_bugs_lightcurvelynx.ipynb`, seccion 6), compartido
por los 3 scripts de produccion de esta investigacion (`run_simsed_poc.py`,
`run_non1ased_poc.py`, `run_snia_ddf_poc.py`) para que las 19 clases del
dashboard usen el mismo codigo -- no una copia pegada 3 veces.

Reemplaza SOLO el panel "lightcurves" del QC de `pipeline.postproc.qc`
(fondo oscuro, colores generales, pensado para el QC de produccion SNANA) --
los otros 3 graficos (detecciones/magnitudes/redshift) los sigue generando
`pipeline/` sin cambios; este modulo no toca `pipeline/`.
"""
from __future__ import annotations

import numpy as np

# Fase 68: paleta Okabe-Ito (segura para daltonismo), misma que
# verificacion_bugs_lightcurvelynx.ipynb -- reemplaza el colormap generico
# tab10 que usa plot_lightcurves() por defecto (asigna color por ORDEN de
# aparicion del filtro, no por banda). Ambas capitalizaciones de "y" porque
# LightCurveLynx usa internamente minuscula pero varios de estos scripts ya
# normalizan a "Y" en otras partes (columna FLT).
BAND_COLORS = {
    "u": "#56B4E9", "g": "#009E73", "r": "#D55E00",
    "i": "#E69F00", "z": "#CC79A7", "y": "#0072B2", "Y": "#0072B2",
}


def plot_notebook_style_lightcurves(source_model, lc, passband_group, detected_snids,
                                     out_path, class_key: str, strategy: str, n_top: int = 6):
    """Mismo tipo de grafico, con el mismo codigo, que el notebook oficial de
    LightCurveLynx -- no una recreacion aproximada: reusa literalmente
    `plot_lightcurves()` (lightcurvelynx.utils.plotting) y
    `compute_single_noise_free_lightcurve()` (lightcurvelynx.simulate),
    graficando flux_perfect (flujo verdadero, sin ruido) con las barras de
    error reales superpuestas a la curva continua del modelo, con la paleta
    BAND_COLORS de arriba.

    Fase 69: "mas luminosas" = mayor flujo pico verdadero
    (max(|flux_perfect|), no observado/con ruido) entre los objetos ya
    marcados como detectados por SEARCHEFF -- pedido explicito del usuario
    (antes: mayor S/N mediana, ver Fase 68). n_top=6 (antes 5) para que
    encaje en una grilla 2x3 sin panel vacio.
    """
    import matplotlib.pyplot as plt
    from lightcurvelynx.graph_state import GraphState
    from lightcurvelynx.simulate import compute_single_noise_free_lightcurve
    from lightcurvelynx.utils.plotting import plot_lightcurves

    # pipeline.postproc.qc._setup_style() (ya corrido arriba, en la misma
    # llamada a main()) muta plt.rcParams GLOBALMENTE al tema nocturno de
    # produccion -- persiste para el resto del proceso de Python. Sin este
    # reset, este grafico heredaria fondo oscuro/colores de esa mutacion en
    # vez del fondo blanco real del notebook oficial (no toca pipeline/, solo
    # revierte el estado global de matplotlib para ESTE grafico).
    plt.rcdefaults()

    detected_ids = set(detected_snids)
    candidates = []
    for idx in range(len(lc)):
        row = lc.iloc[idx]
        if str(int(row["id"])) not in detected_ids:
            continue
        current_lc = row["lightcurve"]
        if current_lc is None or len(current_lc) < 2:
            continue
        lc_flux = np.asarray(current_lc["flux_perfect"], dtype=float)
        if not np.isfinite(lc_flux).any():
            continue
        peak_flux = float(np.nanmax(np.abs(lc_flux)))
        candidates.append((idx, len(current_lc), peak_flux))
    candidates.sort(key=lambda t: t[2], reverse=True)
    top = candidates[:n_top]
    if not top:
        return False

    ncols = min(3, len(top))
    nrows = int(np.ceil(len(top) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(7.5 * ncols, 5 * nrows), squeeze=False)
    flat_axes = axes.ravel()

    for rank, (idx, nobs, peak_flux) in enumerate(top):
        row = lc.iloc[idx]
        current_lc = row["lightcurve"]
        lc_filters = np.asarray(current_lc["filter"], dtype=str)
        lc_mjd = np.asarray(current_lc["mjd"], dtype=float)
        lc_flux = np.asarray(current_lc["flux_perfect"], dtype=float)
        lc_fluxerr = np.asarray(current_lc["fluxerr"], dtype=float)

        noise_free = compute_single_noise_free_lightcurve(
            source_model, GraphState.from_dict(row["params"]), passband_group,
            rest_frame_phase_min=-50.0, rest_frame_phase_max=100.0, rest_frame_phase_step=0.5,
        )
        plot_lightcurves(
            fluxes=lc_flux, times=lc_mjd, fluxerrs=lc_fluxerr, filters=lc_filters,
            underlying_model=noise_free, colormap=BAND_COLORS, ax=flat_axes[rank],
            title=(f"#{rank + 1}/{len(top)} SNID {int(row['id'])} (NOBS={nobs}, "
                   f"flujo pico={peak_flux:,.0f} nJy, z={row['z']:.3f})"),
        )

    for extra_ax in flat_axes[len(top):]:
        extra_ax.set_visible(False)

    fig.suptitle(f"Curvas de luz mas luminosas -- {class_key} ({strategy})", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return True
