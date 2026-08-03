#!/usr/bin/env python3
"""
tag_campaign.py — CLI de la Capa 5: procedencia y reproducibilidad.

Genera un tag de procedencia por GENVERSION y un manifiesto consolidado.

    python -m pipeline.tag_campaign --campaign build/full_v5.3
    python -m pipeline.tag_campaign --self-test

Cada tag contiene:
    - version OpSim (release, filename, sha256)
    - version SNANA
    - hash combinado de los configs (campaign.yaml + models.yaml + simlib.yaml)
    - hash del .INPUT raiz
    - timestamps de simulacion y post-proceso
    - inventario de inputs/outputs
    - snapshot del entorno (Python, OS, paquetes)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

try:
    from pipeline.provenance.tagger import (
        collect_campaign_tags, save_campaign_manifest, tag_run, RunTag,
    )
    from pipeline.provenance.environment import capture_environment
    from pipeline.campaign.compiler import compile_campaign
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.provenance.tagger import (
        collect_campaign_tags, save_campaign_manifest, tag_run, RunTag,
    )
    from pipeline.provenance.environment import capture_environment
    from pipeline.campaign.compiler import compile_campaign


def cmd_tag(build_dir: str, postproc_dir: str | None, out: str | None) -> int:
    build_dir = Path(build_dir)
    if not build_dir.exists():
        print(f"error: {build_dir} no existe", file=sys.stderr)
        return 2

    print(f"» generando tags de procedencia para {build_dir.name}")
    tags = collect_campaign_tags(build_dir, postproc_dir=postproc_dir)
    if not tags:
        print("  (no se encontraron GENVERSION — ¿falta campaign_manifest.json?)")
        return 1

    # guardar tag individual por GENVERSION
    tags_dir = Path(out) if out else build_dir / "provenance"
    for tag in tags:
        p = tag.save(tags_dir / f"{tag.genversion}.provenance.json")

    # manifiesto consolidado
    manifest_path = save_campaign_manifest(tags, tags_dir / "PROVENANCE_MANIFEST.json")

    print(f"  ✓ {len(tags)} tags generados en {tags_dir}")
    print(f"  ✓ manifiesto: {manifest_path.name}")

    # resumen
    print(f"\n  {'GENVERSION':<55} {'OpSim':>8} {'config':>10} {'input':>10}")
    print(f"  {'-'*85}")
    for t in tags[:10]:
        print(f"  {t.genversion:<55} {t.opsim_release or '—':>8} "
              f"{t.config_hash[:8] or '—':>10} {t.input_hash[:8] or '—':>10}")
    if len(tags) > 10:
        print(f"  … y {len(tags) - 10} mas")
    return 0


def cmd_self_test() -> int:
    """Self-test: compila mini-campanha y genera tags."""
    import yaml

    print("» self-test de la Capa 5 (procedencia sintetica)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        models = {
            "T_SNIa": {
                "genmodel": "SALT2.WFIRST-H17",
                "genmodel_path": "$SNDATA_ROOT/models/SALT2/SALT2.WFIRST-H17",
                "gentype": 1, "dndz": "POWERLAW2 2.6E-5 1.5 0.0 1.0",
                "zrange": [0.01, 1.2], "trest": [-40, 100], "ngen": 50,
            },
            "T_SNII": {
                "genmodel": "NON1ASED",
                "genmodel_path": "$SNDATA_ROOT/snsed/NON1ASED.SNII",
                "input_include": "$SNDATA_ROOT/snsed/NON1ASED.SNII/SIMGEN_INCLUDE.INPUT",
                "gentype": 20, "dndz": "POWERLAW2 1e-4 1.5 0.0 1.0",
                "zrange": [0.01, 0.8], "trest": [-20, 200], "ngen": 100,
            },
        }
        (tmp / "models.yaml").write_text(yaml.safe_dump(models))
        camp = {
            "name": "test5", "models_catalog": str(tmp / "models.yaml"),
            "runs": [{"run": "baseline_v5.3.1_10yrs", "strategies": ["WFD", "DDF"]}],
            "classes": [{"model": "T_SNIa"}, {"model": "T_SNII"}],
            "defaults": {"format_mask": 48, "ranseed": 1,
                         "searcheff_pipeline_logic_file": "x", "searcheff_pipeline_eff_file": "x"},
            "batch": {"system": "SBATCH", "partition": "general", "walltime": "01:00:00"},
        }
        camp_path = tmp / "camp.yaml"
        camp_path.write_text(yaml.safe_dump(camp, sort_keys=False))

        plan = compile_campaign(camp_path, out_dir=tmp / "build")
        print(f"  ✓ compilacion: {plan.manifest['n_root_inputs']} .INPUT")

        tags = collect_campaign_tags(tmp / "build")
        print(f"  ✓ {len(tags)} tags generados")

        # verificaciones
        ok = True
        if len(tags) != 4:
            print(f"  ✗ esperados 4 tags, obtuve {len(tags)}")
            ok = False
        else:
            print(f"  ✓ 4 tags (2 clases × 2 estrategias)")

        t0 = tags[0]
        if t0.tagged_at and t0.input_hash:
            print(f"  ✓ tag[0]: tagged_at={t0.tagged_at}, input_hash={t0.input_hash[:16]}…")
        else:
            print(f"  ✗ tag[0] incompleto")
            ok = False

        if t0.environment.get("python"):
            print(f"  ✓ entorno capturado (Python {t0.environment['python'][:10]}…)")
        else:
            print(f"  ✗ entorno no capturado")
            ok = False

        manifest_path = save_campaign_manifest(tags, tmp / "build" / "provenance" / "PROVENANCE_MANIFEST.json")
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text())
            print(f"  ✓ manifiesto: {data['n_runs']} runs, version {data['provenance_version']}")
        else:
            print(f"  ✗ manifiesto no generado")
            ok = False

        print(f"\n  {'self-test OK ✓' if ok else 'FALLÓ ✗'}")
        return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tag_campaign",
        description="Capa 5 — procedencia y reproducibilidad.",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--campaign", metavar="BUILD_DIR",
                   help="genera tags para toda una campanha compilada")
    g.add_argument("--self-test", action="store_true",
                   help="prueba sintetica")
    ap.add_argument("--postproc-dir", help="directorio de post-proceso (Capa 4)")
    ap.add_argument("--out", help="directorio de salida para los tags")
    args = ap.parse_args(argv)

    try:
        if args.self_test:
            return cmd_self_test()
        return cmd_tag(args.campaign, args.postproc_dir, args.out)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
