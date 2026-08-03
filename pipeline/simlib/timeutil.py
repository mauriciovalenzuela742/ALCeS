"""
timeutil.py — Conversion fecha ISO -> MJD sin dependencias (sin astropy).

Se usa para el recorte temporal del SIMLIB a partir de fechas legibles en la
config (p.ej. "2029-12-31"), replicando lo que en el notebook hace
astropy.time.Time(..., format='iso').mjd, pero sin cargar astropy.
"""

from __future__ import annotations

import datetime as _dt

_MJD_OFFSET = 2400000.5


def _gregorian_to_jd(year: int, month: int, day: int) -> float:
    """Dia Juliano (a 0h UTC) por el algoritmo de Fliegel-Van Flandern."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = (day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045)
    return jdn - 0.5  # a 0h UTC


def iso_to_mjd(date: str) -> float:
    """'YYYY-MM-DD' (o con hora) -> MJD. Acepta date/datetime tambien."""
    if isinstance(date, (_dt.date, _dt.datetime)):
        d = date
    else:
        d = _dt.datetime.fromisoformat(str(date))
    frac = 0.0
    if isinstance(d, _dt.datetime):
        frac = (d.hour + d.minute / 60 + d.second / 3600) / 24.0
    jd = _gregorian_to_jd(d.year, d.month, d.day) + frac
    return jd - _MJD_OFFSET
