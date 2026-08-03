#!/usr/bin/env python3
"""
compile_campaign.py — CLI de la Capa 2.

Expande un campaign.yaml en un arbol completo de archivos .INPUT listos para
SNANA (separando survey-includes de model-includes via INPUT_INCLUDE_FILE),
mas UN SCRIPT SLURM POR GENVERSION que invoca snlc_sim.exe directamente
(patron probado: run_<CLASE>_<fecha>.sh, sin depender de submit_batch_jobs.sh).

    python -m pipeline.compile_campaign --config campaigns/full_v5.3.yaml
    python -m pipeline.compile_campaign --config campaigns/full_v5.3.yaml --out build/test --dry-run
    python -m pipeline.compile_campaign --self-test

Genera:
    build/<campaign>/
    ├── includes/
    │   ├── include_survey_WFD_baseline_v5.3.1_10yrs.INPUT
    │   ├── include_model_SNIa.INPUT
    │   └── ...
    ├── sim_SNIa_WFD_baseline_v5.3.1_10yrs.INPUT
    ├── ...
    ├── slurm/
    │   ├── run_SNIa_WFD_baseline_v5.3.1_10yrs.sh
    │   └── ...
    ├── submit_all.sh
    └── campaign_manifest.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from pipeline.campaign.compiler import compile_campaign, CampaignPlan, CampaignError
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.campaign.compiler import compile_campaign, CampaignPlan, CampaignError


def _print_plan(plan: CampaignPlan) -> None:
    m = plan.manifest
    print(f"  campanha:           {m['campaign']}")
    print(f"  descripcion:        {m.get('description', '')}")
    print(f"  survey includes:    {m['n_survey_includes']}")
    print(f"  model includes:     {m['n_model_includes']}")
    print(f"  root .INPUT:        {m['n_root_inputs']}")

    from collections import Counter
    strats = Counter((c["run"], c["strategy"]) for c in m["combos"])
    for (run, strat), n in sorted(strats.items()):
        print(f"    {strat:>4} × {run}: {n} clases")
    print(f"  salida:             {plan.out_dir}")
    print(f"  scripts SLURM:      {len(plan.slurm_scripts)}")
    if plan.submit_all:
        print(f"  lanzador:           {plan.submit_all.name}")


def cmd_compile(args: argparse.Namespace) -> int:
    plan = compile_campaign(
        args.config, out_dir=args.out, dry_run=args.dry_run,
    )
    print(f"» {'dry-run' if args.dry_run else 'compilado'}")
    _print_plan(plan)
    if not args.dry_run:
        print(f"\n  ✓ {len(plan.root_inputs)} archivos .INPUT generados")
        print(f"  siguiente paso:  python -m pipeline.run_campaign --launch {plan.out_dir}")
    return 0


def cmd_self_test() -> int:
    """Compilacion de prueba con un campaign.yaml minimalista sintetico."""
    import tempfile

    print("» self-test de la Capa 2 (compilacion sintetica)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        models = {
            "TestSNIa": {
                "genmodel": "SALT2.WFIRST-H17",
                "genmodel_path": "$SNDATA_ROOT/models/SALT2/SALT2.WFIRST-H17",
                "gentype": 1,
                "dndz": "POWERLAW2  2.6E-5  1.5  0.0  1.0",
                "zrange": [0.01, 1.2],
                "trest": [-40, 100],
                "ngen": 100,
            },
            "TestSNII": {
                "genmodel": "NON1ASED",
                "genmodel_path": "$SNDATA_ROOT/snsed/NON1ASED.SNII-Templates",
                "gentype": 20,
                "dndz": "POWERLAW2  1.0E-4  1.5  0.0  1.0",
                "zrange": [0.01, 0.8],
                "trest": [-20, 200],
                "ngen": 200,
            },
        }
        models_path = tmp / "test_models.yaml"
        import yaml
        models_path.write_text(yaml.safe_dump(models), encoding="utf-8")

        camp = {
            "name": "selftest",
            "description": "Compilacion de prueba automatizada",
            "models_catalog": str(models_path),
            "runs": [
                {"run": "baseline_v5.3.1_10yrs", "strategies": ["WFD", "DDF"]},
            ],
            "classes": [
                {"model": "TestSNIa"},
                {"model": "TestSNII", "ngen": 500},
            ],
            "defaults": {
                "format_mask": 32,
                "ranseed": 12345,
                "kcor_file": "kcor_LSST.fits",
                "searcheff_pipeline_file": "LSST_SEARCHEFF_PIPELINE.DAT",
                "searcheff_pipeline_logic_file": "LSST_PIPELINE_LOGIC.DAT",
            },
            "batch": {
                "partition": "general",
                "walltime": "02:00:00",
                "mem_per_cpu": 2000,
            },
        }
        camp_path = tmp / "test_campaign.yaml"
        camp_path.write_text(yaml.safe_dump(camp, sort_keys=False), encoding="utf-8")

        plan = compile_campaign(camp_path, out_dir=tmp / "build")
        _print_plan(plan)

        ok = True
        n = plan.manifest["n_root_inputs"]
        if n != 4:
            print(f"  ✗ esperados 4 root .INPUT, obtuve {n}")
            ok = False
        else:
            print(f"  ✓ 4 root .INPUT (1 run × 2 estrategias × 2 clases)")

        si = plan.manifest["n_survey_includes"]
        if si != 2:
            print(f"  ✗ esperados 2 survey includes, obtuve {si}")
            ok = False
        else:
            print(f"  ✓ 2 survey includes (WFD + DDF)")

        mi = plan.manifest["n_model_includes"]
        if mi != 2:
            print(f"  ✗ esperados 2 model includes, obtuve {mi}")
            ok = False
        else:
            print(f"  ✓ 2 model includes (TestSNIa + TestSNII)")

        sample = plan.root_inputs[0]
        txt = sample.read_text()
        if "INPUT_INCLUDE_FILE" not in txt or "NGENTOT_LC" not in txt:
            print(f"  ✗ root .INPUT no tiene INPUT_INCLUDE_FILE/NGENTOT_LC (claves reales SNANA)")
            ok = False
        else:
            print(f"  ✓ root .INPUT usa INPUT_INCLUDE_FILE + NGENTOT_LC (confirmado contra .input real)")

        combo_snii_ddf = [c for c in plan.manifest["combos"]
                          if c["model"] == "TestSNII" and c["strategy"] == "DDF"]
        if combo_snii_ddf and combo_snii_ddf[0]["ngen"] == 500:
            print(f"  ✓ override ngen=500 para TestSNII (campaign.yaml)")
        elif combo_snii_ddf:
            print(f"  ✗ ngen override no funciono: {combo_snii_ddf[0]['ngen']}")
            ok = False

        n_scripts = len(plan.slurm_scripts)
        if n_scripts != 4:
            print(f"  ✗ esperados 4 scripts SLURM, obtuve {n_scripts}")
            ok = False
        else:
            print(f"  ✓ 4 scripts SLURM (uno por GENVERSION)")

        sh = plan.slurm_scripts[0]
        sh_txt = sh.read_text() if sh.exists() else ""
        if "#SBATCH" in sh_txt and "snlc_sim.exe" in sh_txt:
            print(f"  ✓ script SLURM invoca snlc_sim.exe directamente (patron probado)")
        else:
            print(f"  ✗ script SLURM malformado")
            ok = False

        if plan.submit_all and plan.submit_all.exists():
            print(f"  ✓ submit_all.sh generado")
        else:
            print(f"  ✗ submit_all.sh no generado")
            ok = False

        print(f"\n  {'self-test OK ✓' if ok else 'FALLÓ ✗'}")
        return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="compile_campaign",
        description="Capa 2 — compilador de campanha SNANA.",
    )
    ap.add_argument("--config", help="ruta a campaign.yaml")
    ap.add_argument("--out", help="directorio de salida (por defecto build/<name>)")
    ap.add_argument("--dry-run", action="store_true", help="solo calcula, no escribe")
    ap.add_argument("--self-test", action="store_true", help="compilacion de prueba sintetica")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return cmd_self_test()
        if not args.config:
            ap.error("se requiere --config (o usa --self-test)")
        return cmd_compile(args)
    except CampaignError as exc:
        print(f"error de campanha: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
