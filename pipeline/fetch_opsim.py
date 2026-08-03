#!/usr/bin/env python3
"""
fetch_opsim.py — CLI de la Capa 0.

Descarga y verifica bases OpSim declaradas en pipeline/opsims.yaml. Uso:

    python -m pipeline.fetch_opsim --list
    python -m pipeline.fetch_opsim --url    baseline_v5.3.1_10yrs
    python -m pipeline.fetch_opsim --run    baseline_v5.3.1_10yrs
    python -m pipeline.fetch_opsim --run    baseline_v5.3.1_10yrs --skip-existing
    python -m pipeline.fetch_opsim --verify baseline_v5.3.1_10yrs
    python -m pipeline.fetch_opsim --all                 # todas las 'verified'
    python -m pipeline.fetch_opsim --all --skip-existing # no re-verifica las ya descargadas
    python -m pipeline.fetch_opsim --add 5.3 ddf_sd ddf_sd_v5.3.1_10yrs.db \\
                                   --label "DDF short-deep" --status registered

Tambien corre como script suelto:  python pipeline/fetch_opsim.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- import robusto: funciona como modulo (-m pipeline...) y como script suelto ---
try:
    from pipeline.registry import Registry, RegistryError, OpSimRun, sha256_of
    from pipeline import paths as _paths
except ImportError:  # ejecucion directa: agrega el dir del repo al path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.registry import Registry, RegistryError, OpSimRun, sha256_of
    from pipeline import paths as _paths

import requests

# tqdm es opcional (en NLHPC viene con rubin_sim). Fallback silencioso.
try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

_CHUNK = 1 << 20  # 1 MiB


# ============================================================== descarga
def _download(url: str, dest: Path, *, force: bool = False) -> Path:
    """Descarga `url` a `dest` con reanudacion (HTTP Range) y barra de progreso.

    Escribe primero en `<dest>.part` y renombra al final (descarga atomica).
    """
    part = dest.with_suffix(dest.suffix + ".part")
    if dest.exists() and not force:
        print(f"  ya existe: {dest.name} (usa --force para re-descargar)")
        return dest

    resume_from = part.stat().st_size if part.exists() and not force else 0
    if force and part.exists():
        part.unlink()
        resume_from = 0

    headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
    with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
        if resume_from and resp.status_code == 200:
            # el servidor ignoro el Range: reiniciamos desde cero
            resume_from = 0
            part.unlink(missing_ok=True)
        elif resume_from and resp.status_code != 206:
            resp.raise_for_status()
        else:
            resp.raise_for_status()

        total = int(resp.headers.get("Content-Length", 0)) + resume_from
        mode = "ab" if resume_from else "wb"
        bar = _make_bar(total, resume_from, dest.name)
        with open(part, mode) as fh:
            for block in resp.iter_content(chunk_size=_CHUNK):
                if not block:
                    continue
                fh.write(block)
                if bar is not None:
                    bar.update(len(block))
        if bar is not None:
            bar.close()

    part.replace(dest)
    return dest


def _make_bar(total: int, initial: int, desc: str):
    if tqdm is not None and total:
        return tqdm(total=total, initial=initial, unit="B", unit_scale=True,
                    unit_divisor=1024, desc=f"  {desc}")
    return None  # sin tqdm: sin barra (la descarga igual funciona)


def _write_provenance(run: OpSimRun, dest: Path, url: str, digest: str) -> Path:
    prov = {
        "run": run.name,
        "filename": run.filename,
        "url": url,
        "release": run.release,
        "family": run.family,
        "sha256": digest,
        "size_bytes": dest.stat().st_size,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "fetch_opsim.py",
    }
    side = dest.with_suffix(dest.suffix + ".provenance.json")
    side.write_text(json.dumps(prov, indent=2), encoding="utf-8")
    return side


# ============================================================== comandos
def cmd_list(reg: Registry) -> int:
    rows = []
    for r in reg:
        state = "✓ local" if reg.is_downloaded(r.name) else "—"
        rows.append((r.name, r.release, r.family, r.status, state))
    if not rows:
        print("(registro vacio)")
        return 0
    widths = [max(len(str(row[i])) for row in [("NAME", "REL", "FAMILY", "STATUS", "LOCAL")] + rows)
              for i in range(5)]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format("NAME", "REL", "FAMILY", "STATUS", "LOCAL"))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*row))
    print(f"\n  data_dir: {reg.data_dir()}")
    return 0


def cmd_url(reg: Registry, name: str) -> int:
    print(reg.url_for(name))
    return 0


def cmd_run(reg: Registry, name: str, *, force: bool, skip_existing: bool = False) -> int:
    run = reg.get(name)
    url = reg.url_for(name)
    dest = reg.local_path(name)

    if skip_existing and dest.exists() and not force:
        size = dest.stat().st_size
        print(f"» {name}\n  ↷ omitido: ya existe en {dest} ({size:,} B) "
              f"— no se recalcula sha256 (usa --force para re-verificar)")
        return 0

    print(f"» {name}\n  url:  {url}\n  dest: {dest}")
    _download(url, dest, force=force)

    if run.size_bytes:
        actual = dest.stat().st_size
        if actual != run.size_bytes:
            print(f"  ⚠ tamanho no coincide con el indice: "
                  f"esperado {run.size_bytes:,} B, obtenido {actual:,} B "
                  f"(el archivo pudo actualizarse en S3DF)")
        else:
            print(f"  ✓ tamanho coincide con el indice ({actual:,} B)")

    digest = sha256_of(dest)
    if run.sha256:
        if digest != run.sha256:
            print(f"  ✗ CHECKSUM NO COINCIDE\n    esperado: {run.sha256}\n    obtenido: {digest}")
            return 2
        print("  ✓ sha256 verificado contra el valor fijado en opsims.yaml")
    else:
        reg.record_sha256(name, digest)
        print(f"  ✓ sha256 registrado (opsims.local.yaml): {digest[:16]}…")

    side = _write_provenance(run, dest, url, digest)
    print(f"  ✓ procedencia: {side.name}")
    if run.n_obs:
        print(f"  i sanity: se esperan ~{run.n_obs:,} observaciones (chequear en Capa 1)")
    return 0


def cmd_all(reg: Registry, *, force: bool, skip_existing: bool = False) -> int:
    targets = [r.name for r in reg if r.status == "verified"]
    if not targets:
        print("no hay runs con status 'verified'")
        return 0
    print(f"descargando {len(targets)} run(s) verificadas: {', '.join(targets)}\n")
    rc = 0
    for name in targets:
        rc |= cmd_run(reg, name, force=force, skip_existing=skip_existing)
        print()
    return rc


def cmd_verify(reg: Registry, name: str) -> int:
    run = reg.get(name)
    dest = reg.local_path(name)
    if not dest.exists():
        print(f"✗ {name}: no descargado ({dest})")
        return 2
    digest = sha256_of(dest)
    expected = run.sha256
    if not expected:
        print(f"i {name}: no hay sha256 de referencia; observado = {digest}")
        reg.record_sha256(name, digest)
        return 0
    ok = digest == expected
    print(("✓" if ok else "✗") + f" {name}: {'coincide' if ok else 'NO COINCIDE'}")
    if not ok:
        print(f"    esperado: {expected}\n    obtenido: {digest}")
    return 0 if ok else 2


def cmd_add(reg: Registry, args: argparse.Namespace) -> int:
    spec = {
        "release": args.release,
        "family": args.family,
        "filename": args.filename,
        "status": args.status,
    }
    if args.label:
        spec["label"] = args.label
    if args.survey_years:
        spec["survey_years"] = args.survey_years
    run = reg.add_run(args.name or _name_from_filename(args.filename), spec)
    print(f"✓ registrada '{run.name}' en opsims.local.yaml")
    print(f"  url: {run.url(reg.s3df_base)}")
    print("  (para hacerla oficial, muevela a pipeline/opsims.yaml)")
    return 0


def _name_from_filename(filename: str) -> str:
    return filename[:-3] if filename.endswith(".db") else filename


# ============================================================== main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fetch_opsim",
        description="Capa 0 — registro y descarga de bases OpSim (Vera C. Rubin).",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="lista las runs del registro")
    g.add_argument("--url", metavar="NAME", help="imprime la URL de descarga")
    g.add_argument("--run", metavar="NAME", help="descarga y verifica una run")
    g.add_argument("--all", action="store_true", help="descarga todas las 'verified'")
    g.add_argument("--verify", metavar="NAME", help="verifica el sha256 de una run local")
    g.add_argument("--add", nargs=3, metavar=("RELEASE", "FAMILY", "FILENAME"),
                   help="registra una run nueva (en opsims.local.yaml)")

    p.add_argument("--force", action="store_true", help="re-descarga aunque exista")
    p.add_argument("--skip-existing", action="store_true", dest="skip_existing",
                   help="si el .db ya existe en disco, no reintenta descargarlo ni "
                        "recalcula su sha256 (salida inmediata, util para --all)")
    # opciones para --add
    p.add_argument("--name", help="nombre de la run (por defecto se deriva del filename)")
    p.add_argument("--label", help="etiqueta legible (para --add)")
    p.add_argument("--status", default="registered",
                   choices=["verified", "registered", "archived"], help="estado (para --add)")
    p.add_argument("--survey-years", type=int, dest="survey_years", help="anhos de survey (para --add)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reg = Registry.load()
        if args.list:
            return cmd_list(reg)
        if args.url:
            return cmd_url(reg, args.url)
        if args.run:
            return cmd_run(reg, args.run, force=args.force, skip_existing=args.skip_existing)
        if args.all:
            return cmd_all(reg, force=args.force, skip_existing=args.skip_existing)
        if args.verify:
            return cmd_verify(reg, args.verify)
        if args.add:
            args.release, args.family, args.filename = args.add
            return cmd_add(reg, args)
    except RegistryError as exc:
        print(f"error de registro: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"error de descarga: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())