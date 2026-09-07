# Cómo usar "el botón" — la interfaz web de generación de sweeps

Instructivo práctico para la app web local (Flask) que reemplaza la línea de comandos para generar,
lanzar y publicar sweeps de LightCurveLynx. Documento hermano de `HOWTO.md` (flujo real de NLHPC) y
`HOWTO_LOCAL.md` (instalación en una máquina sin NLHPC) — este cubre solo la interfaz, construida
sobre esos dos.

## 1. Qué es esto, y qué NO es

Es una app web que corre **en tu propia máquina** (o en el login node de NLHPC para una prueba
rápida) y te deja generar/lanzar/monitorear/publicar sweeps desde el navegador en vez de la
terminal. Todo lo que hace, ya lo hacían los scripts `sweep_*.py` (Fases 66/76/79-82) — esta app
solo les pone un formulario y botones encima; no agrega ninguna capacidad nueva de simulación.

**No es**: un servicio multiusuario ni algo para desplegar en un servidor compartido — corre en
`127.0.0.1` únicamente, pensada para que una sola persona la abra en su propio navegador mientras el
proceso Flask corre en la misma máquina (o vía un túnel SSH si se corre en NLHPC). No entrena ni
despliega ningún modelo — llega hasta producir el dataset (parquet por clase).

## 2. Requisitos

Completar primero `HOWTO_LOCAL.md` (venv con `requirements.txt` instalado -- incluye `flask` desde
la Fase 83 --, datos vendorizados, `.db` de OpSim). Sin eso, la app arranca pero el formulario no
tendrá ninguna clase disponible para elegir.

## 3. Levantar la app

```bash
cd exploration/lightcurvelynx
source venv/bin/activate            # o el equivalente de tu instalación local
python3 webapp/app.py
```

Abre `http://127.0.0.1:5000/` en el navegador. Si corres esto en NLHPC (login node, para probar
antes de instalar localmente) en vez de tu propio computador, necesitas un túnel SSH para verlo en
tu navegador:

```bash
ssh -L 5000:127.0.0.1:5000 nlhpc
```

y luego abrir `http://127.0.0.1:5000/` en tu máquina como si la app corriera ahí mismo.

## 4. Generar y correr un sweep

1. **Generar** (`/`): nombre del sweep, clases (solo aparecen las que ya tienen datos
   vendorizados en esta máquina — ver `HOWTO_LOCAL.md` sección 8 para agregar una clase nueva),
   `ngentot` por clase (vacío = default del catálogo), semillas, WFD/DDF, y si quieres preservar la
   fotometría cruda (`keep_phot` — necesario si vas a publicar un dataset con parquet por clase para
   el equipo de ML, ver sección 6). La sección "Avanzado" deja ajustar memoria/tiempo/CPUs/
   paralelismo si los defaults no alcanzan.
2. Al enviar el formulario, la app genera el YAML real (`sweep_generate.py`, Fase 79) y lo compila
   (`sweep_compile.py`) automáticamente, y te lleva a la página de estado del sweep.
3. **Lanzar**: el botón "Lanzar" corre el sweep en segundo plano (sin bloquear la página) vía el
   mismo runner local sin SLURM de la Fase 76. El estado de cada corrida se actualiza solo, cada
   pocos segundos, sin recargar la página — cuando termina, aparecen enlaces reales a sus 4 gráficos
   de control (QC).
4. Cuando todas las corridas terminan, aparecen los botones **Agregar** (consolida las métricas del
   sweep) y **Publicar** (crea un dataset versionado por hash en `datasets/<hash>/`).

## 5. Historial

La pestaña "Historial" muestra `generation_history.jsonl` (Fase 80) — cada sweep generado,
compilado, corrido o publicado, más reciente primero, con quién/qué lo disparó. Es la traza
reproducible real: cualquiera que abra esta página ve exactamente qué se generó, cuándo y con qué
parámetros, sin tener que leer `NOTES.md`.

## 6. El dataset publicado (conector de ML)

La página de un dataset (`/datasets/<hash>`) muestra su `ingestion_format`:

- **`parquet_by_class_v1`**: al menos una corrida de origen tenía `keep_phot=true` — hay archivos
  reales en `datasets/<hash>/by_class/<clase>.parquet` (fotometría completa + contexto +
  procedencia), listos para entregar al equipo de ML tal cual (Fase 82).
- **`null`**: ninguna corrida de origen preservó fotometría cruda — la página explica por qué.
  Solución: generar un sweep nuevo marcando "Preservar fotometría cruda" y volver a publicar.

## 7. Qué NO hace esta interfaz

- No entrena ni despliega ningún modelo — el punto de entrega es el `parquet` por clase.
- No agrega soporte para `SNIa`/SALT2 ni las clases NON1ASED al sistema de sweeps (decisión ya
  tomada en Fase 73) — el formulario solo lista clases de `CLASS_CONFIGS` (`run_simsed_poc.py`).
- No reemplaza `sweep_launch.py`/`sbatch` para barridos grandes reales en NLHPC con SLURM — usa el
  runner local (Fase 76), pensado para máquinas sin cluster. Para un barrido grande en NLHPC con
  cientos de corridas, seguir usando `sweep_launch.py` desde la terminal (`HOWTO.md` sección 5-bis).

## 8. Para profundizar

- `HOWTO.md` / `HOWTO_LOCAL.md` — los flujos de NLHPC y de instalación local que esta interfaz
  envuelve.
- `NOTES.md`, Fases 79-85 — el detalle real de cada pieza (el generador, el historial,
  `keep_phot`, el conector por clase, el backend Flask, el frontend, y esta fase de cierre).
- `docs/index.html`, pestaña "06 LightCurveLynx" — el resumen curado de todas las fases.
