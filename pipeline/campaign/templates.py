"""
templates.py — Generador de archivos .INPUT de simulacion SNANA.

REESCRITO tras confirmar el formato real contra un .input PROBADO y exitoso
del propio usuario (DATASIM_LSST/DDF/input_files_v6/AGN/AGN_20251020.input,
70+ corridas reales en NLHPC). Hallazgos que corrigen supuestos anteriores:

    - La clave de include es INPUT_INCLUDE_FILE (NO "INPUT_FILE_INCLUDE" que
      se uso antes — esa es la MENOS documentada; INPUT_INCLUDE_FILE aparece
      5+ veces en el manual como la forma canonica).
    - NGENTOT_LC (numero total simulado), NO "NGEN_LC" (numero que pasa cortes
      — semantica distinta, no intercambiable).
    - Faltan por completo en la version anterior: GENSOURCE, KCOR_FILE,
      SEARCHEFF_PIPELINE_FILE (ademas de LOGIC_FILE), APPLY_SEARCHEFF_OPT,
      GENFILTERS (no "FILTERS"/"SURVEY"/"TELESCOPE", que no son claves reales
      de sim-input), SOLID_ANGLE, GENRANGE_MJD, GENSIGMA_SEARCH_PEAKMJD,
      OPT_MWEBV/OPT_MWCOLORLAW, SMEARFLAG_FLUX/ZEROPT, SIMLIB_MAXRANSTART,
      SIMLIB_MSKOPT, SIMGEN_DUMPALL.

Arquitectura (se mantiene el concepto, solo cambian las claves):

    include_survey_{STRATEGY}_{RUN}.INPUT
        → todo lo que es igual para cualquier clase con ese run+estrategia:
          SIMLIB_FILE, KCOR_FILE, SEARCHEFF_*, GENFILTERS, GENRANGE_MJD/PEAKMJD,
          SMEARFLAG_*, OPT_MWEBV/COLORLAW, SIMGEN_DUMPALL.

    include_model_{CLASE}.INPUT
        → passthrough (INPUT_INCLUDE_FILE) a un SIMGEN_INCLUDE_*.INPUT curado,
          o modo SCRATCH best-effort si no existe uno.

    sim_{CLASE}_{STRATEGY}_{RUN}.INPUT  (el raiz)
        → GENVERSION, GENSOURCE, NGENTOT_LC, RANSEED
          + INPUT_INCLUDE_FILE de survey
          + INPUT_INCLUDE_FILE de model
"""

from __future__ import annotations

from dataclasses import dataclass

# Clave de ruta de SNANA por GENMODEL, para el modo SCRATCH (fallback).
_PATH_KEY_BY_GENMODEL = {
    "NON1ASED": "PATH_NON1ASED",
    "SIMSED": "PATH_SIMSED",
}

# Variables del SIMGEN_DUMPALL, tal como en el archivo real probado.
_DUMP_VARS = (
    "CID LIBID  SIM_SEARCHEFF_MASK  GENTYPE  NON1A_INDEX\n"
    "   ZCMB ZHELIO ZCMB_SMEAR RA DEC MWEBV\n"
    "   GALID GALZPHOT GALZPHOTERR  GALSNSEP GALSNDDLR  RV AV\n"
    "   MU LENSDMU PEAKMJD MJD_DETECT_FIRST MJD_DETECT_LAST DTSEASON_PEAK\n"
    "   PEAKMAG_u PEAKMAG_g PEAKMAG_r PEAKMAG_i PEAKMAG_z PEAKMAG_Y\n"
    "   SNRMAX SNRMAX2 SNRMAX3 NOBS NOBS_SATURATE"
)


@dataclass
class SurveyContext:
    run: str                    # nombre logico del registro (Capa 0)
    strategy: str                # WFD o DDF
    simlib_path: str             # ruta ABSOLUTA al .SIMLIB
    mjd_min: float
    mjd_max: float
    peakmjd_min: float
    peakmjd_max: float
    kcor_file: str
    searcheff_pipeline_file: str
    searcheff_pipeline_logic_file: str
    genfilters: str = "ugrizY"
    solid_angle: float = 0.0
    simlib_maxranstart: int = 1000
    simlib_mskopt: int = 128
    gensigma_search_peakmjd: float = 1.0
    opt_mwebv: int = 1
    opt_mwcolorlaw: int = 99
    smearflag_flux: int = 1
    smearflag_zeropt: int = 1
    format_mask: int = 32       # 32=FITS ; +16=random CID (ver --HELP SIM)
    dump_all: bool = True


