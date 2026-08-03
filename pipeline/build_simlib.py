#!/usr/bin/env python3
"""
build_simlib.py — CLI de la Capa 1.

Construye un SIMLIB (WFD o DDF) a partir de una base OpSim registrada en la
Capa 0, y emite un reporte de cobertura por banda para contrastar contra MAF.

    python -m pipeline.build_simlib --run baseline_v5.3.1_10yrs --strategy WFD
    python -m pipeline.build_simlib --run baseline_v5.3.1_10yrs --strategy DDF --limit 50
    python -m pipeline.build_simlib --self-test        # tuberia sintetica (sin .db)

NOTA: contra un .db real esto es computo pesado (Healpix + BallTree sobre
~1.8M filas) y SOLO corre dentro de un job SLURM — se niega a correr en el
login node (ver pipeline.paths.require_slurm). Lanzar con:
    sbatch slurm/build_simlib.sbatch <RUN> <STRATEGY>
--self-test si corre libre en login, es sintetico y liviano.

Pasos (contra un .db real):
    Registry -> OpSimSummaryV2 -> clasificar -> recorte temporal -> split
    -> BallTree -> compute_hp_rep -> sample_survey -> escribir SIMLIB + cobertura
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from pipeline.registry import Registry, RegistryError
    from pipeline import paths as _paths
    from pipeline.simlib import config as cfgmod
    from pipeline.simlib import classify, formatobs, coverage, hprep, writer
    from pipeline.simlib.timeutil import iso_to_mjd
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.registry import Registry, RegistryError
    from pipeline import paths as _paths
    from pipeline.simlib import config as cfgmod
    from pipeline.simlib import classify, formatobs, coverage, hprep, writer
    from pipeline.simlib.timeutil import iso_to_mjd


# ----------------------------------------------------------- recorte temporal
def resolve_cut(df: pd.DataFrame, cut) -> tuple[float, float]:
    lo = df["observationStartMJD"].min()
    hi = df["observationStartMJD"].max()
    mjd_min = cut.mjd_min if cut.mjd_min is not None else (iso_to_mjd(cut.date_min) if cut.date_min else lo)
    mjd_max = cut.mjd_max if cut.mjd_max is not None else (iso_to_mjd(cut.date_max) if cut.date_max else hi)
    return max(mjd_min, lo), min(mjd_max, hi)


# --------------------------------------------------------------- escritura core
def write_simlib_and_coverage(sub: pd.DataFrame, tree, sample: pd.DataFrame,
                              cfg, out_simlib: Path, opsim_file: str):
    """Escribe el SIMLIB recorriendo campos y acumula el reporte de cobertura."""
    p = cfg.writer
    idxs = hprep.field_obs_indices(tree, sample["hp_ra"].to_numpy(),
                                   sample["hp_dec"].to_numpy(), cfg.radius_deg)
    area = float(sample.attrs.get("survey_area_deg", 0.0))
    minmjd = float(sub["observationStartMJD"].min())
    maxmjd = float(sub["observationStartMJD"].max())

    parts = [writer.simlib_doc(opsim_file, minmjd, maxmjd, area, p),
             writer.simlib_header(len(sample), p)]
    cov_frames = []
    for libid, (row, idx) in enumerate(zip(sample.itertuples(index=False), idxs)):
        obs = sub.iloc[idx]
        fobs = formatobs.format_obs(obs, cfg.pixsize)
        ra, dec = np.degrees(row.hp_ra), np.degrees(row.hp_dec)
        parts.append(writer.lib_header(libid, ra, dec, len(fobs), p))
        parts.extend(
            writer.dataline(t.expMJD, t.ObsID, t.BAND, t.SKYSIG, t.PSF, t.ZPT, p)
            for t in fobs.itertuples(index=False)
        )
        parts.append(writer.lib_footer(libid))
        f2 = fobs.copy(); f2["field_id"] = libid
        cov_frames.append(f2)
    parts.append(writer.simlib_footer(len(sample)))

    out_simlib.parent.mkdir(parents=True, exist_ok=True)
    out_simlib.write_text("\n".join(s.rstrip("\n") for s in parts) + "\n", encoding="utf-8")

    allf = pd.concat(cov_frames, ignore_index=True) if cov_frames else pd.DataFrame()
    report = coverage.coverage_report(allf, n_fields=len(sample), bands=list(cfg.bands))
    return report


def save_reports(report: dict, out_simlib: Path, run: str, strategy: str, opsim_file: str):
    # OJO: no usar Path.with_suffix() sobre el nombre base — nombres de run
    # como "baseline_v5.3.1_10yrs" tienen puntos, y with_suffix() solo corta
    # el ULTIMO ".algo", así que aplicarlo dos veces (una para pelar .SIMLIB,
    # otra para poner .coverage.json) trunca el nombre a "baseline_v5.3"
    # y deja el .coverage.json donde compile_campaign nunca lo encuentra
    # (cae en silencio al rango MJD por defecto — bug real, ya visto en produccion).
    base_name = out_simlib.name.removesuffix(out_simlib.suffix)  # quita solo ".SIMLIB"
    base = out_simlib.parent / base_name
    coverage.coverage_to_frame(report).to_csv(base.parent / f"{base.name}.coverage.csv", index=False)
    (base.parent / f"{base.name}.coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    prov = {
        "run": run, "strategy": strategy, "opsim_file": opsim_file,
        "simlib": out_simlib.name, "n_fields": report["n_fields"], "n_obs": report["n_obs"],
        "mjd_min": report["mjd_min"], "mjd_max": report["mjd_max"],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "build_simlib.py",
    }
    (base.parent / f"{base.name}.provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")


def print_coverage(report: dict):
    print(f"\n  cobertura: {report['n_obs']:,} obs · {report['n_fields']} campos · "
          f"MJD {report['mjd_min']:.1f}–{report['mjd_max']:.1f} ({report['duration_years']} a)")
    print(f"  {'banda':<6}{'N':>10}{'m5':>9}{'ZPT':>9}{'PSF':>7}{'SKYSIG':>9}{'cad(d)':>9}")
    for b in report["bands"]:
        if not b.get("n"):
            print(f"  {b['band']:<6}{0:>10}"); continue
        f = lambda v: f"{v:.2f}" if v is not None else "—"
        print(f"  {b['band']:<6}{b['n']:>10,}{f(b['m5_median']):>9}{f(b['zpt_median']):>9}"
              f"{f(b['psf_median']):>7}{f(b['skysig_median']):>9}{f(b['cadence_median_days']):>9}")


# ------------------------------------------------------------------ build real
def build(run: str, strategy: str, cfg, out_dir: Path, limit: int | None, *, allow_login: bool = False) -> int:
    _paths.require_slurm(
        "build_simlib (Capa 1)",
        f"sbatch slurm/build_simlib.sbatch {run} {strategy}",
        allow_flag=allow_login,
    )

    import opsimsummaryv2 as opsim  # lazy: solo al construir contra un .db real

    reg = Registry.load()
    run_meta = reg.get(run)
    db = reg.local_path(run)
    if not db.exists():
        print(f"error: {db} no existe. Corre primero:  python -m pipeline.fetch_opsim --run {run}",
              file=sys.stderr)
        return 2

    print(f"» cargando {db.name} con OpSimSummaryV2 …")
    survey = opsim.OpSimSurvey(str(db))
    df = survey.opsimdf
    if run_meta.n_obs and len(df) != run_meta.n_obs:
        print(f"  ⚠ sanity: {len(df):,} obs leidas ≠ {run_meta.n_obs:,} esperadas (registro)")
    else:
        print(f"  ✓ {len(df):,} observaciones")

    df = hprep.ensure_radian_coords(df)
    df["field_type"] = classify.classify_field_type(df["scheduler_note"], cfg.rules)
    print(f"  clasificacion: {classify.classification_summary(df['field_type'])}")

    mjd_lo, mjd_hi = resolve_cut(df, cfg.cut)
    df = df[(df["observationStartMJD"] >= mjd_lo) & (df["observationStartMJD"] <= mjd_hi)]
    print(f"  recorte temporal: MJD {mjd_lo:.2f} – {mjd_hi:.2f} ({len(df):,} obs)")

    key = "DDF" if strategy.upper() == "DDF" else "WFD"
    sub = df[df["field_type"] == key].copy()
    if sub.empty:
        print(f"error: no hay observaciones {key} tras el recorte", file=sys.stderr)
        return 2

    st = cfg.strategy(key)
    tree = hprep.build_tree(sub)
    rep = hprep.compute_hp_rep(sub, tree, cfg.nside, st.min_visits, radius_deg=cfg.radius_deg)
    n = min(st.n_fields, len(rep))
    sample = hprep.sample_survey(rep, n, cfg.seed)
    if limit:
        sample = sample.head(limit)
    print(f"  {key}: {len(rep):,} campos ≥{st.min_visits} vis · muestra={len(sample)}")

    out = out_dir / run / f"{key}_{run}.SIMLIB"
    report = write_simlib_and_coverage(sub, tree, sample, cfg, out, run_meta.filename)
    save_reports(report, out, run, key, run_meta.filename)
    print(f"  ✓ SIMLIB: {out}")
    print_coverage(report)
    return 0


# ------------------------------------------------------------------ self-test
def self_test(cfg, out_dir: Path) -> int:
    """Corre classify -> format_obs -> writer -> coverage sobre datos SINTETICOS.

    No usa healpy ni opsimsummary: agrupa obs falsas en 'campos' a mano. Sirve
    para validar el cableado de la capa (y el formato del SIMLIB) sin un .db.
    """
    print("» self-test con datos SINTETICOS (no son datos reales)")
    rng = np.random.default_rng(cfg.seed)
    bands = list("ugrizY")
    notes = {  # mezcla de familias v5.0 y v5.3
        "pair_33, gr, a": "WFD", "templates uu, 30, 69": "WFD",
        "pair_33, gr, bs 55, a": "WFD", "blob_long, ri, b": "WFD",
        "DD:COSMOS, 1, 2": "DDF", "twilight_near_sun, 0": "twilight",
        "ToO, neutrino, r": "Other",
    }
    # verifica el clasificador
    s = pd.Series(list(notes))
    got = classify.classify_field_type(s, cfg.rules).tolist()
    assert got == list(notes.values()), f"clasificacion inesperada: {got}"
    print(f"  ✓ clasificacion OK: {dict(zip(notes, got))}")

    # fabrica obs WFD-like agrupadas en 8 campos
    rows, field_of = [], []
    for fid in range(8):
        ra, dec = rng.uniform(0, 360), rng.uniform(-70, 20)
        mjd = 61208 + rng.uniform(0, 20)
        for _ in range(60):
            mjd += rng.choice([0.023, 2.5, 3.0])
            b = rng.choice(bands)
            rows.append(dict(
                observationStartMJD=mjd, band=b, fieldRA=ra, fieldDec=dec,
                seeingFwhmEff=float(rng.uniform(0.7, 1.3)),
                fiveSigmaDepth=float(rng.uniform(22.5, 24.5)),
                skyBrightness=float(rng.uniform(19.5, 22.0)),
                scheduler_note="pair_33, gr, a",
            ))
            field_of.append(fid)
    df = pd.DataFrame(rows)

    # format_obs + escritura por campo
    p = cfg.writer
    parts = [writer.simlib_doc("SYNTH", df.observationStartMJD.min(),
                               df.observationStartMJD.max(), 42.0, p),
             writer.simlib_header(8, p)]
    cov = []
    for fid in range(8):
        obs = df[np.array(field_of) == fid].reset_index(drop=True)
        fobs = formatobs.format_obs(obs, cfg.pixsize)
        parts.append(writer.lib_header(fid, obs.fieldRA.iloc[0], obs.fieldDec.iloc[0], len(fobs), p))
        parts.extend(writer.dataline(t.expMJD, t.ObsID, t.BAND, t.SKYSIG, t.PSF, t.ZPT, p)
                     for t in fobs.itertuples(index=False))
        parts.append(writer.lib_footer(fid))
        f2 = fobs.copy(); f2["field_id"] = fid; cov.append(f2)
    parts.append(writer.simlib_footer(8))

    out = out_dir / "_selftest" / "WFD_selftest.SIMLIB"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(x.rstrip("\n") for x in parts) + "\n", encoding="utf-8")
    report = coverage.coverage_report(pd.concat(cov, ignore_index=True), n_fields=8, bands=bands)
    save_reports(report, out, "selftest", "WFD", "SYNTH")
    print(f"  ✓ SIMLIB sintetico: {out}")
    print_coverage(report)
    print("\n  self-test OK ✓")
    return 0


# ------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_simlib",
                                 description="Capa 1 — constructor de SIMLIB (Vera C. Rubin).")
    ap.add_argument("--run", help="nombre de la run OpSim (registro Capa 0)")
    ap.add_argument("--strategy", choices=["WFD", "DDF"], help="estrategia a construir")
    ap.add_argument("--config", help="ruta a simlib.yaml (por defecto pipeline/simlib.yaml)")
    ap.add_argument("--out", help="directorio de salida (por defecto data/simlib)")
    ap.add_argument("--limit", type=int, help="cap de campos (pruebas rapidas)")
    ap.add_argument("--self-test", action="store_true", help="tuberia sintetica sin .db")
    ap.add_argument("--allow-login", action="store_true",
                     help="fuerza correr en el login node (excepcion, no la regla — ver README)")
    args = ap.parse_args(argv)

    cfg = cfgmod.SimlibConfig.load(args.config)
    out_dir = Path(args.out) if args.out else _paths.repo_root() / "data" / "simlib"

    try:
        if args.self_test:
            return self_test(cfg, out_dir)
        if not args.run or not args.strategy:
            ap.error("se requieren --run y --strategy (o usa --self-test)")
        return build(args.run, args.strategy, cfg, out_dir, args.limit, allow_login=args.allow_login)
    except RegistryError as exc:
        print(f"error de registro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
