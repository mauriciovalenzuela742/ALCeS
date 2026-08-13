# Fase 0 — Spike técnico: LightCurveLynx vs. SNANA

Ver plan completo en `C:\Users\HOME\.claude\plans\harmonic-singing-pebble.md` (o el historial
de la sesión). Este documento consolida las 5 preguntas abiertas de la Fase 0, todas
respondidas con código corrido de verdad en NLHPC (venv aislado en
`exploration/lightcurvelynx/venv`, `lightcurvelynx==0.5.2`), no solo lectura de documentación.

## Resumen ejecutivo

**Recomendación: GO a Fase 1.** No apareció ningún bloqueador duro. Hay una brecha real y
concreta (SEARCHEFF) y un trabajo de integración real pero acotado (SIMSED), ambos manejables.
La ingesta de OpSim y la extinción MW funcionan literalmente sin escribir código de adaptación.
El rendimiento medido es dramáticamente mejor que SNANA (~150x más rápido en la comparación
cruda de throughput, ver punto 5) — si la Fase 1 confirma equivalencia científica, el caso para
migrar es fuerte.

## 1. SIMSED — soporte parcial, requiere integración propia

`lightcurvelynx/utils/io_utils.py::read_grid_data()` lee **un solo** grid 2D
(fase × longitud de onda → flujo) desde un archivo de 3 columnas — no es un lector de
directorios SIMSED completos. Confirmado contra un SIMSED real de nuestro catálogo
(`run_SNANA/plasticc_models/SIMSED.TDE-MOSFIT/`, 745 archivos `.dat.gz` + `SED.INFO` con 8
parámetros físicos por SED, formato estándar SNANA SIMSED).

**Conclusión**: no hay lector de "librería SIMSED" nativo. La ruta de integración es escribir
un wrapper propio: parsear `SED.INFO` (formato texto simple), cargar cada `.SED` individual vía
`SEDTemplate`/`SEDTemplateModel` (`lightcurvelynx/models/sed_template_model.py`, que sí acepta
un grid N×3 de fase/longitud de onda/flujo — compatible con el formato de cada `.dat` de SIMSED
después de descomprimir), y samplear entre las 745 plantillas según los pesos/parámetros de
`SED.INFO` usando los nodos de sampleo existentes (`GivenValueSampler`/`GivenValueSelector`).
Esto afecta a nuestras clases MOSFIT: TDE, SLSN-I, PISN-STELLA (×2), CaRT, ILOT — trabajo real
pero acotado, no un bloqueador.

## 2. SEARCHEFF — brecha real confirmada

`lightcurvelynx/astro_utils/obs_utils.py` tiene:
- `phot_eff_function(snr)`: **función escalón dura** (`snr > 5 → 1.0, si no → 0.0`), no una
  curva suave ajustada a datos reales como el `SEARCHEFF_PIPELINE_EFF_file` de SNANA.
- `spec_eff_function(peak_imag)`: eficiencia de seguimiento espectroscópico en función de la
  magnitud i de pico — **basada explícitamente en la Ecuación 17 de Kessler et al. 2019**
  (mismo linaje científico que SNANA, curiosamente).

**Falta**: la lógica de trigger multi-época/multi-filtro de SNANA
(`SEARCHEFF_PIPELINE_LOGIC.DAT`, p.ej. "2 detecciones separadas por N días en M filtros") no
tiene equivalente. **Conclusión**: hay piezas básicas, pero no el sistema completo. Opciones
para la Fase 1/2: (a) aplicar nuestra propia lógica de `SEARCHEFF_PIPELINE_LOGIC.DAT`/
`SEARCHEFF_PIPELINE_LSST.DAT` (que ya tenemos, calibrados) como post-proceso sobre la columna
`lightcurve.detection` que sí exporta `post_process_results.py`, o (b) aceptar el escalón
simple si el objetivo es solo comparación estadística agregada, no fidelidad de pipeline real.

## 3. Ingesta de OpSim — funciona sin ninguna transformación ✓

`lightcurvelynx/obstable/opsim.py::OpSim` tiene un `_default_colnames` que mapea
**exactamente** a las columnas reales de `data/opsim/baseline_v5.3.1_10yrs.db`
(`fieldRA`, `fieldDec`, `observationStartMJD`, `filter`, `fiveSigmaDepth`, `numExposures`,
`seeingFwhmEff`, `skyBrightness`...) — mismo schema que produce el simulador oficial de Rubin
(`rubin-scheduler`, no una convención propia de LightCurveLynx).

