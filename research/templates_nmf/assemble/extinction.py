"""Ley de extincion de Cardelli, Clayton & Mathis (1989) con los coeficientes opticos de
O'Donnell (1994). Valida entre 0.3 y 10 um^-1 (1000 A - 3.3 um).

A(lambda) = E(B-V) * R_V * (a(x) + b(x)/R_V), con x = 1/lambda en um^-1.
"""
import numpy as np


def ccm89_odonnell94(wave_A, r_v=3.1):
    """A(lambda)/A(V) para longitudes de onda en Angstrom (escalar o arreglo)."""
    x = 1e4 / np.atleast_1d(np.asarray(wave_A, dtype=float))
    a = np.full_like(x, np.nan)
    b = np.full_like(x, np.nan)

    ir = (x >= 0.3) & (x < 1.1)
    a[ir] = 0.574 * x[ir] ** 1.61
    b[ir] = -0.527 * x[ir] ** 1.61

    opt = (x >= 1.1) & (x < 3.3)
    y = x[opt] - 1.82
    a[opt] = np.polyval([-0.505, 1.647, -0.827, -1.718, 1.137, 0.701, -0.609, 0.104, 1.0], y)
    b[opt] = np.polyval([3.347, -10.805, 5.491, 11.102, -7.985, -3.989, 2.908, 1.952, 0.0], y)

    uv = (x >= 3.3) & (x <= 8.0)
    xu = x[uv]
    fa = np.where(xu >= 5.9, -0.04473 * (xu - 5.9) ** 2 - 0.009779 * (xu - 5.9) ** 3, 0.0)
    fb = np.where(xu >= 5.9, 0.2130 * (xu - 5.9) ** 2 + 0.1207 * (xu - 5.9) ** 3, 0.0)
    a[uv] = 1.752 - 0.316 * xu - 0.104 / ((xu - 4.67) ** 2 + 0.341) + fa
    b[uv] = -3.090 + 1.825 * xu + 1.206 / ((xu - 4.62) ** 2 + 0.263) + fb

    fuv = (x > 8.0) & (x <= 10.0)
    z = x[fuv] - 8.0
    a[fuv] = np.polyval([-0.070, 0.137, -0.628, -1.073], z)
    b[fuv] = np.polyval([0.374, -0.420, 4.257, 13.670], z)

    out = a + b / r_v
    return out if np.ndim(wave_A) else float(out[0])


def a_lambda(wave_A, ebv, r_v=3.1):
    """Extincion en magnitudes."""
    return np.asarray(ebv) * r_v * ccm89_odonnell94(wave_A, r_v)
