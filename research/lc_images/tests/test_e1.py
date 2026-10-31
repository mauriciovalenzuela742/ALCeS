"""Tests de E1 con datos sinteticos (no necesitan corridas de NLHPC).

    python -m pytest research/lc_images/tests -q
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import runs as D  # noqa: E402
from experiments import e1_leakage as E1  # noqa: E402
from experiments import metrics as M  # noqa: E402
from experiments import splits as S  # noqa: E402
from models.knn import KNN, prepare  # noqa: E402


def _leaky(n_templates=30, per_template=12, shift=0.15, noise=0.05, seed=0):
    """Dos clases; cada template es una huella fuerte y la clase apenas mueve la huella.

    Con el mismo template en train y test, el kNN acierta por memoria; sin el, casi al azar.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for c, cls in enumerate(["A", "B"]):
        for t in range(n_templates):
            center = rng.normal(0, 1, 4) + c * shift
            for j in range(per_template):
                x = center + rng.normal(0, noise, 4)
                rows.append({"run": f"{cls}_seed0", "SNID": t * 100 + j, "class_key": cls,
                             "TEMPLATE_INDEX": t, "f0": x[0], "f1": x[1], "f2": x[2], "f3": x[3],
                             "n_det_nights": 1 + (j % 7)})
    df = pd.DataFrame(rows)
    df["group"] = D.template_groups(df)
    df["night_bin"] = pd.cut(df["n_det_nights"], D.NIGHT_BINS, labels=D.NIGHT_LABELS).astype(str)
    return df


def test_agrupada_no_comparte_templates():
    df = _leaky()
    y, g = df["class_key"].to_numpy(), df["group"].to_numpy()
    for seed in range(5):
        test = S.grouped_split(y, g, 0.3, seed)
        assert not set(g[test]) & set(g[~test])
        assert S.shared_groups(g, test) == 0.0
        for c in ("A", "B"):  # cada clase tiene train y test, cerca de 30 %
            frac = test[y == c].mean()
            assert 0.2 < frac < 0.45
    rnd = S.random_split(y, 0.3, 0)
    assert S.shared_groups(g, rnd) > 0.9  # con 12 objetos por template casi todo se comparte


def test_e1_detecta_la_fuga_y_el_control_da_azar():
    df = _leaky()
    res = E1.run_e1(df, ["f0", "f1", "f2", "f3"], seeds=[0, 1, 2])
    allb = res[res["bin"] == "all"].groupby("split")["balanced_accuracy"].mean()
    assert allb["random"] > 0.95
    assert allb["random"] - allb["grouped"] > 0.25
    assert abs(allb["grouped_shuffled"] - 0.5) < 0.15
    assert set(res["bin"]) == {"all", *D.NIGHT_LABELS}
    text = E1.summarize(res)
    assert "fuga" in text and "| all |" in text


def test_sin_template_cada_objeto_es_su_grupo():
    df = pd.DataFrame({"run": ["SNIa_seed0"] * 3 + ["KN-K17_seed0"] * 2, "SNID": [1, 2, 3, 1, 2],
                       "class_key": ["SNIa"] * 3 + ["KN-K17"] * 2,
                       "TEMPLATE_INDEX": [np.nan, np.nan, np.nan, 7, 7]})
    g = D.template_groups(df)
    assert len(set(g[:3])) == 3  # SALT2: sin template, la agrupada se reduce a la aleatoria
    assert g[3] == g[4] == "KN-K17:T7"


def test_clase_con_un_template_queda_sin_evaluar():
    y = np.array(["A"] * 10 + ["B"] * 10)
    g = np.array(["A:T0"] * 10 + [f"B:T{i}" for i in range(10)])
    test = S.grouped_split(y, g, 0.3, 0)
    assert not test[y == "A"].any()
    assert S.untestable_classes(y, test) == ["A"]


def test_metricas():
    y = np.array(["a", "a", "a", "b"])
    p = np.array(["a", "a", "b", "b"])
    assert M.balanced_accuracy(y, p) == (2 / 3 + 1) / 2
    f1_a, f1_b = 2 * 1 * (2 / 3) / (1 + 2 / 3), 2 * 0.5 * 1 / 1.5
    assert math.isclose(M.macro_f1(y, p), (f1_a + f1_b) / 2)
    cm = M.confusion(y, p)
    assert math.isclose(cm.loc["a", "b"], 1 / 3)
    rows = M.by_bin(y, p, np.array(["1", "1", "2", "2"]), ["1", "2", "6+"])
    assert [r["bin"] for r in rows] == ["1", "2"]


def test_prepare_usa_solo_estadisticas_de_train():
    tr = pd.DataFrame({"a": [0.0, 2.0, np.nan]})
    te = pd.DataFrame({"a": [100.0, np.nan]})
    xtr, xte = prepare(tr, te, ["a"])
    # mediana de train = 1 imputa los NaN; media 1 y sd 0.816 de train escalan el test
    assert np.allclose(xtr[:, 0], [-1.2247, 1.2247, 0.0], atol=1e-3)
    assert math.isclose(xte[0, 0], (100 - 1) / np.std([0, 2, 1]))
    assert xtr.shape[1] == 2 and list(xte[:, 1]) == [0.0, 1.0]  # columna de faltantes


def test_knn_vota_ponderado_por_clase():
    x = np.array([[0.0], [0.1], [0.2], [0.3], [5.0]])
    y = np.array(["mayor"] * 4 + ["menor"])
    # Cada voto pesa 1/(tamano de su clase): un vecino "menor" vale lo que cuatro "mayor".
    assert KNN(k=3).fit(x, y).predict(np.array([[0.05]]))[0] == "mayor"
    assert KNN(k=1).fit(x, y).predict(np.array([[4.9]]))[0] == "menor"


def test_features_desde_photometria_sintetica():
    def obs(snid, mjd, flt, flux, det):
        return {"run": "KN-K17_seed0", "SNID": snid, "MJD": mjd, "FLT": flt, "FLUXCAL": flux,
                "FLUXCALERR": 10.0, "PHOTFLAG": 4096 if det else 0, "MAG": 27.5 - 2.5 * np.log10(flux)}
    phot = pd.DataFrame([obs(1, 60000.2, "g", 500.0, True), obs(1, 60000.3, "r", 600.0, True),
                         obs(1, 60003.2, "r", 300.0, True), obs(2, 60010.2, "i", 400.0, True),
                         obs(2, 60011.2, "i", 20.0, False)])
    head = pd.DataFrame({"run": ["KN-K17_seed0"] * 2, "SNID": [1, 2], "class_key": ["KN-K17"] * 2,
                         "REDSHIFT_HELIO": [0.02, 0.03], "TEMPLATE_INDEX": [4, 9]})
    df = D.features(head, phot).set_index("SNID")
    assert df.at[1, "n_det_nights"] == 2 and df.at[1, "night_bin"] == "2"
    assert df.at[2, "n_det_nights"] == 1 and df.at[2, "night_bin"] == "1"
    assert df.at[1, "group"] == "KN-K17:T4"
    assert set(D.LC_COLS) <= set(df.columns)