@dataclass
class ModelSpec:
    key: str
    # Modo EXISTING (preferido): ruta absoluta a un SIMGEN_INCLUDE_*.INPUT
    # ya curado. Si se da, el resto de los campos SCRATCH se ignoran.
    simgen_include: str | None = None
    # Modo SCRATCH (fallback): se ignoran si simgen_include esta definido.
    genmodel: str = ""
    genmodel_path: str = ""
    gentype: int = 0
    dndz: str = ""
    zrange: tuple[float, float] = (0.0, 1.0)
    trest: tuple[float, float] = (-20.0, 100.0)
    minslope_extrap_late: float | None = None
    ngen: int = 10000
    # Inyectados por el compilador SOLO si el simgen_include curado (modo
    # EXISTING) no los define ya el mismo — algunos modelos LCLIB (p.ej. los
    # ELASTiCC en elastic/model_config/) traen su propio OPT_MWEBV/OPT_MWCOLORLAW
    # (su MW-extinction ya viene aplicada en el template) y SNANA aborta con
    # "exceeds limit=1" si la clave queda duplicada entre el survey include y
    # el modelo. None = no inyectar (el survey include ya no los escribe).
    opt_mwebv: int | None = None
    opt_mwcolorlaw: int | None = None


def render_survey_include(ctx: SurveyContext) -> str:
    """Genera el include_survey_{STRATEGY}_{RUN}.INPUT (claves reales confirmadas)."""
    lines = [
        f"# Auto-generated survey include: {ctx.strategy} / {ctx.run}",
        f"# Modifica este archivo para cambiar cadencia/profundidad sin tocar modelos.",
        f"",
        f"GENSOURCE:  RANDOM",
        f"",
        f"SIMLIB_FILE: {ctx.simlib_path}",
        f"SIMLIB_MAXRANSTART: {ctx.simlib_maxranstart}",
        f"SIMLIB_MSKOPT:   {ctx.simlib_mskopt}",
        f"",
        f"KCOR_FILE: {ctx.kcor_file}",
        f"SEARCHEFF_PIPELINE_FILE: {ctx.searcheff_pipeline_file}",
        f"SEARCHEFF_PIPELINE_LOGIC_FILE: {ctx.searcheff_pipeline_logic_file}",
        f"APPLY_SEARCHEFF_OPT: 1",
        f"",
        f"GENFILTERS:   {ctx.genfilters}",
        f"SOLID_ANGLE:  {ctx.solid_angle}",
        f"",
        f"GENRANGE_MJD:      {ctx.mjd_min:.0f} {ctx.mjd_max:.0f}    # ventana de observacion (SIMLIB)",
        f"GENRANGE_PEAKMJD:  {ctx.peakmjd_min:.0f} {ctx.peakmjd_max:.0f}   # mas ancho, para capturar el ascenso",
        f"",
        f"GENSIGMA_SEARCH_PEAKMJD:  {ctx.gensigma_search_peakmjd}     # sigma-smearing (dias)",
        f"",
        f"# OPT_MWEBV/OPT_MWCOLORLAW NO van aqui — se inyectan por clase en el",
        f"# include_model_ (ver render_model_include) porque algunos modelos",
        f"# LCLIB ya traen su propio valor y SNANA aborta con clave duplicada",
        f"# si tambien se escribe a nivel de survey.",
        f"",
        f"# smear flags: 0=off, 1=on",
        f"SMEARFLAG_FLUX:    {ctx.smearflag_flux}  # photo-stat smearing de senhal, cielo, etc",
        f"SMEARFLAG_ZEROPT:  {ctx.smearflag_zeropt}  # smear del zero-point con zptsig",
        f"",
        f"FORMAT_MASK:   {ctx.format_mask}  # 2=TEXT  32=FITS  (+16=random CID)",
        f"",
    ]
    if ctx.dump_all:
        lines.append(f"SIMGEN_DUMPALL:  35")
        lines.append(f"   {_DUMP_VARS}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_model_include(m: ModelSpec) -> str:
    """Genera el include_model_{CLASE}.INPUT (modo EXISTING o SCRATCH)."""
    if m.simgen_include:
        # Modo EXISTING: passthrough a un archivo curado real. No reinventamos
        # DNDZ/pesos/rangos — esos ya estan afinados en el archivo referenciado.
        lines = [
            f"# Auto-generated model include: {m.key}",
            f"# Referencia directa a un SIMGEN_INCLUDE curado (no generado por este pipeline).",
            f"# Para cambiar el modelo, edita el archivo original o el path en models.yaml.",
            f"",
            f"INPUT_INCLUDE_FILE:  {m.simgen_include}",
        ]
        # OPT_MWEBV/OPT_MWCOLORLAW: el compilador ya verifico que el archivo
        # curado NO los define — si m.opt_mwebv es None es porque el propio
        # archivo ya trae el suyo (evita 'exceeds limit=1' de SNANA).
        if m.opt_mwebv is not None:
            lines.append(f"OPT_MWEBV:  {m.opt_mwebv}")
        if m.opt_mwcolorlaw is not None:
            lines.append(f"OPT_MWCOLORLAW:  {m.opt_mwcolorlaw}")
        lines.append("")
        return "\n".join(lines)

    # Modo SCRATCH: best-effort, verificar contra documentacion SNANA.
    lines = [
        f"# Auto-generated model include: {m.key}  (modo SCRATCH — sin SIMGEN_INCLUDE curado)",
        f"# Modifica este archivo para cambiar el modelo sin tocar el survey.",
        f"",
        f"GENMODEL:  {m.genmodel}",
    ]
    path_key = _PATH_KEY_BY_GENMODEL.get(m.genmodel)
    if m.genmodel_path and path_key:
        lines.append(f"{path_key}:  {m.genmodel_path}")
    elif m.genmodel_path:
        lines.append(f"# ADVERTENCIA: no se conoce la clave de PATH para GENMODEL={m.genmodel!r};"
                     f" agregar a _PATH_KEY_BY_GENMODEL en templates.py y verificar.")
        lines.append(f"# PATH (sin confirmar):  {m.genmodel_path}")
    if m.minslope_extrap_late is not None:
        lines.append(f"MINSLOPE_EXTRAPMAG_LATE:  {m.minslope_extrap_late}")
    lines += [
        f"",
        f"GENTYPE:   {m.gentype}",
        f"SNTYPE:    {m.gentype}",
        f"",
        f"DNDZ:  {m.dndz}",
        f"GENRANGE_REDSHIFT:  {m.zrange[0]:.3f}  {m.zrange[1]:.3f}",
        f"GENRANGE_TREST:     {m.trest[0]:.1f}  {m.trest[1]:.1f}",
        f"",
    ]
    if m.opt_mwebv is not None:
        lines.append(f"OPT_MWEBV:  {m.opt_mwebv}")
    if m.opt_mwcolorlaw is not None:
        lines.append(f"OPT_MWCOLORLAW:  {m.opt_mwcolorlaw}")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_root_input(
    genversion: str,
    survey_include: str,
    model_include: str,
    ngen: int,
    ranseed: int,
) -> str:
    """Genera el .INPUT raiz: GENVERSION + NGENTOT_LC + 2x INPUT_INCLUDE_FILE."""
    lines = [
        f"# Auto-generated root .INPUT:  {genversion}",
        f"#",
        f"# NO EDITAR: regenerar con  compile_campaign.py",
        f"# Los cambios van en campaign.yaml, models.yaml, o en los includes.",
        f"",
        f"NGENTOT_LC: {ngen}",
        f"",
        f"GENVERSION: {genversion}",
        f"",
        f"RANSEED: {ranseed}",
        f"",
        f"INPUT_INCLUDE_FILE: {survey_include}",
        f"INPUT_INCLUDE_FILE: {model_include}",
        f"",
    ]
    return "\n".join(lines) + "\n"
