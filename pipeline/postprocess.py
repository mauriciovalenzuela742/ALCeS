#!/usr/bin/env python3
"""
postprocess.py — CLI de la Capa 4.

Lee los FITS que genero snlc_sim (HEAD/PHOT) directo a DataFrames en memoria
y genera los 4 graficos de control de calidad del poster. NO convierte a
CSV/Parquet: los .FITS ya son la fuente de verdad del dataset, no hace falta
duplicarlos en otro formato.

    # post-procesar toda una campanha (multiples clases -> pesado, ver abajo):
    python -m pipeline.postprocess --campaign build/full_v5.3

    # post-procesar un solo GENVERSION (liviano, OK en login node):
    python -m pipeline.postprocess --genversion $SNDATA_ROOT/SIM/SNIa_WFD_baseline_v5.3.1_10yrs

    # self-test con datos sinteticos (sin FITS):
    python -m pipeline.postprocess --self-test

NOTA: `--campaign` sobre muchas clases (p.ej. full_v5.3, 84 GENVERSION) es
pesado (lee FITS grandes + matplotlib) y SOLO corre dentro de un job SLURM
— se niega a correr en el login node (ver pipeline.paths.require_slurm):
    sbatch slurm/run_pipeline_step.sbatch pipeline.postprocess --campaign build/full_v5.3
Para campanhas chicas (2-3 clases, p.ej. test_small) el propio README lo
documenta como aceptable en login: usa --allow-login para confirmarlo.
`--genversion` (una sola clase) nunca requiere el guardia.

Outputs por GENVERSION:
    qc/
        <gv>_qc_redshift.png
        <gv>_qc_magnitudes.png
        <gv>_qc_detections.png
        <gv>_qc_lightcurves.png
    postprocess_manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from pipeline.postproc import converter, qc
    from pipeline import paths as _paths
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.postproc import converter, qc
    from pipeline import paths as _paths


# ------------------------------------------------------------------ core
def process_genversion(
    gv_dir: str | Path,
    out_base: str | Path | None = None,
    *,
    skip_qc: bool = False,
) -> dict:
    """Lee los FITS de un GENVERSION en memoria y genera su QC."""
    gv_dir = Path(gv_dir)
    gv_name = gv_dir.name
    out_base = Path(out_base) if out_base else gv_dir

    print(f"  » procesando {gv_name}")

    # lectura FITS -> DataFrames en memoria
    result = converter.read_genversion(gv_dir)
    head_df = result.pop("head_df")
    phot_df = result.pop("phot_df")
    dump_df = result.pop("dump_df", None)
    print(f"    ✓ {result['n_objects']:,} objetos · {result['n_observations']:,} observaciones (desde FITS)")

    # QC
    qc_paths = {}
    if not skip_qc:
        qc_paths = qc.run_all_qc(head_df, phot_df, out_base / "qc", gv_name, dump_df=dump_df)
        qc_paths = {k: str(v) for k, v in qc_paths.items()}
        print(f"    ✓ {len(qc_paths)} graficos QC generados")

    result["qc"] = qc_paths
    result["genversion"] = gv_name
    return result


def process_campaign(
    build_dir: str | Path,
    *,
    sim_root: str | Path | None = None,
    out_base: str | Path | None = None,
    skip_qc: bool = False,
    allow_login: bool = False,
) -> dict:
    """Recorre una campanha compilada y post-procesa (QC) cada GENVERSION."""
    build_dir = Path(build_dir)
    manifest_path = build_dir / "campaign_manifest.json"
    if not manifest_path.exists():
        print(f"error: no existe {manifest_path}", file=sys.stderr)
        return {}

    manifest = json.loads(manifest_path.read_text())
    combos = manifest.get("combos", [])

    _paths.require_slurm(
        "postprocess --campaign (Capa 4)",
        f"sbatch slurm/run_pipeline_step.sbatch pipeline.postprocess --campaign {build_dir}",
        allow_flag=allow_login,
    )

    sim_root = Path(sim_root) if sim_root else Path(os.environ.get("SNDATA_ROOT", "")) / "SIM"
    out_base = Path(out_base) if out_base else build_dir / "postproc"

    results = []
    skipped = []
    for combo in combos:
        gv = combo["genversion"]
        gv_dir = sim_root / gv
        if not gv_dir.is_dir():
            skipped.append(gv)
            continue
        try:
            r = process_genversion(gv_dir, out_base / gv, skip_qc=skip_qc)
            results.append(r)
        except Exception as exc:
            print(f"    ✗ {gv}: {exc}")
            results.append({"genversion": gv, "error": str(exc)})

    if skipped:
        print(f"\n  ⚠ {len(skipped)} GENVERSION(s) no encontradas en {sim_root}")
        print(f"    (¿la simulacion ya termino? Verificar con --status)")

    # manifest de post-proceso
    pp_manifest = {
        "campaign": manifest.get("campaign", "?"),
        "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_processed": len([r for r in results if "error" not in r]),
        "n_errors": len([r for r in results if "error" in r]),
        "n_skipped": len(skipped),
        "skipped": skipped,
        "results": results,
    }
    out_base.mkdir(parents=True, exist_ok=True)
    mp = out_base / "postprocess_manifest.json"
    mp.write_text(json.dumps(pp_manifest, indent=2, default=str), encoding="utf-8")
    print(f"\n  ✓ manifiesto: {mp}")
    return pp_manifest


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    """Genera DataFrames sinteticos y corre conversion + QC completos."""
    import tempfile

    print("» self-test de la Capa 4 (datos sinteticos, sin FITS)")

    rng = np.random.default_rng(42)
    bands = list("ugrizY")
    n_obj = 30

    # head_df sintetico
    head_rows = []
    for i in range(n_obj):
        head_rows.append({
            "SNID": f"SN{i:04d}",
            "SNTYPE": rng.choice([1, 20, 30, 40]),
            "RA": rng.uniform(0, 360),
            "DEC": rng.uniform(-70, 20),
            "REDSHIFT_HELIO": rng.uniform(0.01, 1.2),
            "REDSHIFT_CMB": rng.uniform(0.01, 1.2),
            "MWEBV": rng.uniform(0.01, 0.1),
            "PEAKMJD": rng.uniform(61200, 62400),
            "NOBS": rng.integers(20, 100),
            "PTROBS_MIN": 0,   # not used in self-test
            "PTROBS_MAX": 0,
        })
    head_df = pd.DataFrame(head_rows)

    # phot_df sintetico
    phot_rows = []
    for i in range(n_obj):
        peak = head_df.iloc[i]["PEAKMJD"]
        nobs = int(head_df.iloc[i]["NOBS"])
        for j in range(nobs):
            mjd = peak + rng.uniform(-30, 80)
            b = rng.choice(bands)
            flux = max(1.0, rng.normal(500, 200))
            phot_rows.append({
                "SNID": f"SN{i:04d}",
                "MJD": mjd,
                "FLT": b,
                "FLUXCAL": flux,
                "FLUXCALERR": abs(rng.normal(20, 10)),
                "MAG": -2.5 * np.log10(flux) + 27.5,
                "MAGERR": rng.uniform(0.01, 0.3),
                "PHOTFLAG": 0,
            })
    phot_df = pd.DataFrame(phot_rows)

    print(f"  ✓ DataFrames sinteticos en memoria: {len(head_df)} objetos, {len(phot_df)} observaciones")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        out = tmp / "qc_test"

        # QC
        qc_paths = qc.run_all_qc(head_df, phot_df, out / "qc", "selftest")
        for name, path in qc_paths.items():
            exists = Path(path).exists()
            size_kb = Path(path).stat().st_size / 1024 if exists else 0
            print(f"  {'✓' if exists else '✗'} {name}: {Path(path).name} ({size_kb:.1f} KB)")

        all_ok = all(Path(p).exists() for p in qc_paths.values())
        print(f"\n  {'self-test OK ✓' if all_ok else 'FALLÓ ✗'}")
        return 0 if all_ok else 1


# ------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="postprocess",
        description="Capa 4 — post-proceso SNANA: FITS → QC (sin conversion a tablas).",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--campaign", metavar="BUILD_DIR",
                   help="post-procesa toda una campanha compilada (pesado, ver guardia SLURM)")
    g.add_argument("--genversion", metavar="GV_DIR",
                   help="post-procesa un solo directorio GENVERSION (liviano, OK en login)")
    g.add_argument("--self-test", action="store_true",
                   help="prueba sintetica sin FITS")
    ap.add_argument("--sim-root", help="raiz de los SIM outputs (por defecto $SNDATA_ROOT/SIM)")
    ap.add_argument("--out", help="directorio de salida")
    ap.add_argument("--skip-qc", action="store_true", help="solo lee/valida los FITS, sin graficos")
    ap.add_argument("--allow-login", action="store_true",
                     help="fuerza --campaign en el login node (excepcion, no la regla — ver README)")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return self_test()
        if args.genversion:
            r = process_genversion(args.genversion, args.out, skip_qc=args.skip_qc)
            print(json.dumps({k: v for k, v in r.items()
                              if k not in ("head_df", "phot_df")}, indent=2, default=str))
            return 0
        if args.campaign:
            process_campaign(args.campaign, sim_root=args.sim_root, out_base=args.out,
                             skip_qc=args.skip_qc, allow_login=args.allow_login)
            return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
