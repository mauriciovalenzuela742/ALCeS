"""Tests de la libreria de armado (no necesitan descargas).

    python -m pytest research/templates_nmf/assemble/tests -q
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import csp_system  # noqa: E402
from extinction import a_lambda, ccm89_odonnell94  # noqa: E402


# --- extincion -----------------------------------------------------------------------------

def test_ccm_es_uno_en_v():
    # x = 1.82 um^-1 => y = 0 => a = 1, b = 0 por construccion de CCM89.
    assert ccm89_odonnell94(1e4 / 1.82) == pytest.approx(1.0, abs=1e-12)


def test_ccm_b_menos_v_da_ebv():
    # Con R_V = 3.1, A(B) - A(V) ~ E(B-V) en las longitudes de onda Johnson (4400, 5500 A).
    ab, av = a_lambda([4400.0, 5500.0], 1.0)
    assert ab - av == pytest.approx(1.0, abs=0.05)


def test_ccm_monotona_en_optico_e_ir():
    w = np.linspace(3500, 30000, 300)
    r = ccm89_odonnell94(w)
    assert np.all(np.diff(r) < 0)


def test_ccm_fuera_de_rango_es_nan():
    assert math.isnan(ccm89_odonnell94(50000.0))  # x = 0.2 < 0.3


def test_ccm_continua_en_los_bordes():
    for x in (1.1, 3.3, 8.0):
        lo, hi = ccm89_odonnell94([1e4 / (x - 1e-6), 1e4 / (x + 1e-6)])
        assert lo == pytest.approx(hi, rel=2e-2)


# --- sistema CSP ---------------------------------------------------------------------------

def test_v_de_csp1_cambia_en_enero_2006():
    assert csp_system.filter_key("Swope+Site3", "V", 53700.0) == "V-3014"
    assert csp_system.filter_key("Swope+Site3", "V", 53755.0) == "V-3009"
    assert csp_system.filter_key("Swope+Site3", "V", 53800.0) == "V-9844"
    assert csp_system.filter_key("Swope+e2v", "V", 53800.0) == "V"


def test_offsets_ab_de_la_tabla():
    _, lam, off = csp_system.lookup("Swope+Site3", "B", 54000.0)
    assert (lam, off) == (4350.6, -0.125)
    _, lam, off = csp_system.lookup("Swope+RetroCam", "J", 54000.0)
    assert (lam, off) == (12386.5, 0.912)
    _, lam, off = csp_system.lookup("Swope+RetroCam", "J", 55000.0)
    assert (lam, off) == (12356.3, 0.901)


def test_sistema_sin_calibrar_da_nan():
    _, lam, off = csp_system.lookup("duPont+TEK5", "B", 54000.0)
    assert math.isnan(lam) and math.isnan(off)


# --- armado CSP SNII (solo funciones puras) ------------------------------------------------

build = pytest.importorskip("build_csp_snii")


def test_parse_explosion():
    assert build.parse_explosion("46708.0$^{n}$(3)") == (46708.0, "non_detection", 3.0, False)
    assert build.parse_explosion("48442.5$^{s}$(8)*") == (48442.5, "spectral_matching", 8.0, True)
    t0, meth, err, ch = build.parse_explosion("--")
    assert math.isnan(t0) and meth == ""


def test_signed_num_de_a16():
    assert build.signed_num("0.45\t") == 0.45
    assert build.signed_num("-0.07") == -0.07
    assert build.signed_num("--0.01") == -0.01  # menos en LaTeX
    assert build.signed_num("93.7    ") == 93.7
    assert math.isnan(build.signed_num("$\\cdots$"))


@pytest.mark.parametrize("hdr,fname,hint,mjd", [
    ({"JD": 2449366.65277778}, "x.fits", None, 49366.15277778),
    ({"MJD-OBS": 3.39e-20, "JD": None, "DATE-OBS": "2005-10-18T01:58:05"}, "x.fits", None, 53661.0),
    ({"DATE-OBS": "2002-10- 8"}, "x.fits", None, 52555.0),
    ({}, "sn93k.14jan94a.fits", 1993, 49366.0),  # el anio del nombre gana al de la SN
    ({}, "sn88a.02feb.fits", 1988, 47193.0),  # sin anio: usa el de la SN
    ({}, "sn90e.blue.3jul90.fits", 1990, 48075.0),
    ({"DATE-OBS": "16/05/93"}, "x.fits", None, 49123.0),
])
def test_fits_mjd(hdr, fname, hint, mjd):
    assert build.fits_mjd(hdr, fname, hint) == pytest.approx(mjd, abs=1e-6)


def test_folder_to_key():
    keys = {"1986L", "2004er", "210"}
    assert build.folder_to_key("SN86L", keys) == "1986L"
    assert build.folder_to_key("SN04er", keys) == "2004er"
    assert build.folder_to_key("SN00cb", keys) == ""  # no esta en la tabla del paper
    assert build.folder_to_key("SN210", keys) == "210"


# --- fin del plateau ----------------------------------------------------------------------

fpe = pytest.importorskip("fit_plateau_end")


def _curve(t, t_pt=100.0, a0=2.0, w0=4.0, noise=0.02, seed=0):
    rng = np.random.default_rng(seed)
    m = fpe.olivares(t, 17.0, a0, w0, 0.01, t_pt) + rng.normal(0, noise, len(t))
    return t, m, np.full(len(t), noise)


def test_plateau_end_recupera_t_pt():
    r = fpe.fit_one(*_curve(np.arange(30.0, 160.0, 4.0)))
    assert r["status"] == "ok"
    assert r["t_pt"] == pytest.approx(100.0, abs=1.5)
    assert r["a0"] == pytest.approx(2.0, abs=0.2)


def test_plateau_sin_caida_no_inventa_t_pt():
    r = fpe.fit_one(*_curve(np.arange(30.0, 85.0, 4.0)))
    assert r["status"] == "sin_caida" and math.isnan(r["t_pt"])


def test_plateau_cola_rala_infla_el_error():
    t = np.r_[np.arange(30.0, 92.0, 4.0), 125.0, 140.0]  # hueco de 33 dias en la caida
    r = fpe.fit_one(*_curve(t))
    assert r["t_pt_err"] >= (125.0 - 90.0) / 2 - 1e-6
    assert r["status"] == "mal_medido"


def test_plateau_inicio_de_caida_con_a0_fijo():
    t = np.arange(30.0, 104.0, 3.0)  # termina en medio de la caida, sin cola
    r_libre = fpe.fit_one(*_curve(t))
    r_fijo = fpe.fit_one(*_curve(t), fixed=(2.0, 4.0))
    assert r_fijo["status"] == "ok"
    assert r_fijo["t_pt"] == pytest.approx(100.0, abs=2.0)
    assert r_libre["status"] != "ok" or abs(r_libre["t_pt"] - 100.0) < 5


# --- armado CSP SESN ----------------------------------------------------------------------

sesn = pytest.importorskip("build_csp_sesn")


def test_sesn_parse_irsa():
    xml = "<statistics>\n <refPixelValueSandF>\n     0.0194 (mag)\n </refPixelValueSandF>"
    assert sesn.parse_irsa(xml) == 0.0194
    assert math.isnan(sesn.parse_irsa("<error/>"))


def test_sesn_lee_fotometria_con_huecos(tmp_path):
    p = tmp_path / "t.dat"
    p.write_text("2004ew 2453289.70  ---     ---   18.666 0.013  17.655 0.011  17.382 0.011"
                 "  19.256 0.015  18.063 0.021\n")
    ph = sesn.read_photometry(str(p), "Swope+Site3", sesn.OPT)
    assert list(ph["band"]) == ["g", "r", "i", "B", "V"]  # u es '---'
    assert ph.loc[ph["band"] == "V", "mag_nat"].item() == 18.063
    assert ph.loc[ph["band"] == "g", "mag_err"].item() == 0.013
