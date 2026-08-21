# Cómo correr LightCurveLynx en este proyecto

Instructivo práctico para operar el PoC de LightCurveLynx desde cero — pensado para poder
hacerlo funcionar sin depender de esta sesión. Cubre entorno, conceptos mínimos de la librería,
cómo correr una simulación real, y cómo leer lo que produce. El detalle de *por qué* cada
decisión de diseño es la que es (bugs encontrados, parámetros verificados clase por clase, etc.)
vive en `NOTES.md` — este documento es solo el "cómo", no el "por qué".

## 1. Qué es LightCurveLynx en este proyecto

[LightCurveLynx](https://github.com/lincc-frameworks/LightCurveLynx) (LINCC Frameworks) es un
simulador de curvas de luz en Python — la pregunta que este proyecto viene investigando desde la
Fase 0 es si puede reemplazar a SNANA (el simulador real de producción, en C, capa 1-4 del
pipeline) como motor de simulación. Todo lo de esta carpeta es **exploratorio**, no forma parte
del pipeline de producción (`pipeline/`) — no toca `campaigns/`, `models.yaml` ni corre dentro de
`run_campaign.py`.

## 2. Entorno — cómo se instaló (ya hecho, para referencia)

Vive en un venv **aislado** en NLHPC, separado del venv del pipeline SNANA real:

```bash
cd ~/AUTOSIM/exploration/lightcurvelynx
module load python/3.12.3-legacy-skylake
python3 -m venv venv
source venv/bin/activate
pip install "lightcurvelynx[all]"   # incluye jax, dask, hats, dust_extinction, synphot, etc.
```

Desde Fase 17 el mismo venv también tiene `jupyter`/`nbconvert`/`ipykernel` (para
`analyze_phot_df.ipynb`) y `pandas`/`pyarrow`/`matplotlib` (para leer/graficar `phot_df.parquet`).

**Nunca trabajar en el login node** para nada que no sea trivial (instalar paquetes, editar
archivos) — todo lo que simula o lee datos reales va por `sbatch` (ver sección 5). Esto no es una
convención arbitraria: dos de las capas del pipeline real se niegan a correr fuera de SLURM por
guardia automática, y el mismo criterio se aplica aquí por consistencia.

## 3. Conceptos mínimos de LightCurveLynx (lo que este proyecto realmente usa)

LightCurveLynx arma un **grafo de nodos** — cada parámetro del objeto simulado (redshift, RA/Dec,
t0, parámetros del modelo, extinción...) es un nodo que sabe samplear su propio valor, y esos
nodos se conectan entre sí como dependencias. Las piezas que este proyecto usa:

- **`OpSim`** (`lightcurvelynx.obstable.opsim`): envuelve la tabla de observaciones reales del
  survey (leída directo del `.db` de OpSim vía `sqlite3`/`pandas`, no de un SIMLIB pre-construido
  — mismo patrón en los 3 scripts). Es lo que le dice al simulador *cuándo* y *con qué
  profundidad/PSF/cielo* se observó cada punto del cielo.
- **`ObsTableRADECSampler`**: samplea posiciones RA/Dec reales de los pointings de un `OpSim` ya
  filtrado (DDF o WFD), ponderado por número de visitas — no una caja uniforme de cielo (eso deja
  casi todo con `NOBS=0`, ver `NOTES.md` Fase 1).
- **Modelos de fuente** — dos tipos según la clase:
  - `SIMSEDModel`/`MultiSEDTemplateModel` (`run_simsed_poc.py`/`run_non1ased_poc.py`): un
    ensemble de templates SED reales de SNANA (SIMSED o NON1ASED), con pesos (uniformes o
    correlacionados vía `SIMSED_REDCOR`).
  - `SncosmoWrapperModel` sobre `sncosmo.SALT2Source` (`run_snia_ddf_poc.py`): el modelo SALT2
    real (`SALT2.WFIRST-H17`), cargado directo de los archivos de SNANA, no de un mirror remoto.
- **Efectos** (`ClippedExtinctionEffect`/`ExtinctionEffect`): extinción MW (`frame="observer"`) y
  de galaxia anfitriona (`frame="rest"`), aplicados como efectos encadenados sobre el modelo de
  fuente.
- **`PassbandGroup.from_preset(preset="LSST")`**: curvas de transmisión reales de Rubin (verificado
  en Fase 12 que coinciden con el `kcor_LSST.fits` real de la campaña).
- **`simulate_lightcurves(source, ngentot, survey_info, ...)`**: el punto de entrada real — genera
  `ngentot` objetos, cada uno con su curva de luz (flujo/error) en las épocas reales que le
  tocaron según su posición.
- **Samplers custom** (`snana_params.py`, no nativos de LightCurveLynx): réplicas de los modelos
  de tasa (`DNDZ`), distribución de `x1`/`c` bifurcada, atenuación de host (`exp`/`exp_halfgauss`/
  `wv07`), dispersión de `MWEBV`, y desde Fase 17 el lookup de E(B-V) real para WFD. Todos
  devuelven una función `func(size=None, **kw)` — la firma que espera `FunctionNode`.

### Trampas reales de la librería (no leer la documentación y asumir que basta)

Confirmadas leyendo el código fuente instalado (`inspect.getsource()`, no la doc oficial) — ver
`NOTES.md` Fases 4-5 para el detalle completo:

1. `ObsTableRADECSampler` aplica jitter de posición sin semilla si `radius > 0` → siempre pasar
   `radius=0.0` para pointings fijos (DDF/WFD, no requieren jitter sub-FOV).
2. `TableSampler.__init__` (clase base del sampler anterior) arma su índice de fila interno **sin
   heredar** el `seed=` del constructor externo → sembrarlo a mano después:
   `radec_sampler.setters["selected_table_index"].dependency.set_seed(seed_base + 5)`.
3. `SIMSEDModel.from_dir()`/`MultiSEDTemplateModel.__init__` arman su sampler de selección de
   template **sin `seed=`** → `source_model._sampler_node.set_seed(seed_base + 9)` después de
   construir el modelo.
4. `simulate_lightcurves()` necesita `rng=np.random.default_rng(seed_base + N)` explícito, si no
   el ruido fotométrico cae en un generador sin semilla.

Los 3 scripts `run_*_poc.py` ya aplican estos 4 fixes — si se escribe un script nuevo contra
LightCurveLynx, hay que replicarlos a mano.

## 4. Los 3 scripts reales de este proyecto

| Script | Modelo | Clases | Uso |
|---|---|---|---|
| `run_simsed_poc.py` | `SIMSEDModel` | 14 (`CLASS_CONFIGS`, ver `python3 run_simsed_poc.py` sin args para la lista) | `python3 run_simsed_poc.py <clase> [seed_index] [--wfd]` |
| `run_non1ased_poc.py` | `MultiSEDTemplateModel` (NON1ASED) | 5: `SNIa-91bg`, `SNIax`, `TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP` | `python3 run_non1ased_poc.py <clase> [seed_index] [--wfd]` |
| `run_snia_ddf_poc.py` | `SncosmoWrapperModel`/SALT2 | 1: `SNIa` (única clase SALT2 del proyecto) | `python3 run_snia_ddf_poc.py [seed_index] [--wfd]` |

`--wfd` (Fase 17) corre a escala WFD (footprint completo, sin campos fijos, E(B-V) real por
posición vía `wfd_mwebv_grid.csv`) en vez de DDF (6 campos fijos) — mismo `NGENTOT` en ambos casos
(2000/clase, salvo `PISN-STELLA-HYDROGENIC` en 20000). `seed_index` (0 = corrida "principal";
1-4 = semillas extra para banda de incertidumbre, ver Fase 5) es siempre el 2do argumento
posicional; `--wfd` puede ir en cualquier posición.

Todos comparten el mismo patrón interno: leer `OpSim` real → construir el modelo de fuente con
sus efectos → `simulate_lightcurves()` → aplanar a `head_df`/`phot_df` → aplicar `SEARCHEFF` real
(`searcheff.py`) → persistir tablas + `summary.json` → generar QC (`pipeline.postproc.qc`, el
mismo módulo que usa SNANA real, sin modificar).

## 5. Cómo correr una simulación real

Nunca directo en el login node — siempre `sbatch`, desde la raíz del repo (`~/AUTOSIM`):

```bash
cd ~/AUTOSIM
sbatch exploration/lightcurvelynx/run_simsed_poc.sbatch SNIa-91bg-elastic       # DDF, seed 0
sbatch exploration/lightcurvelynx/run_simsed_poc.sbatch SNIa-91bg-elastic 0 --wfd  # WFD, seed 0
sbatch exploration/lightcurvelynx/run_non1ased_poc.sbatch SLSN-I 2             # DDF, seed 2
sbatch exploration/lightcurvelynx/run_snia_ddf_poc.sbatch 0 --wfd             # SNIa/SALT2, WFD
```

Verificar progreso: `squeue -u $USER`, logs en `logs/lcl_*_%j.out`/`.err` (creado por el
`#SBATCH -o`/`-e` del script). El tiempo de reserva (`#SBATCH -t`) varía según cuántos templates
carga la clase — algunas SIMSED grandes (SLSN-I-MOSFIT, 960 templates) tardan bastante solo en
cargar, ver el comentario en `run_simsed_poc.sbatch`.

**Antes de cualquier corrida real, verificar headroom de disco** (la cuota de NLHPC es el recurso
más frágil de todo el proyecto, ver Fase 8/17 en `NOTES.md` — ya hubo un incidente real):

```bash
du -sh ~/                                                  # uso actual
dd if=/dev/zero of=~/.headroom_test bs=1M count=500        # prueba de escritura real
rm -f ~/.headroom_test
```

## 6. Qué produce y cómo leerlo

Cada corrida crea `poc_output_<clase>[_seed<N>][_wfd]/` con:

- **`summary.json`** — la "comprobación" agregada: `ngentot_lc`, `n_with_obs`, `n_detected`,
  `detection_efficiency_pct`, `snr_median`/`snr_p90`, `strategy` (`DDF`/`WFD`, desde Fase 17).
  Esto es lo único que se conserva siempre, incluso para las corridas de semilla extra.
- **`head_df.parquet`** — una fila por objeto simulado con observación: `SNID`, `SNTYPE`, `RA`,
  `DEC`, `REDSHIFT_HELIO`, `PEAKMJD`, `NOBS`, `DETECTED`.
- **`phot_df.parquet`** — una fila por observación individual: `SNID`, `MJD`, `FLT`, `FLUXCAL`/
  `FLUXCALERR` (nJy, no el `FLUXCAL`/ZEROPT=27.5 de SNANA), `MAG`, `PHOTFLAG`. El más pesado —
  puede pesar cientos de MB para `NGENTOT` grande, no se versiona en git (`.gitignore`).
- **`qc/*.png`** — 4 gráficos de control (`pipeline.postproc.qc`, mismo módulo que SNANA real):
  detecciones, curvas de luz, magnitudes, redshift.

Para explorar `phot_df`/`head_df` sin escribir código nuevo cada vez, usar
`exploration/lightcurvelynx/analyze_phot_df.ipynb` (Fase 17) — escanea automáticamente qué
corridas hay disponibles y arma los gráficos/estadísticas estándar del proyecto. Ejecutarlo dentro
del venv real, nunca en el login node para las celdas que leen `phot_df.parquet` completo:

```bash
cd ~/AUTOSIM/exploration/lightcurvelynx
sbatch execute_analyze_notebook.sbatch     # corre jupyter nbconvert --execute en un job real
```

El glosario completo de columnas/siglas (qué es `SNTYPE`, `PHOTFLAG`, `SIGCOH`, etc.) vive en el
dashboard (`docs/index.html`, pestaña "LightCurveLynx", sección "Glosario") y, condensado, en la
primera celda markdown del notebook.

## 7. Dónde está cada cosa real que estos scripts leen

Todo bajo `/home/mvalenzuela/` en NLHPC — nunca hardcodear un valor sin verificar contra el
archivo real primero (es el criterio metodológico de todo este proyecto, ver `NOTES.md`):

- `.INPUT` reales de cada clase: `run_SNANA/model_config/SIMGEN_INCLUDE_<clase>.INPUT`
  (producción base) o `run_SNANA/elastic/model_config/SIMGEN_INCLUDE_<clase>[_NON1ASED].INPUT`
  (árbol "elastic" — usado por las variantes NON1ASED reales). **La fuente de verdad de cuál
  archivo usa cada `GENVERSION` real** es
  `AUTOSIM/build/full_v5.3_10yrs/includes/include_model_<clase>.INPUT` (`INPUT_INCLUDE_FILE:`
  apunta al `.INPUT` real que de verdad se compiló) — no asumir por el nombre de carpeta.
- SIMLIB/OpSim real: `AUTOSIM/data/opsim/baseline_v5.3.1_10yrs.db` (SQLite; `target_name LIKE
  '%ddf_%'` filtra DDF, el resto es WFD).
- SEARCHEFF real: `run_SNANA/LSST_SEARCHEFF_PIPELINE.DAT` (curva vs. SNR) +
  `run_SNANA/LSST_PIPELINE_LOGIC.DAT` (lógica de trigger).
- SALT2 real: `run_SNANA/plasticc_models/SALT2.WFIRST-H17/` (+ `SALT2.INFO` para
  `COLORCOR_PARAMS`).
- `.DUMP`/FITS de una campaña real ya corrida (para comparar): buscar bajo
  `/home/mvalenzuela/DATASIM_LSST_1/<DDF|WFD>/<carpeta de la version>/<GENVERSION>/` — no un path
  fijo, cambia con cada versión de campaña (`ls ~/DATASIM_LSST_1/DDF/` para ver las disponibles).

## 8. Para profundizar

- `NOTES.md` (mismo directorio) — el historial completo, 18 fases, con cada hallazgo/bug/decisión
  justificado con evidencia real de código, no supuestos.
- `docs/index.html`, pestaña "06 LightCurveLynx" — el resumen curado para lectores no expertos,
  con glosario y las 19 fases explicadas en una línea cada una.
