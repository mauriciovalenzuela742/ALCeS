"""
Pruebas de la Capa 1 (modulos puros; sin healpy/opsimsummary).
Se pueden correr con:  python tests/test_simlib_core.py
"""
import sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from pipeline.simlib import classify, formatobs, coverage, writer
from pipeline.simlib.timeutil import iso_to_mjd

_fail = 0
def check(cond, msg):
    global _fail
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond: _fail += 1


# --------- clasificacion (v5.0 + v5.3) ---------
def test_classify():
    print("test_classify")
    notes = pd.Series([
        "pair_33, gr, a",            # WFD (v5.0)
        "pair_33, gr, bs 55, a",     # WFD (v5.3 bloques)
        "templates uu, 30, 69",      # WFD (v5.3 template tier)
        "blob_long, ri, b",          # WFD
        "greedy i",                  # WFD (por prefijo)
        "DD:COSMOS, 20360613, 1",    # DDF
        "twilight_near_sun, 0",      # twilight
        "ToO, neutrino, r, 32",      # Other
        None,                        # Other (NaN)
    ])
    exp = ["WFD","WFD","WFD","WFD","WFD","DDF","twilight","Other","Other"]
    got = classify.classify_field_type(notes).tolist()
    check(got == exp, f"prefijos v5.0+v5.3 -> {got}")


# --------- format_obs (arxiv 1905.02887) ---------
def test_format_obs():
    print("test_format_obs")
    df = pd.DataFrame({
        "observationStartMJD": [61208.5, 61210.5],
        "band": ["r", "y"],
        "seeingFwhmEff": [1.0, 0.8],
        "fiveSigmaDepth": [24.0, 23.0],
        "skyBrightness": [21.0, 20.0],
    })
    out = formatobs.format_obs(df, pixsize=0.2)
    psf_expected = 1.0 / (2*np.sqrt(2*np.log(2))) / 0.2  # ~2.1236
    check(abs(out["PSF"].iloc[0] - psf_expected) < 1e-6, f"PSF={out['PSF'].iloc[0]:.4f} (~2.1236)")
    check(bool((out["SKYSIG"] > 0).all()), "SKYSIG > 0")
    check(bool(np.isfinite(out["ZPT"]).all()), "ZPT finito")
    check(out["BAND"].tolist() == ["r","Y"], "banda y -> Y")


# --------- timeutil ---------
def test_timeutil():
    print("test_timeutil")
    # el notebook obtuvo 62501.00 para 2029-12-31
    check(abs(iso_to_mjd("2029-12-31") - 62501.0) < 1e-6, f"2029-12-31 -> {iso_to_mjd('2029-12-31')}")
    check(abs(iso_to_mjd("2027-01-01") - 61406.0) < 1e-6, f"2027-01-01 -> {iso_to_mjd('2027-01-01')}")


# --------- coverage ---------
def test_coverage():
    print("test_coverage")
    df = pd.DataFrame({
        "BAND": ["r"]*4 + ["g"]*2,
        "expMJD": [1.0, 3.0, 6.0, 10.0, 2.0, 5.0],
        "m5": [24]*6, "ZPT": [31]*6, "PSF": [2.0]*6, "SKYSIG": [40]*6,
        "field_id": [0,0,0,0,0,0],
    })
    rep = coverage.coverage_report(df, n_fields=1, bands=["u","g","r","i","z","Y"])
    r = {b["band"]: b for b in rep["bands"]}
    check(rep["n_obs"] == 6, "n_obs=6")
    check(r["r"]["n"] == 4 and r["g"]["n"] == 2, "conteo por banda")
    check(r["u"]["n"] == 0, "banda ausente -> 0")
    check(abs(r["r"]["cadence_median_days"] - 3.0) < 1e-9, "cadencia r (gaps 2,3,4 -> mediana 3)")


# --------- writer round-trip (escribir -> parsear) ---------
def _parse(txt):
    bands, nlib = {}, 0
    for line in txt.splitlines():
        if line.startswith("NLIBID:"): nlib = int(line.split()[1])
        if line.startswith("S:"):
            t = line.split()[1:]
            bands[t[2]] = bands.get(t[2], 0) + 1
    return nlib, bands

def test_writer_roundtrip():
    print("test_writer_roundtrip")
    p = writer.WriterParams()
    df = pd.DataFrame({
        "observationStartMJD": np.linspace(61208, 61230, 12),
        "band": (["u","g","r","i","z","y"]*2),
        "seeingFwhmEff": [1.0]*12, "fiveSigmaDepth": [24.0]*12, "skyBrightness": [21.0]*12,
    })
    fobs = formatobs.format_obs(df)
    parts = [writer.simlib_header(1, p), writer.lib_header(0, 12.3, -45.6, len(fobs), p)]
    parts += [writer.dataline(t.expMJD, t.ObsID, t.BAND, t.SKYSIG, t.PSF, t.ZPT, p)
              for t in fobs.itertuples(index=False)]
    parts += [writer.lib_footer(0), writer.simlib_footer(1)]
    txt = "\n".join(parts)
    nlib, bands = _parse(txt)
    check(nlib == 1, "NLIBID=1")
    check(sum(bands.values()) == 12, "12 lineas S:")
    check(set(bands) == {"u","g","r","i","z","Y"}, f"bandas {sorted(bands)} (y->Y)")
    # columna FLT en indice 2, ZPT en indice 9 (layout que lee el visualizer)
    sline = [l for l in txt.splitlines() if l.startswith("S:")][0].split()[1:]
    check(len(sline) == 12, "12 columnas por linea S:")


if __name__ == "__main__":
    for t in (test_classify, test_format_obs, test_timeutil, test_coverage, test_writer_roundtrip):
        t()
    print(f"\n{'TODOS OK ✓' if _fail == 0 else str(_fail)+' FALLARON ✗'}")
    sys.exit(1 if _fail else 0)
