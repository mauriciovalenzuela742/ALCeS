"""Sistema fotometrico natural de CSP: longitud de onda efectiva y offset a AB por filtro.

Fuente: tabla de https://csp.obs.carnegiescience.edu/data/filters (consultada 2026-10-28), que
reproduce los zero points de Krisciunas et al. (2017AJ....154..211K). Convencion de la pagina:
m(AB) = m(natural) + offset.

CSP-I usa la Swope con el CCD SITe #3 (la tabla lo rotula "Site2 CCD" con el mismo rango de
fechas 2003-10/2013; Anderson+24 lo llama "Swope+Site3"). CSP-II usa el CCD e2v desde 10/2013.
La V de CSP-I cambio dos veces de filtro en enero de 2006 (LC-3014 -> LC-3009 -> LC-9844).
"""
import math

# Cambios de filtro/instrumento (MJD).
MJD_V3009 = 53749.0  # 2006-01-14
MJD_V9844 = 53760.0  # 2006-01-25
MJD_J_SWOPE_NEW = 54846.0  # 2009-01-15

# (lambda_eff [A], offset AB) por filtro.
SWOPE_SITE3 = {
    "u": (3639.3, -0.058), "g": (4765.1, -0.017), "r": (6223.3, -0.006),
    "i": (7609.2, +0.001), "B": (4350.6, -0.125),
    "V-3014": (5369.6, -0.016), "V-3009": (5401.4, -0.019), "V-9844": (5375.2, -0.020),
}
SWOPE_E2V = {
    "u": (3615.1, -0.046), "g": (4646.6, -0.012), "r": (6142.3, -0.004),
    "i": (7573.8, +0.003), "B": (4338.1, -0.126), "V": (5354.7, -0.020),
}
SWOPE_RETROCAM = {
    "Y": (10350.8, +0.629), "J-old": (12386.5, +0.912), "J-new": (12356.3, +0.901),
    "H": (16297.7, +1.343),
}
DUPONT_WIRC = {"Y": (10439.8, +0.629), "J": (12383.2, +0.912), "H": (16282.8, +1.342)}
DUPONT_RETROCAM = {"Y": (10353.1, +0.632), "J": (12364.0, +0.904), "H": (16214.4, +1.339)}


def filter_key(system, band, mjd):
    """Nombre del filtro fisico usado (para V y J dependen de la fecha)."""
    if system == "Swope+Site3" and band == "V":
        if mjd < MJD_V3009:
            return "V-3014"
        return "V-3009" if mjd < MJD_V9844 else "V-9844"
    if system == "Swope+RetroCam" and band == "J":
        return "J-old" if mjd < MJD_J_SWOPE_NEW else "J-new"
    return band


TABLES = {
    "Swope+Site3": SWOPE_SITE3,
    "Swope+e2v": SWOPE_E2V,
    "Swope+RetroCam": SWOPE_RETROCAM,
    "duPont+WIRC": DUPONT_WIRC,
    "duPont+RetroCam": DUPONT_RETROCAM,
}


def lookup(system, band, mjd):
    """(filtro, lambda_eff, offset_AB). NaN si el sistema no esta en la tabla de CSP
    (p. ej. duPont+TEK5, que la pagina no calibra)."""
    key = filter_key(system, band, mjd)
    lam, off = TABLES.get(system, {}).get(key, (math.nan, math.nan))
    return key, lam, off
