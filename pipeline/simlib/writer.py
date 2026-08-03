"""
writer.py — Escritura de archivos SIMLIB en formato SNANA.

Auto-contenido: implementa su propia `dataline` (no depende de
opsimsummaryv2.utils), garantizando el layout estandar que lee el visualizer:

    S: MJD  ID*NEXPOSE  FLT  GAIN  NOISE  SKYSIG  PSF1 PSF2 PSF2/1  ZPTAVG ZPTERR  MAG

Reproduce get_SIMLIB_doc / header / LIBheader / LIBdata / LIBfooter / footer
del notebook, parametrizados por SimlibConfig.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


@dataclass
class WriterParams:
    survey: str = "LSST"
    filters: str = "ugrizY"
    telescope: str = "LSST"
    pixsize: float = 0.2
    ccd_gain: float = 1.0
    ccd_noise: float = 0.25
    zpt_err: float = 0.005
    nexpose: int = 1                 # v5.x: exposicion unica (sin snaps)
    saturation_flag: int = 1024
    npe_saturate: int = 100000
    author: str = "pipeline"


def dataline(expmjd: float, obsid, band: str, skysig: float, psf: float,
             zpt: float, p: WriterParams) -> str:
    """Una linea de observacion 'S:' en el layout SNANA estandar."""
    b = "Y" if band == "y" else band
    return (
        f"S: {expmjd:.4f} {int(obsid)}*{p.nexpose} {b} "
        f"{p.ccd_gain:.2f} {p.ccd_noise:.2f} {skysig:.2f} "
        f"{psf:.3f} 0.000 0.000 {zpt:.3f} {p.zpt_err:.3f} -99.000"
    )


def simlib_doc(opsim_file: str, minmjd: float, maxmjd: float,
               total_area_deg: float, p: WriterParams) -> str:
    date = _dt.datetime.now().strftime("%Y-%m")
    return (
        "DOCUMENTATION:\n"
        f"    PURPOSE: simulate LSST based on opsim {opsim_file}\n"
        "    INTENT:   Nominal\n"
        "    USAGE_KEY: SIMLIB_FILE\n"
        "    USAGE_CODE: snlc_sim.exe\n"
        "    NOTES:\n"
        f"        PARAMS MINMJD: {minmjd:.4f}\n"
        f"        PARAMS MAXMJD: {maxmjd:.4f}\n"
        f"        PARAMS TOTAL_AREA: {total_area_deg:.3f}\n"
        "    VERSIONS:\n"
        f"    - DATE : {date}\n"
        f"    AUTHORS : {p.author}, pipeline.simlib\n"
        "DOCUMENTATION_END:\n"
    )


def simlib_header(nlibid: int, p: WriterParams, comments: str = "") -> str:
    return (
        "\n\n\n"
        f"SURVEY: {p.survey}   FILTERS: {p.filters}  TELESCOPE: {p.telescope}\n"
        f"USER: pipeline     HOST: NLHPC\n"
        f"NLIBID: {nlibid}\n"
        f"NPE_PIXEL_SATURATE:   {p.npe_saturate}\n"
        f"PHOTFLAG_SATURATE:    {p.saturation_flag}\n"
        f"{comments}\n"
        "BEGIN LIBGEN\n"
    )


def lib_header(libid: int, ra: float, dec: float, nobs: int,
               p: WriterParams, mwebv: float = 0.0) -> str:
    s = "# --------------------------------------------\n"
    s += f"LIBID: {libid:10d}\n"
    s += (f"RA: {ra:+10.6f} DEC: {dec:+10.6f}   NOBS: {nobs:10d} "
          f"MWEBV: {mwebv:5.2f} PIXSIZE: {p.pixsize:5.3f}\n")
    s += "#                           CCD  CCD         PSF1 PSF2 PSF2/1\n"
    s += "#     MJD      ID*NEXPOSE  FLT GAIN NOISE SKYSIG (pixels)  RATIO  ZPTAVG ZPTERR  MAG\n"
    return s


def lib_footer(libid: int) -> str:
    return f"END_LIBID: {libid:10d}\n"


def simlib_footer(nlibid: int) -> str:
    return f"END_OF_SIMLIB: {nlibid:10d} ENTRIES\n"
