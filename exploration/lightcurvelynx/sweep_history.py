"""
Fase 80: historial reproducible append-only -- el "JSON como historial"
que pidio el profesor ("un historial de..., cualquier otra persona tome
el codigo y pueda seguir").

Ningun mecanismo existente cumple esto hoy: `manifest.json` (por sweep),
`run_hash.json` (por corrida) y `datasets/<hash>/manifest.json` (por
publicacion) son todos snapshots FRESCOS y autocontenidos -- nada se
acumula a traves de multiples acciones de generar/compilar/correr/publicar
a lo largo del tiempo. La unica "historia" real hasta ahora es NOTES.md,
prosa de miles de lineas, no legible por maquina.

`generation_history.jsonl` (JSON Lines, gitignorado -- mismo criterio que
sweep_runs/datasets: config se versiona, output generado no) acumula un
evento por linea, nunca se reescriben lineas existentes. Deliberadamente
NO registra cada corrida individual -- eso ya vive completo y autoritativo
en runs/<hash>/run_hash.json; duplicarlo violaria el criterio de no
inventar mecanismos paralelos. Este historial conecta eventos de DECISION
(generar/compilar/correr/publicar), no de ejecucion fila-a-fila.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import sweep_hash

HERE = Path(__file__).resolve().parent
HISTORY_PATH = HERE / "generation_history.jsonl"


def record_event(event_type: str, *, triggered_by: str = "cli", **fields) -> dict:
    record = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event_type": event_type,
        "triggered_by": triggered_by,
        **fields,
    }
    sweep_hash.append_jsonl(HISTORY_PATH, record)
    return record


def read_history(limit: int | None = None) -> list[dict]:
    """Devuelve los eventos, mas reciente primero. Lectura tolerante:
    una linea corrupta (proceso muerto a mitad de un append -- mitigado
    por flush()+fsync() en sweep_hash.append_jsonl, pero no imposible si
    el propio filesystem falla) se salta con una advertencia en vez de
    tumbar toda la lectura del historial."""
    import json

    if not HISTORY_PATH.exists():
        return []
    events = []
    for i, line in enumerate(HISTORY_PATH.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"  ! linea {i + 1} de {HISTORY_PATH.name} no es JSON valido -- se omite")
    events.reverse()
    return events[:limit] if limit else events


if __name__ == "__main__":
    for event in read_history():
        print(f"[{event['timestamp']}] {event['event_type']} (via {event['triggered_by']})")
