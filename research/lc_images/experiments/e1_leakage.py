"""E1: ¿infla la exactitud repetir templates entre train y test?

Mismo modelo y mismos rasgos con dos particiones: aleatoria por objeto y agrupada por template
(clase + TEMPLATE_INDEX). La diferencia entre ambas es la fuga. Se reporta global y por bin de
noches con deteccion (1, 2, 3, 4-5, 6+), con 5 semillas y un control con etiquetas barajadas
(debe dar nivel de azar).

Uso (en NLHPC, dentro de SLURM; ver slurm/e1_leakage.sbatch):
    python e1_leakage.py --runs-dir <dir con <clase>_seed<N>/> --classes KN-K17 KN-BULLA19 SNIa \\
        --out results/e1/<tag> [--model knn|gbdt] [--with-z] [--seeds 0 1 2 3 4]

Escribe en --out: config.json (argumentos, commit y SHA256 de cada parquet), features.parquet,
metrics.csv (una fila por semilla, particion y bin) y summary.md.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data import runs as D  # noqa: E402
from experiments import metrics as M  # noqa: E402
from experiments import splits as S  # noqa: E402
from models.knn import KNN, prepare  # noqa: E402

SPLITS = ["random", "grouped", "grouped_shuffled"]


def make_model(name: str, seed: int, k: int):
    if name == "knn":
        return KNN(k=k)
    from models.gbdt import GBDT, available
    if not available():
        raise SystemExit("--model gbdt necesita sklearn (venv aparte de research/lc_images).")
    return GBDT(seed=seed)


def run_e1(df: pd.DataFrame, cols: list[str], seeds: list[int], test_frac: float = 0.3,
           model: str = "knn", k: int = 5) -> pd.DataFrame:
    """Una fila por (semilla, particion, bin); bin 'all' es el global."""
    y, groups = df["class_key"].to_numpy(), df["group"].to_numpy()
    nights = df["night_bin"].to_numpy()
    rows = []
    for seed in seeds:
        masks = {"random": S.random_split(y, test_frac, seed),
                 "grouped": S.grouped_split(y, groups, test_frac, seed)}
        masks["grouped_shuffled"] = masks["grouped"]
        for split in SPLITS:
            test = masks[split]
            tr, te = df[~test], df[test]
            xtr, xte = prepare(tr, te, cols)
            ytr = y[~test].copy()
            if split == "grouped_shuffled":
                np.random.default_rng(seed + 1000).shuffle(ytr)
            pred = make_model(model, seed, k).fit(xtr, ytr).predict(xte)
            base = {"seed": seed, "split": split, "model": model,
                    "shared_group_frac": S.shared_groups(groups, test),
                    "untestable": ";".join(S.untestable_classes(y, test))}
            rows.append({**base, "bin": "all", "n": int(test.sum()), "n_classes": len(np.unique(y[test])),
                         "balanced_accuracy": M.balanced_accuracy(y[test], pred),
                         "macro_f1": M.macro_f1(y[test], pred)})
            rows += [{**base, **r} for r in M.by_bin(y[test], pred, nights[test], D.NIGHT_LABELS)]
    return pd.DataFrame(rows)


def summarize(res: pd.DataFrame) -> str:
    """Tabla media ± desviacion por particion y bin, y la fuga (aleatoria - agrupada)."""
    order = ["all"] + D.NIGHT_LABELS
    g = res.groupby(["bin", "split"])["balanced_accuracy"].agg(["mean", "std", "count"]).reset_index()
    lines = ["| bin | " + " | ".join(SPLITS) + " | fuga (aleatoria − agrupada) |",
             "|---|" + "---|" * (len(SPLITS) + 1)]
    for b in order:
        sub = g[g["bin"] == b].set_index("split")
        if sub.empty:
            continue
        cells = [f"{sub.at[s, 'mean']:.3f} ± {sub.at[s, 'std']:.3f}" if s in sub.index else "—" for s in SPLITS]
        paired = res[res["bin"] == b].pivot_table(index="seed", columns="split", values="balanced_accuracy")
        if {"random", "grouped"} <= set(paired.columns):
            d = paired["random"] - paired["grouped"]
            cells.append(f"{d.mean():+.3f} ± {d.std():.3f}")
        else:
            cells.append("—")
        lines.append(f"| {b} | " + " | ".join(cells) + " |")
    shared = res[res["bin"] == "all"].groupby("split")["shared_group_frac"].mean()
    lines += ["", "Fracción de objetos de test cuyo template también está en train: " +
              ", ".join(f"{s} {v:.2f}" for s, v in shared.items())]
    unt = sorted({c for v in res["untestable"] for c in v.split(";") if c})
    if unt:
        lines.append(f"Clases sin evaluación agrupada posible (un solo template): {', '.join(unt)}")
    return "\n".join(lines)


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--classes", nargs="*", default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", choices=["knn", "gbdt"], default="knn")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--with-z", action="store_true", help="agrega REDSHIFT_HELIO a los rasgos")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    head, phot = D.load(args.runs_dir, args.classes)
    df = D.features(head, phot)
    df.to_parquet(args.out / "features.parquet", index=False)
    cols = D.LC_COLS + (["REDSHIFT_HELIO"] if args.with_z else [])
    cols = [c for c in cols if df[c].notna().mean() > 0.2]  # como separability_pairs
    config = {**{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
              "features_used": cols, "commit": git_commit(),
              "n_detected": df["class_key"].value_counts().to_dict(),
              "n_templates": df.groupby("class_key")["group"].nunique().to_dict(),
              "inputs_sha256": D.input_hashes(args.runs_dir, sorted(df["run"].unique()))}
    (args.out / "config.json").write_text(json.dumps(config, indent=1, default=str))

    res = run_e1(df, cols, args.seeds, args.test_frac, args.model, args.k)
    res.to_csv(args.out / "metrics.csv", index=False, float_format="%.4f")
    text = summarize(res)
    (args.out / "summary.md").write_text(f"# E1 ({args.model}, {', '.join(sorted(config['n_detected']))})\n\n"
                                         f"Exactitud balanceada, media ± desviación en {len(args.seeds)} semillas.\n\n"
                                         + text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
