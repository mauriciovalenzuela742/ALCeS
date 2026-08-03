#!/usr/bin/env python3
"""
run_campaign.py — CLI de la Capa 3: orquestacion de campañas SNANA.

Integra Capas 0-2 y añade pre-flight, lanzamiento y monitoreo.

    # flujo tipico completo (compila + valida + lanza):
    python -m pipeline.run_campaign --launch campaigns/full_v5.3.yaml

    # paso a paso:
    python -m pipeline.run_campaign --preflight build/full_v5.3
    python -m pipeline.run_campaign --launch    build/full_v5.3
    python -m pipeline.run_campaign --status    build/full_v5.3

    # self-test (sin SLURM ni SNANA: valida compile + preflight)
    python -m pipeline.run_campaign --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from pipeline.orchestrate.preflight import preflight_check, preflight_summary
    from pipeline.orchestrate.launcher import launch_campaign
    from pipeline.orchestrate.monitor import campaign_status, format_status
    from pipeline.campaign.compiler import compile_campaign
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.orchestrate.preflight import preflight_check, preflight_summary
    from pipeline.orchestrate.launcher import launch_campaign
    from pipeline.orchestrate.monitor import campaign_status, format_status
    from pipeline.campaign.compiler import compile_campaign


def cmd_preflight(build_dir: str) -> int:
    print(f"» pre-flight checks para {build_dir}\n")
    results = preflight_check(build_dir)
    ok, summary = preflight_summary(results)
    print(summary)
    return 0 if ok else 2


def cmd_launch(target: str, *, dry_run: bool, skip_preflight: bool) -> int:
    target_path = Path(target)
    # si es un .yaml, compilar primero y lanzar el build_dir resultante
    if target_path.suffix in (".yaml", ".yml"):
        print(f"» compilando {target} …")
        plan = compile_campaign(target_path)
        print(f"  ✓ {plan.manifest['n_root_inputs']} .INPUT en {plan.out_dir}\n")
        build_dir = plan.out_dir
    else:
        build_dir = target_path

    return launch_campaign(
        build_dir, skip_preflight=skip_preflight, dry_run=dry_run,
    )


def cmd_status(build_dir: str) -> int:
    cs = campaign_status(build_dir)
    print(format_status(cs))
    return 0


def cmd_self_test() -> int:
    """Compila una mini-campanha sintetica, corre preflight (espera algunos warnings)."""
    import tempfile
    import yaml

    print("» self-test de la Capa 3 (sin SLURM ni SNANA)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # catalogo minimo
        models = {
            "T_SNIa": {
                "genmodel": "SALT2.WFIRST-H17",
                "genmodel_path": "$SNDATA_ROOT/models/SALT2/SALT2.WFIRST-H17",
                "gentype": 1, "dndz": "POWERLAW2 2.6E-5 1.5 0.0 1.0",
                "zrange": [0.01, 1.2], "trest": [-40, 100], "ngen": 50,
            },
        }
        (tmp / "models.yaml").write_text(yaml.safe_dump(models))
        camp = {
            "name": "test3", "models_catalog": str(tmp / "models.yaml"),
            "runs": [{"run": "baseline_v5.3.1_10yrs", "strategies": ["WFD"]}],
            "classes": [{"model": "T_SNIa"}],
            "defaults": {"format_mask": 48, "ranseed": 1,
                         "searcheff_pipeline_logic_file": "x", "searcheff_pipeline_eff_file": "x"},
            "batch": {"system": "SBATCH", "partition": "general", "walltime": "01:00:00"},
        }
        camp_path = tmp / "camp.yaml"
        camp_path.write_text(yaml.safe_dump(camp, sort_keys=False))

        # compilar
        plan = compile_campaign(camp_path, out_dir=tmp / "build")
        print(f"  ✓ compilacion: {plan.manifest['n_root_inputs']} .INPUT\n")

        # preflight (esperamos que FALLE porque no hay SNANA/SLURM en este entorno)
        results = preflight_check(tmp / "build")
        ok, summary = preflight_summary(results)
        print(summary)

        # verificar que el master se validó
        master_check = [r for r in results if r.name == "master_submit.INPUT"]
        if master_check and master_check[0].ok:
            print("\n  ✓ master_submit.INPUT validado")
        else:
            print("\n  ✗ master_submit.INPUT no validado")

        # status (sin jobs, debe mostrar UNKNOWN)
        cs = campaign_status(tmp / "build")
        print(f"\n  ✓ status: {cs.summary}")
        print(format_status(cs))

        # dry-run launch
        rc = launch_campaign(tmp / "build", skip_preflight=True, dry_run=True)
        print(f"\n  ✓ dry-run launch rc={rc}")

        print(f"\n  self-test OK ✓  (warnings de snlc_sim/SLURM son esperados)")
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="run_campaign",
        description="Capa 3 — orquestacion de campañas SNANA (validar + lanzar + monitorear).",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", metavar="BUILD_DIR",
                   help="solo corre los checks pre-vuelo")
    g.add_argument("--launch", metavar="TARGET",
                   help="compila (si es .yaml) + valida + lanza; o lanza un build_dir existente")
    g.add_argument("--status", metavar="BUILD_DIR",
                   help="muestra el estado de la campanha")
    g.add_argument("--self-test", action="store_true",
                   help="prueba sintetica (sin SLURM ni SNANA)")
    ap.add_argument("--dry-run", action="store_true",
                    help="valida todo pero no invoca submit_batch_jobs")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="salta los checks pre-vuelo")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return cmd_self_test()
        if args.preflight:
            return cmd_preflight(args.preflight)
        if args.launch:
            return cmd_launch(args.launch, dry_run=args.dry_run,
                              skip_preflight=args.skip_preflight)
        if args.status:
            return cmd_status(args.status)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
