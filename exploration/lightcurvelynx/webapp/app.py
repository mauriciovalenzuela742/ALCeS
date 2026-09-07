"""
Fase 83: "el boton" que pidio el profesor -- una app web local (Flask)
que corre en la propia maquina donde se instalo el proyecto (ver
HOWTO_LOCAL.md), con un formulario real para generar/lanzar sweeps sin
tocar la terminal.

`docs/index.html` (el dashboard publicado) se descarto a proposito como
vehiculo para esto -- es una pagina 100% estatica en GitHub Pages, sin
capacidad de ejecutar nada del lado servidor. Esta app es un vehiculo
nuevo, deliberadamente separado, que SI puede correr codigo real.

Todas las rutas importan directo las funciones ya existentes de
sweep_*.py -- nunca subprocess/shell-out. `run_hash.json` (via
sweep_monitor.monitor_sweep) sigue siendo la unica fuente de verdad de
estado -- no se inventa un mecanismo de estado nuevo. El unico estado en
memoria del proceso Flask (`RUNNING`) es apenas un guard para no lanzar el
mismo sweep dos veces en paralelo -- no es fuente de verdad.

Un solo usuario local, sin despliegue multiusuario: host="127.0.0.1"
siempre, nunca "0.0.0.0" (ver HOWTO_WEBAPP.md, Fase 85).

Uso:
    cd exploration/lightcurvelynx
    module load python/3.12.3-legacy-skylake && source venv/bin/activate   # NLHPC
    # o el venv local equivalente (ver HOWTO_LOCAL.md)
    python3 webapp/app.py
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

WEBAPP_DIR = Path(__file__).resolve().parent
LCL_DIR = WEBAPP_DIR.parent
sys.path.insert(0, str(LCL_DIR))

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, url_for

import pandas as pd

import sweep_aggregate
import sweep_compile
import sweep_generate
import sweep_history
import sweep_monitor
import sweep_publish_dataset
import sweep_run_local
from sweep_compile import SWEEP_RUNS_DIR
from sweep_publish_dataset import DATASETS_DIR

app = Flask(__name__)
app.secret_key = "lightcurvelynx-webapp-local"  # solo para flash() -- app local, sin sesiones reales

# Guard en memoria para no lanzar el mismo sweep 2 veces en paralelo -- NO
# es fuente de verdad de estado (esa sigue siendo run_hash.json via
# sweep_monitor.monitor_sweep). Se pierde al reiniciar el proceso, y eso
# esta bien: si el proceso Flask murio, el hilo de ejecucion tambien.
RUNNING: dict[str, threading.Thread] = {}


@app.route("/")
def index():
    return render_template("index.html", classes=sweep_generate.available_classes())


@app.route("/generate", methods=["POST"])
def generate():
    form = request.form
    classes = form.getlist("classes")
    try:
        seeds = [int(s.strip()) for s in form.get("seeds", "0").split(",") if s.strip()]
    except ValueError:
        flash("semillas invalidas -- deben ser numeros separados por coma (p.ej. '0,1,2')")
        return redirect(url_for("index"))

    ngentot_overrides = {}
    for class_key in classes:
        raw = form.get(f"ngentot_{class_key}", "").strip()
        if raw:
            try:
                ngentot_overrides[class_key] = int(raw)
            except ValueError:
                flash(f"ngentot invalido para '{class_key}': '{raw}'")
                return redirect(url_for("index"))

    # DDF y WFD son casillas independientes -- marcar las dos genera un
    # `mode` por cada una en el mismo sweep (sweep_compile.py::build_runs()
    # ya itera sobre una lista de modos, esto no es una capacidad nueva,
    # solo se estaba exponiendo como un solo toggle antes).
    modes = []
    if "mode_ddf" in form:
        modes.append({"wfd": False, "simsed_t0_mode": "bolometric_peak"})
    if "mode_wfd" in form:
        modes.append({"wfd": True, "simsed_t0_mode": "bolometric_peak"})
    if not modes:
        flash("elegir al menos una estrategia -- DDF, WFD, o ambas")
        return redirect(url_for("index"))

    # Fase 84: seccion "avanzado" del formulario -- mismos campos y mismos
    # defaults que generate_sweep() ya usa internamente si se omiten, asi
    # que el formulario nunca envia algo mas restrictivo de lo que el YAML
    # tendria por default (ver sweep_generate.py).
    try:
        cpus = int(form.get("cpus") or 2)
        max_conc = int(form.get("max_concurrent") or 2)
    except ValueError:
        flash("valores de 'CPUs' o 'Máx. en paralelo' invalidos -- deben ser numeros enteros")
        return redirect(url_for("index"))
    resources = {
        "default": {"mem": form.get("mem") or "8G", "time": form.get("time") or "00:15:00", "cpus": cpus},
        "overrides": {},
    }
    max_concurrent = {"default": max_conc}

    try:
        yaml_path = sweep_generate.generate_sweep(
            sweep_name=form.get("sweep_name", ""),
            classes=classes,
            seeds=seeds,
            ngentot_overrides=ngentot_overrides,
            modes=modes,
            resources=resources,
            max_concurrent=max_concurrent,
            keep_phot="keep_phot" in form,
            description=form.get("description", ""),
            triggered_by="webapp",
        )
    except (ValueError, FileExistsError) as e:
        flash(str(e))
        return redirect(url_for("index"))

    sweep_compile.compile_sweep(yaml_path, triggered_by="webapp")
    return redirect(url_for("sweep_status", name=form.get("sweep_name")))


@app.route("/sweep/<name>")
def sweep_status(name):
    manifest_path = SWEEP_RUNS_DIR / name / "manifest.json"
    if not manifest_path.exists():
        flash(f"'{name}' no tiene manifiesto compilado todavia")
        return redirect(url_for("index"))
    yaml_path = sweep_generate.SWEEPS_DIR / f"{name}.yaml"
    rows = sweep_monitor.monitor_sweep(name)
    all_done = bool(rows) and all(r["status"] == "done" for r in rows)
    agg_path = SWEEP_RUNS_DIR / name / "aggregated_summary.parquet"

    # Fase 83: los nombres de archivo de QC son dinamicos (prefijo real
    # "LightCurveLynx_<clase>_<WFD|DDF>_poc_qc_*.png", ver
    # pipeline/postproc/qc.py::run_all_qc + run_simsed_poc.py) -- se listan
    # los .png reales en vez de adivinar un nombre fijo.
    for r in rows:
        qc_dir = SWEEP_RUNS_DIR / name / "runs" / r["run_hash"] / "qc"
        r["qc_files"] = sorted(p.name for p in qc_dir.glob("*.png")) if qc_dir.is_dir() else []

    return render_template(
        "sweep_status.html", name=name, rows=rows, all_done=all_done,
        running=name in RUNNING and RUNNING[name].is_alive(),
        yaml_text=yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else "",
        aggregated=agg_path.exists(),
    )


@app.route("/sweep/<name>/run", methods=["POST"])
def sweep_run(name):
    if name in RUNNING and RUNNING[name].is_alive():
        flash(f"'{name}' ya esta corriendo -- no se lanza dos veces en paralelo")
        return redirect(url_for("sweep_status", name=name))

    yaml_path = sweep_generate.SWEEPS_DIR / f"{name}.yaml"
    workers = request.form.get("workers", "").strip()
    workers_override = int(workers) if workers.isdigit() else None

    def _run():
        sweep_run_local.run_sweep_local(yaml_path, workers_override=workers_override, triggered_by="webapp")

    thread = threading.Thread(target=_run, daemon=True)
    RUNNING[name] = thread
    thread.start()
    flash(f"'{name}' lanzado en segundo plano -- el estado se actualiza abajo")
    return redirect(url_for("sweep_status", name=name))


@app.route("/sweep/<name>/status")
def sweep_status_json(name):
    rows = sweep_monitor.monitor_sweep(name)
    for r in rows:
        qc_dir = SWEEP_RUNS_DIR / name / "runs" / r["run_hash"] / "qc"
        r["qc_files"] = sorted(p.name for p in qc_dir.glob("*.png")) if qc_dir.is_dir() else []
    return jsonify(rows)


@app.route("/sweep/<name>/aggregate", methods=["POST"])
def sweep_aggregate_route(name):
    sweep_aggregate.aggregate_sweep(name)
    flash(f"'{name}' agregado")
    return redirect(url_for("sweep_status", name=name))


@app.route("/sweep/<name>/publish", methods=["POST"])
def sweep_publish_route(name):
    try:
        out_dir = sweep_publish_dataset.publish_dataset([name], triggered_by="webapp")
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("sweep_status", name=name))
    return redirect(url_for("dataset_view", dataset_hash=out_dir.name))


@app.route("/qc/<sweep>/<run_hash>/<filename>")
def qc_image(sweep, run_hash, filename):
    qc_dir = SWEEP_RUNS_DIR / sweep / "runs" / run_hash / "qc"
    return send_from_directory(qc_dir, filename)


@app.route("/history")
def history():
    return render_template("history.html", events=sweep_history.read_history())


@app.route("/datasets/<dataset_hash>")
def dataset_view(dataset_hash):
    import sweep_hash as sh
    manifest_path = DATASETS_DIR / dataset_hash / "manifest.json"
    if not manifest_path.exists():
        flash(f"dataset '{dataset_hash}' no existe")
        return redirect(url_for("index"))
    manifest = sh.read_json(manifest_path)
    by_class_shapes = {}
    for class_key, rel_path in manifest.get("by_class_files", {}).items():
        df = pd.read_parquet(DATASETS_DIR / dataset_hash / rel_path)
        by_class_shapes[class_key] = df.shape
    return render_template("dataset.html", manifest=manifest, by_class_shapes=by_class_shapes)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