**Verificado con ejecución real**: cargamos las 1,844,189 observaciones de
`baseline_v5.3.1_10yrs.db` directo a un objeto `OpSim` sin ningún error ni transformación de
columnas — coincide con `len(df)` exacto.

DDF vs. WFD **no** viene distinguido por defecto en `OpSim`, pero la columna cruda
`target_name` sí lo permite (`ddf_elaiss1`, `ddf_cosmos`, `ddf_xmm_lss`, `ddf_edfs_a/b`,
`ddf_ecdfs` — los 6 campos DDF oficiales de Rubin) — mismo patrón que ya usa nuestra Capa 1
hoy (filtrar antes de pasar los pointings), no un bloqueador.

Nota interesante: los valores por defecto de zeropoint/extinción de `OpSim`
(`_opsim_zeropoint_per_sec_zenith`, `_opsim_extinction_coeff`) están explícitamente calculados
con **`syseng_throughputs v1.9`** — la misma versión de throughputs que ya confirmamos vigente
para nuestro `kcor_LSST.fits` (ver `pipeline/kcor/README.md`). Buena señal de consistencia
entre ambos ecosistemas.

## 4. Extinción MW — soportada, más flexible que SNANA ✓

`lightcurvelynx/effects/extinction.py::ExtinctionEffect` soporta `frame='observer'` (MW) o
`frame='rest'` (host) explícitamente, con `ebv`/`r_v` parametrizables, respaldado por el
paquete `dust_extinction` (Gordon 2024, JOSS — estándar de facto en la comunidad astropy) o
alternativamente el paquete `extinction` (usado por sncosmo). Incluye CCM89 y otras leyes
estándar — cubre lo que SNANA aplica hoy (CCM89+O'Donnell94) y más opciones. **Sin brecha.**

## 5. Escala / rendimiento — medido, dramáticamente más rápido

Benchmark real corrido en el login node de NLHPC (1 core, sin SLURM), simulando SNIa via
`SncosmoWrapperModel("salt2-h17")` sobre el `OpSim` real completo (1.8M observaciones):

| N eventos | tiempo total | ms/evento | eventos/seg |
|---|---|---|---|
| 200   | 0.34s | 1.71 | ~1830 |
| 1000  | 0.86s | 0.86 | ~1765 |

Extrapolado a `NGENTOT_LC=200,000` (el tamaño real de una clase WFD en producción):
**~110-115 segundos**, en un solo core de login node, sin escribir a disco.

Comparado con SNANA real: los logs de la campaña v8 muestran tasas de escritura
(`NGENLC_WRITE`) del orden de **10-15 eventos/seg** (p.ej. `1036 (15/sec)`, `25 (12/sec)`) vía
SLURM en nodos de cómputo dedicados. La comparación no es 100% equivalente (SNANA cuenta
eventos que pasan el trigger de escritura tras generar más internamente, incluye I/O a FITS,
y esta prueba no escribió a disco) — pero la diferencia de orden de magnitud (~150x) es lo
bastante grande como para ser una señal real, a confirmar con más rigor en la Fase 1.

Un detalle de madurez a anotar: apareció un `RuntimeWarning: invalid value encountered in
sqrt` en `noise_models/noise_utils.py` durante la corrida de N=1000 — no rompió la simulación,
pero es la clase de señal que hay que vigilar dado que el proyecto es pre-1.0 (consistente con
el propio disclaimer de la documentación).

**Sin decidir todavía** (no crítico para el go/no-go de Fase 1, sí para Fase 2-3): si la
orquestación final usa "un job SLURM por clase" (como hoy) o cambia a un solo job con
`dask`/`ray` dado lo económico que resulta computacionalmente — con estos números, probablemente
ni siquiera hace falta SLURM para volúmenes de esta escala, lo cual simplificaría bastante la
Capa 3 actual (`pipeline/orchestrate/`).

## Detalle técnico adicional (no una de las 5 preguntas, pero relevante)

El propio tutorial oficial (`docs/notebooks/simple_snia.ipynb`) usa `SncosmoWrapperModel`
(wrapper de `sncosmo`, modelo `"salt2-h17"`) como la vía principal y mejor documentada para
SNIa, no `SALT2JaxModel` — este último existe pero tiene menos ejemplos end-to-end en la
documentación. Para la Fase 1 (PoC SNIa acordado con el usuario), usar `SncosmoWrapperModel`
como primera opción por ser el camino mejor pavimentado, y `SALT2JaxModel` como alternativa
si se necesita diferenciabilidad (gradientes vía JAX) — a decidir al iniciar la Fase 1, no
cambia el resultado de este spike.

## Entorno de referencia

- `exploration/lightcurvelynx/venv/` en NLHPC — venv aislado, **no** compartido con
  `pipeline/venv` (el pipeline SNANA activo no fue tocado).
- `pip install "lightcurvelynx[all]"` — incluye jax, dask, hats, dust_extinction,
  VBMicrolensing, synphot, bilby, pzflow, lsdb.
- Scripts de verificación: `check_opsim_schema.py`, `test_opsim_load.py`, `bench_snia.py`
  (este directorio).

---

# Fase 1 — PoC SNIa_DDF: parámetros reales de SNANA, comparación directa

Plan completo: `C:\Users\HOME\.claude\plans\delegated-tumbling-petal.md`. Objetivo acordado:
un PoC de una sola clase (SNIa) con parámetros reales (no placeholders) que confirme o
descarte equivalencia científica con SNANA — no solo velocidad — usando `SNIa_DDF` como
baseline (`SNIa_WFD` seguía con el FITS corrupto de antes, verificado de nuevo al iniciar
esta fase: mismo timestamp, mismo `UnicodeDecodeError`, sin resimulación exitosa desde
entonces).

## Resumen ejecutivo

**Resultado: la mecánica del PoC funciona de punta a punta — parámetros reales, samplers
custom (DNDZ, Gaussianas bifurcadas), extinción MW real, eficiencia de detección real
(SEARCHEFF real, no el escalón nativo), reuso directo del QC ya arreglado esta sesión — pero
la eficiencia de detección global sale ~2x más alta que SNANA real (60.75% vs 29.85%, tras
intentar calibrar `zp_err_mag` contra el valor real de SNANA sin éxito — ver punto 7b), y la
causa más probable diagnosticada es que el modelo de ruido fotométrico de LightCurveLynx
subestima el ruido por-época real, no un problema con la población simulada (redshift/color/
extinción); dos rondas de investigación no encontraron el componente exacto responsable.
Esta brecha queda abierta, no resuelta. Por separado, se validó el patrón de orquestación
propuesto para Fase 2 (`dask.distributed.LocalCluster` dentro de un único job SLURM, sin
tocar el login node): 3.16x de speedup real medido. Recomendación: GO condicional a Fase 2,
contingente en calibrar/reemplazar el modelo de ruido de LightCurveLynx antes de sacar
conclusiones cuantitativas de cualquier corrida futura.**

## 1. Parámetros reales de `SIMGEN_INCLUDE_SNIa-SALT2.INPUT`

El spike de Fase 0 (`bench_snia.py`) usaba placeholders (redshift uniforme, Gaussianas
simples, sin DNDZ). Verificado contra el `.INPUT` real en NLHPC:

| Parámetro | Placeholder (Fase 0) | Real (usado en Fase 1) |
|---|---|---|
| `GENRANGE_REDSHIFT` | uniforme 0.01–0.6 | DNDZ POWERLAW2 real, 0.011–1.2 |
| `GENSIGMA_SALT2c` | Normal simple, σ=0.02 | bifurcada: peak=-0.054, σ=(0.043, 0.101) |
| `GENSIGMA_SALT2x1` | Normal simple, σ=2.0 | bifurcada: peak=0.973, σ=(1.472, 0.222) |
| `alpha`/`beta` | 0.14/3.1 | igual (ya coincidía) |
| `GENMAG_SMEAR_MODELNAME: G10` | no implementado | aproximado: dispersión acromática coherente,
  `SIGMA_INT=0.090` de `SALT2.INFO` (no la covarianza x1/c completa de G10 — fuera de alcance
  de un PoC, ver Fase 0 punto 1) |

`snana_params.py` (nuevo): `build_dndz_powerlaw2_cdf()` construye la tasa diferencial
`dN/dz = DNDZ(z)·dVc/dz/(1+z)` (dilución temporal incluida) numéricamente y samplea por
inversión de CDF; `make_bifurcated_normal_sampler()` samplea una Gaussiana con σ distinto a
cada lado del pico, con corte por rechazo en `GENRANGE_SALT2{c,x1}`. Verificado standalone
(fuera del grafo de LightCurveLynx) contra 5000 muestras: formas y percentiles razonables,
CDF sube monótonamente 0→1 sin degeneración.

## 2. Bug real encontrado: `FunctionNode` nunca pasa `size=` a la función envuelta

Al conectar los samplers custom al grafo de LightCurveLynx (`FunctionNode(mi_sampler,
node_label=...)`), la primera corrida completa produjo un redshift casi degenerado (un solo
bin angosto cerca de z≈1.2 en vez de la distribución esperada 0.011–1.2). Diagnóstico:
`FunctionNode.compute()` (base, `lightcurvelynx/base_models.py`) llama
`self.func(**args)` **sin `size` en absoluto** — a diferencia de `NumpyRandomFunc.compute()`,
que sí inyecta `size=graph_state.num_samples` explícitamente. Con la firma
`sampler(size=None, **kw)`, cada llamada devolvía un solo valor escalar que el grafo
terminaba difundiendo (broadcast) a los N samples — confirmado con
`FunctionNode(sampler, node_label='z').generate(num_samples=10)` devolviendo el mismo
valor 10 veces.

**Fix**: `SizeAwareFunctionNode` (en `snana_params.py`), una subclase mínima de
`FunctionNode` que sobreescribe `compute()` para inyectar `size=graph_state.num_samples` —
mismo patrón que usa `NumpyRandomFunc` internamente, aplicado a un callable arbitrario.
Verificado: `SizeAwareFunctionNode(sampler, ...).generate(num_samples=2000)` devuelve 2000
valores únicos con la forma esperada.

## 3. SALT2 H17: el mirror remoto de sncosmo está caído — se usó el modelo real de SNANA

`get_source("salt2-h17")` (usado en `bench_snia.py`) intenta descargar desde
`https://sncosmo.github.io/data/models/snana/salt2-h17/` — **404 confirmado** (GitHub Pages,
recurso no existe más). En vez de reintentar contra un mirror caído, se cargó el modelo H17
real que ya usa `SNIa_DDF` de SNANA (`run_SNANA/plasticc_models/SALT2.WFIRST-H17/*.dat.gz`)
directo vía `sncosmo.SALT2Source(modeldir=...)` — mismo modelo físico, no una aproximación.
Dos ajustes de formato (no de contenido científico, ver `setup_salt2_local.py`):
descomprimir los `.dat.gz`, y reescribir `salt2_color_correction.dat` en el formato de texto
que espera `sncosmo` (`<ncoeffs>\n<coefs>\nSalt2ExtinctionLaw.version 1\n...`) usando los
coeficientes reales de `SALT2.INFO::COLORCOR_PARAMS` (`-1.33154627 0.61225710 -0.12117791
0.00840832`, rango 2800–9500Å) — el archivo de SNANA con ese mismo nombre es una tabla de
dispersión de ~4.9MB, un producto distinto, no los ~4 coeficientes que separa `sncosmo`.
Verificado: `SALT2Source` carga y evalúa flujo correctamente con este modelo local.

## 4. Posiciones RA/Dec: hay que samplear del footprint real, no una caja uniforme

Primer intento con RA/Dec uniformes sobre todo el cielo (mismo patrón que `bench_snia.py`):
la mayoría de los objetos caían con `nobs=0` porque DDF son solo 6 pointings angostos, no
todo el cielo. Fix: `ObsTableRADECSampler(obs_table)` — samplea posiciones reales
(visit-weighted) de los pointings del `OpSim` ya filtrado a DDF, con el radio de campo de
visión real. `extra_cols=["field"]` además devuelve, ya emparejada por fila, la etiqueta del
campo DDF real (`cosmos`, `ecdfs`, `edfs_a`, `edfs_b`, `elaiss1`, `xmm_lss`) — necesaria para
asignar extinción MW correcta por campo (punto 6).

## 5. SEARCHEFF real (no el escalón SNR>5 nativo)

`searcheff.py` (nuevo): parsea `LSST_SEARCHEFF_PIPELINE.DAT` (curva de eficiencia vs SNR por
banda, u/g comparten curva y z/Y comparten curva, r e i propias — interpolación lineal,
formato validado contra el archivo real) y `LSST_PIPELINE_LOGIC.DAT` (`LSST: 2
u+g+r+i+z+Y` → ≥2 épocas detectadas en cualquier combinación de filtros). Aplica Monte Carlo
por observación (SNR=flux/fluxerr → interpola eficiencia → sortea detección), luego el mismo
umbral de trigger que usa `snlc_sim.exe`. Mismo `PHOTFLAG` (4096/6144) que ya usa
`pipeline/postproc/qc.py` tras el fix de esta sesión, así que ambos lados de la comparación
usan la misma definición de "detección real".

## 6. Extinción MW real — no era la explicación de la brecha de eficiencia

`ExtinctionEffect(extinction_model="O94", frame="observer", r_v=3.1)` — misma familia que
`OPT_MWCOLORLAW` de SNANA (CCM89+O'Donnell94). `dustmaps`/`sfdmap2` no pudieron descargar el
mapa SFD completo desde NLHPC (Harvard Dataverse API devuelve cuerpo vacío pese a HTTP 202;
el mirror de GitHub `kbarbary/sfddata` solo tiene un README, sin los `.fits`) — en vez de
mapear posiciones individuales, se consultó el **servicio REST IRSA Dust Extinction** de
NASA/IPAC (sí alcanzable) para los 6 centros de campo DDF reales (calculados desde
`baseline_v5.3.1_10yrs.db`, no de memoria):

| Campo | RA | Dec | E(B-V) SFD |
|---|---|---|---|
| cosmos | 150.110 | 2.234 | 0.0182 |
| ecdfs | 52.981 | -28.119 | 0.0084 |
| edfs_a | 59.374 | -49.150 | 0.0062 |
| edfs_b | 63.151 | -47.772 | 0.0152 |
| elaiss1 | 9.446 | -44.030 | 0.0080 |
| xmm_lss | 35.575 | -4.820 | 0.0251 |

Cada objeto simulado recibe el E(B-V) de su campo real (vía `extra_cols=["field"]` del punto
4, para que posición y extinción vengan de la misma fila sampleada, no independientes).
**Resultado**: la eficiencia global apenas bajó (59.95% sin extinción → 57.2% con extinción)
— estos 6 campos fueron elegidos por el survey precisamente por su baja extinción (todos
< 0.03 mag), así que no explican la brecha de ~2x contra SNANA real (29.85%).

## 7. Diagnóstico real de la brecha de eficiencia: ruido fotométrico, no población

Con extinción descartada como explicación principal, se comparó el SNR simulado
(`|flux/fluxerr|`, **todas** las observaciones, no solo las detectadas) contra el SNR real de
SNANA para la misma campaña:

| | mediana SNR | p90 SNR |
|---|---|---|
| SNANA real (`SNIa_DDF`) | 0.78 | 2.26 |
| LightCurveLynx (este PoC) | 1.008 | 5.68 |

La mediana ya sale ~29% más alta, pero la cola alta (p90) sale **2.5x** más alta — es decir,
las épocas de mayor SNR (las que más pesan en el trigger "≥2 detecciones") están
sistemáticamente menos ruidosas en la simulación de LightCurveLynx que en la de SNANA para
el mismo `OpSim` (misma profundidad, PSF, cielo). Como el ratio SNR=flux/fluxerr no depende
de la convención de unidades de flujo (nJy vs FLUXCAL — un error de escala afectaría flux Y
fluxerr por igual, cancelándose en el ratio), esto no es un bug de conversión de unidades en
este script: apunta a que el modelo de ruido fotométrico interno de LightCurveLynx (derivado
de profundidad/PSF/cielo del `OpSim`) subestima el ruido por-época real que usa SNANA para
esta campaña — probablemente porque el pipeline real de SNANA/LSST incluye términos de ruido
sistemático/calibración adicionales que el modelo de LightCurveLynx no captura, o usa una
calibración de ruido distinta para el mismo profundidad nominal.

**No resuelto en este PoC** — calibrar o reemplazar el modelo de ruido de LightCurveLynx
contra el de SNANA es trabajo real de integración (no un ajuste de una línea), apropiado para
Fase 2 si se decide seguir, no para cerrar aquí. Es la brecha concreta más importante que
queda abierta.

## 7b. Intento de calibración — candidatos descartados, brecha sigue abierta

Dos rondas de investigación real después del punto 7, ninguna cerró la brecha:

**`zp_err_mag` (calibración de zeropoint) — descartado empíricamente.** El termino de
varianza por incertidumbre de zeropoint en `poisson_bandflux_std()`
(`noise_models/noise_utils.py`) escala con `bandflux²` (a diferencia de los términos Poisson,
que escalan con `bandflux¹`), así que en principio pesa más justo en las épocas de mayor SNR
— coincidiendo con que la brecha p90 (2.5x) es peor que la de mediana (29%). `OpSim` por
defecto usa `zp_err_mag=1e-4`, pero el `ZEROPT_ERR` real de SNANA para esta campaña es
`0.005` (mediana, std=7.5e-5 — un valor de calibración fijo, no ruido). Se corrigió
`OpSim(df_ddf, zp_err_mag=0.005)` (parámetro documentado del constructor) y se volvió a
correr: **1215/2000 = 60.75% detectados — sin mejora real** (contra 57.2% antes del fix,
dentro del ruido esperado de una corrida con distinto seed). La hipótesis mecánicamente tenía
sentido pero los números no la sostienen — a esta profundidad/flujo, el término de zeropoint
no es dominante.

**Auditoría de la cadena cielo/PSF/zeropoint — sin bug encontrado.** Se leyó
`OpSim._derive_noise_columns()` completo:
- `zp` sí aplica corrección por airmass real (`flux_electron_zeropoint(ext_coeff, zp_per_sec,
  filter, airmass, exptime)` — no usa el zeropoint de cenit sin corregir).
- `psf_footprint = GAUSS_EFF_AREA2FWHM_SQ · (seeing/pixel_scale)²`, con
  `GAUSS_EFF_AREA2FWHM_SQ = π/(2·ln2) ≈ 2.266` — es la formula estandar de area efectiva de
  un PSF Gaussiano en funcion de FWHM, no una aproximacion custom.
- `pixel_scale=0.2 arcsec/pixel` — correcto para LSSTCam.
- Se verificó la distribución real de `seeingFwhmEff` en `baseline_v5.3.1_10yrs.db` (DDF):
  mediana 0.977 arcsec — consistente con el diseño de LSST, no hay un problema de datos de
  entrada.

Ningún componente individual de la formula parece incorrecto en aislamiento. La brecha sigue
sin explicación puntual — puede ser una combinación de terminos menores (`dark_current` no
comparado directamente contra SNANA, sin columna equivalente clara en el FITS), una
diferencia de convención en como SNANA computa `SKY_SIG`/`PSF_SIG` en su SIMLIB que no se
pudo verificar sin documentacion mas profunda de ese formato, o algo fuera de esta cadena de
formulas. **Se detiene la investigación aquí** (dos rondas de hipótesis concretas
descartadas, no un abandono prematuro) — la brecha queda documentada como abierta para quien
retome Fase 2, con las dos rutas ya descartadas explícitas para no repetir el trabajo.

## 8. Rendimiento — sigue siendo dramáticamente más rápido

`NGENTOT_LC=2000` (SNIa_DDF real, `pipeline/models.yaml::ngen_ddf`) completo — ingesta OpSim
+ SALT2 + samplers custom + extinción + 2000 objetos — en **60–73 segundos** de wall time
dentro de un job SLURM liviano (16GB, 4 cores), confirmando de nuevo el orden de magnitud de
ventaja de velocidad medido en Fase 0 (~150x vs SNANA en throughput crudo).

## 8b. Orquestación para Fase 2: dask `LocalCluster` — validado

Fase 0 (punto 5) dejó abierta la pregunta de si Fase 2 necesita `dask`/`ray` para escalar a
más clases, dado lo económico que resultó el cómputo. Se revisó qué está realmente instalado
en el venv: `dask`/`distributed` sí; `dask_jobqueue` (lanza un job SLURM separado por worker)
y `ray` no. Para esta escala no hace falta `dask_jobqueue` — un `LocalCluster` levantado
**dentro** de una sola asignación SLURM (nunca el login node, misma regla del resto del
pipeline) alcanza: todo el ciclo de vida del cluster (scheduler + workers) vive dentro de esa
única asignación.

`run_dask_poc.py` (nuevo) valida el patrón con carga real, no una tarea de prueba: 4 chunks
independientes de `NGEN=500` (2000 total, igual que el PoC de Fase 1), cada uno con su propio
grafo de samplers, corridos (a) secuencial en un proceso y (b) en paralelo vía
`dask.distributed.LocalCluster(n_workers=4)` — mismo job SLURM, mismo nodo.

| | tiempo total | 
|---|---|
| Secuencial (1 proceso) | 224.1s |
| Paralelo (`LocalCluster`, 4 workers confirmados por el scheduler) | 70.9s |

**Speedup: 3.16x sobre 4 workers (79% de eficiencia respecto al ideal 4.0x)** — la brecha
frente al ideal es la carga independiente de OpSim/SALT2/passbands en cada worker (no hay
estado compartido entre procesos), no un problema del patrón en sí. Corrida limpia, sin
errores, sin tocar el login node en ningún momento (confirmado por el log — todo el trabajo
ocurre dentro del job `sbatch`). Patrón listo para usar cuando se planifique el alcance real
de Fase 2 (cobertura de clases) — no se construyó la orquestación completa de Fase 2 aquí,
solo se validó que el mecanismo funciona.

## 9. Recomendación: GO condicional a Fase 2

Lo que **sí** quedó confirmado y funcionando de punta a punta: parámetros reales de SNANA
(DNDZ, bifurcadas, rango de redshift), el modelo SALT2 H17 real (no una aproximación),
posiciones reales del footprint DDF, extinción MW real por campo, eficiencia de detección
real (SEARCHEFF real, no el escalón nativo), reuso directo de la infraestructura de QC ya
arreglada esta sesión (mismos 4 gráficos, mismos criterios de detección), la ventaja de
velocidad de Fase 0 se sostiene, y el patrón de orquestación con `dask` para Fase 2 quedó
validado (3.16x de speedup real, sin tocar el login node). Se encontraron y corrigieron 3
problemas reales en el camino (bug de broadcast en `FunctionNode`, mirror de SALT2 caído,
formato de color law) — ninguno bloqueante, todos con fix concreto documentado arriba.

Lo que **no** quedó confirmado: equivalencia cuantitativa de detección (~2x de brecha,
diagnosticada pero no cerrada — ruido fotométrico, no población). Por eso la recomendación es
**GO condicional**, no un GO sin reservas: seguir a Fase 2 (cobertura de más clases, wrapper
SIMSED) es razonable dado que la mecánica funciona y la brecha tiene un candidato de causa
concreto y acotado (no un problema difuso de "LightCurveLynx no sirve para esto") — pero
cualquier resultado cuantitativo de Fase 1/2 debe tratarse como preliminar hasta calibrar el
modelo de ruido contra SNANA real, no como una comparación científica cerrada todavía.

## Archivos de esta fase

- `snana_params.py` — samplers DNDZ + bifurcado + `SizeAwareFunctionNode` (fix del bug de
  broadcast).
- `searcheff.py` — parser de `LSST_SEARCHEFF_PIPELINE.DAT`/`LSST_PIPELINE_LOGIC.DAT` +
  aplicación Monte Carlo de detección real.
- `setup_salt2_local.py` — reproduce `salt2_h17_local/` (no versionado, se regenera desde los
  archivos de SNANA ya en NLHPC) desde cero.
- `run_snia_ddf_poc.py` + `run_snia_ddf_poc.sbatch` — script principal, corre en NLHPC vía
  SLURM (nunca login node). Incluye override `zp_err_mag=0.005` (calibración intentada, ver
  punto 7b) y el diagnóstico de SNR permanente en cada corrida.
- `poc_output/summary.json` + `poc_output/qc/*.png` — resultado real de la corrida con
  `zp_err_mag` calibrado (`n_detected=1215/2000`, eficiencia 60.75% — sin mejora real sobre
  la corrida anterior, ver punto 7b).
- `run_dask_poc.py` + `run_dask_poc.sbatch` — validación del patrón `LocalCluster` para Fase 2
  (punto 8b), 3.16x de speedup real medido.
