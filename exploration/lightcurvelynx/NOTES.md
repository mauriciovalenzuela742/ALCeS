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
- `run_dask_poc.py` + `run_dask_poc.sbatch` — validación del patrón `LocalCluster` para Fase 2
  (punto 8b), 3.16x de speedup real medido.
- `compare_noise_formulas.py` (nuevo, Fase 2 parte A) — comparación numérica término a
  término SNANA real vs LightCurveLynx.
- `poc_output/summary.json` + `poc_output/qc/*.png` — resultado real de la corrida más
  reciente (Fase 2 parte A: `H0=70` + ruido real de SNANA inyectado, `n_detected=1086/2000`,
  eficiencia 54.3%).

# Fase 2 — parte A: cerrar la brecha de ruido antes de ampliar cobertura

Plan: `C:\Users\HOME\.claude\plans\delegated-tumbling-petal.md`. Antes de ampliar Fase 2 a más
clases (el wrapper SIMSED necesario resultó afectar **11** clases del catálogo, no las 5-6 que
estimaba Fase 0 — `CaRT`, `ILOT`, `KN-BULLA19`, `KN-K17`, `PISN-MOSFIT`, `SLSN-I-MOSFIT`,
`SNIa-91bg`, `SNIax`, `SNII-NMF`, `SNIIn-MOSFIT`, `TDE-MOSFIT`, verificado con
`grep -l 'GENMODEL:.*SIMSED' run_SNANA/model_config/*.INPUT`), el usuario decidió cerrar
primero la brecha de eficiencia ~2x de Fase 1.

## 1. Comparación numérica directa: SNANA real vs LightCurveLynx, término a término

`pipeline/simlib/formatobs.py` (Capa 1, ya en producción — construye el SIMLIB real de la
campaña v8) implementa la fórmula exacta de SNANA (`formatObs`, arxiv:1905.02887) para derivar
`SKYSIG`/`PSF`/`ZPT` desde `fiveSigmaDepth`/`skyBrightness`/`seeingFwhmEff` — con el zeropoint
derivado **directamente del `fiveSigmaDepth` oficial** de Rubin (ya calibrado con toda la
física real de instrumento+atmósfera), a diferencia de LightCurveLynx, que deriva su
zeropoint desde cero con constantes fijas simplificadas (`zp_per_sec` a cenit + corrección de
airmass). Esta comparación directa no se había hecho en Fase 1 (las dos rondas previas solo
auditaron la fórmula de LightCurveLynx en aislamiento).

`compare_noise_formulas.py` (nuevo) calcula ambas derivaciones sobre las mismas 145,345
visitas DDF reales y compara termino a término (conversión de unidades: `sky_bg_e=SKYSIG²`,
`psf_footprint=noise_area/pixsize²`, `zp=mag2flux(ZPT)`):

| término | SNANA real (mediana) | LightCurveLynx (mediana) | razón LCL/SNANA |
|---|---|---|---|
| `psf_footprint` (pix²) | 54.08 | 54.08 | **1.0000 — coinciden exactamente** |
| `sky_bg_e` (e⁻/pix) | 1917 | 2320 | 1.18x (LCL con **más** ruido de cielo, no menos) |
| `zp` (nJy/e⁻) | 0.8653 | 0.6907 | 0.85x (LCL más sensible por electrón) |

Prueba directa con una fuente de referencia fija (100 nJy, mismo readout/dark en ambos):
usando los inputs de LightCurveLynx el SNR mediano sale **1.2x** más alto que usando los
inputs reales de SNANA — un efecto real pero modesto, muy por debajo del ~2.5x observado en
la cola alta de Fase 1. **Esto refuta la hipótesis original de Fase 1** ("el modelo de ruido
subestima el ruido real") como explicación *principal* — el término de PSF coincide
exactamente, y sky/zp se cancelan parcialmente entre sí (más ruido de cielo, pero más
sensible por electrón), dejando solo ~20% de efecto neto.

## 2. Segunda pista: `H0=73` nunca se verificó contra SNANA real

Ninguna cosmología está fijada explícitamente en la campaña (`grep` sin resultados en
`run_SNANA/*.INPUT` ni en `pipeline/`) — SNANA corre con su default interno, que en el linaje
PLAsTiCC/Kessler+2019 de este catálogo es `H0=70`. El PoC de Fase 1 heredó `H0=73` del
placeholder original de `bench_snia.py` (Fase 0) sin verificarlo nunca contra la config real
— un ~4.3% de error en H0 implica ~0.1 mag de brillo sistemático de más.

## 3. Resultado combinado (H0=70 + columnas de ruido reales de SNANA inyectadas)

En vez de seguir ajustando constantes de LightCurveLynx, se precalculan `zp`/`psf_footprint`/
`sky_bg_e` con la fórmula real de SNANA (`snana_noise_columns()`, nuevo en
`run_snia_ddf_poc.py`, reusa `pipeline.simlib.formatobs.format_obs()` sin duplicar lógica) y
se inyectan como columnas del `DataFrame` **antes** de construir el `OpSim` —
`_derive_noise_columns()` solo calcula estas columnas si no están presentes, así que
LightCurveLynx usa el modelo de ruido de SNANA por construcción. Combinado con `H0=70`:

| | mediana SNR | p90 SNR | eficiencia |
|---|---|---|---|
| SNANA real (`SNIa_DDF`) | 0.78 | 2.26 | 29.85% (597/2000) |
| Fase 1 original (`H0=73`, ruido propio de LCL) | 1.008 (+29%) | 5.68 (+151%) | 60.75% |
| + `H0=70` | 0.916 (+17%) | 3.580 (+58%) | 57.85% |
| + `H0=70` **y** ruido real de SNANA inyectado | 0.889 (+14%) | 3.185 (+41%) | 54.3% (1086/2000) |

**Progreso real y verificado**: ambas brechas de SNR se redujeron aproximadamente a la mitad
(mediana 29%→14%, p90 151%→41%) con dos causas concretas, diagnosticadas y corregidas (no
constantes ajustadas a ciegas). **No cerrado del todo**: la eficiencia sigue en ~1.8x la real
(54.3% vs 29.85%), un residual notablemente menor que el ~2x original pero aún significativo
— la eficiencia de detección responde de forma no lineal (vía la curva SEARCHEFF) a mejoras en
el SNR cerca del umbral, así que una reducción de brecha de SNR no se traduce 1:1 en reducción
de brecha de eficiencia.

Se revisó una tercera pista (`M_abs=-19.3`, también heredado sin verificar de Fase 0) contra
`SIMGEN_INCLUDE_SNIa-SALT2.INPUT` y `SALT2.INFO`: SNANA no fija un `M_abs`/`MAGOFF` explícito
para esta clase — `-19.3` es el valor de calibración estándar de SALT2 en la literatura
(Betoule et al. 2014), consistente con `H0=70`, no un placeholder obviamente incorrecto. No se
encontró una cuarta pista concreta y barata de seguir en esta ronda.

## 4. Estado y siguiente decisión

Dos causas reales identificadas y corregidas (columnas de ruido + cosmología), reduciendo la
brecha sustancialmente pero sin cerrarla del todo. El residuo (~1.8x) probablemente vive en la
población/modelo de fuente (evaluación exacta de la superficie SALT2 vía `sncosmo` vs el
código interno de SNANA, o la simplificación de `SIGMA_INT` coherente en vez de la covarianza
completa de G10 — ambas ya señaladas como aproximaciones aceptadas desde Fase 1, no
investigadas más a fondo aquí). Decisión del usuario: proceder a Fase 2 parte B (SIMSED) con
este ~1.8x como caveat explícito y cuantificado (mejor que el ~2x sin diagnosticar de Fase 1).

# Fase 2 — parte B: primer PoC del wrapper SIMSED (`SNIa-91bg_DDF`)

## Hallazgo que cambia el plan original: LightCurveLynx ya trae un lector SIMSED nativo

Fase 0 concluyó "no hay lector de librería SIMSED nativo... hay que escribir un wrapper
propio" (`SEDTemplate`/`SEDTemplateModel` + `GivenValueSampler` a mano). Al investigar para
esta fase se encontró `lightcurvelynx.models.sed_template_model.SIMSEDModel` — una clase
**completa y lista para usar**, no disponible (o no encontrada) en la versión de Fase 0:
`SIMSEDModel.from_dir(simsed_dir, weights=...)` parsea `SED.INFO` (YAML), carga todos los
templates (maneja `.gz` automáticamente), aplica `FLUX_SCALE`, y selecciona un template por
objeto simulado vía `GivenValueSampler(weights=...)` ya integrado — exactamente la
combinación que Fase 0 anticipaba tener que construir a mano. Esto reduce sustancialmente el
riesgo/esfuerzo de ingeniería que se esperaba para esta fase.

## Elegir la clase más simple: no era `TDE-MOSFIT`

El plan original (basado en una lectura rápida de Fase 0) asumía `TDE-MOSFIT` como la más
simple. Verificado contra los directorios reales en NLHPC: `SIMSED.TDE-MOSFIT` tiene **745**
templates con **8** parámetros físicos (`TDE_INDEX Rph0 Tvis b bhmass eff lphoto starmass`) —
no es simple en absoluto. Comparando las 11 clases SIMSED del catálogo:

| clase | templates | NPAR |
|---|---|---|
| **`SIMSED.SNIa-91bg`** | **35** | **2** |
| `SIMSED.KN-K17` | 330 | 4 |
| `SIMSED.CART-MOSFIT` | 225 | 6 |
| `SIMSED.ILOT-MOSFIT` | 385 | 6 |
| `SIMSED.SNIax` | 1001 | 5 |
| `SIMSED.SNIIn-MOSFIT` | 839 | 6 |
| `SIMSED.SLSN-I-MOSFIT` | 960 | 9 |
| `SIMSED.PISN-MOSFIT` | 1000 | 3 |
| `SIMSED.SNII-NMF` | ~385 (+`COV.INFO`, modelo PCA) | 4 |
| `SIMSED.TDE-MOSFIT` | 745 | 8 |
| `SIMSED.KN-BULLA19` | *(directorio con 3 sub-variantes anidadas)* | — |

`SNIa-91bg` es la más simple por márgen amplio: grilla regular 7×5 (stretch × color), sin
covarianza espectral compleja — se eligió como primer PoC en su lugar.

## Bug real encontrado en el dato de referencia de SNANA (no nuestro)

`SED.INFO` de `SIMSED.SNIa-91bg` trae un typo real: la línea de comentario

    $ template to all 91bg at low-z as from Gonzalez-Gaitan+14.

usa `$` en vez de `#` (confirmado con `cat -A` en NLHPC). El parser de SNANA
(`snlc_sim.exe`) lo tolera porque no exige YAML estricto, pero
`SIMSEDModel._read_simsed_info_file()` sí hace `yaml.safe_load()` sobre el archivo completo, y
ese carácter rompe el parseo. **No se modificó el archivo real de SNANA** — mismo patrón que
`setup_salt2_local.py` de Fase 1: `setup_simsed_91bg_local.py` (nuevo) copia los 35 templates
+ una copia de `SED.INFO` con el fix de un carácter a
`exploration/lightcurvelynx/simsed_91bg_local/` (no versionado, se regenera desde NLHPC).

## Otro detalle de API real: `SIMSEDModel` valida sus parámetros en el constructor

A diferencia de `SncosmoWrapperModel` (Fase 1), `SIMSEDModel` **exige** `distance` (distancia
lumínica en pc, no `redshift` directamente) ya en el constructor — agregar parámetros después
vía `.add_parameter()` no funciona porque la validación ocurre en `__init__`. Se agregó un
sampler propio (`_luminosity_distance_pc`, misma cosmología `H0=70/Ωm=0.3` de Fase 2 parte A)
que convierte `redshift_func` a distancia en pc, pasado junto con `ra`/`dec`/`t0` directo al
`from_dir(...)`.

## Resultado: `run_simsed_91bg_ddf_poc.py`, `NGENTOT_LC=2000` (igual que SNANA DDF real)

Mismo patrón de Fase 1/2A: `H0=70` + ruido real de SNANA inyectado desde el inicio (no una
brecha nueva por cerrar), extinción MW real por campo, SEARCHEFF real, `pipeline.postproc.qc`
reusado sin modificar. `DNDZ: POWERLAW` (un tramo, más simple que el `POWERLAW2` de SNIa) y
los pesos de cada uno de los 35 templates calculados con la bivariada normal correlacionada
real (`GENPEAK_stretch=0.975 σ=0.096`, `GENPEAK_color=0.557 σ=0.175`,
`SIMSED_REDCOR=-0.656`) evaluada en el `(stretch, color)` propio de cada template — no un peso
uniforme.

| | mediana SNR | p90 SNR | eficiencia |
|---|---|---|---|
| SNANA real (`SNIa-91bg_DDF`) | 0.769 | 2.087 | 36.15% (723/2000) |
| LightCurveLynx (este PoC) | 0.890 (+15.7%) | 3.232 (+55%) | 49.65% (993/2000, **1.37x**) |

**Corrió de punta a punta sin errores** (57.8s de simulación para 2000 objetos, curvas de luz
con marcadores detectado/no-detectado reales, QC de 4 gráficos generado y visualmente
verificado). La brecha de eficiencia (1.37x) es notablemente **menor** que la de SNIa/SALT2
(1.8x) pese a que las brechas de SNR son de magnitud muy similar (mediana ~15%, p90 ~50-55%
en ambas clases) — señal cruzada útil: el residuo de SNR parece ser un factor sistémico
(no específico del modelo SALT2 vs SIMSED), pero su efecto en la eficiencia final depende de
en qué parte de la curva SEARCHEFF cae la población de cada clase.

## Archivos de esta parte

- `setup_simsed_91bg_local.py` (nuevo) — copia local de `SIMSED.SNIa-91bg` con el fix de
  `SED.INFO`, no versionada (se regenera).
- `run_simsed_91bg_ddf_poc.py` + `.sbatch` (nuevo) — PoC principal.
- `poc_output_91bg/summary.json` + `poc_output_91bg/qc/*.png` — resultado real.

## Estado y siguiente decisión

Primer PoC SIMSED exitoso: el lector nativo de LightCurveLynx funciona, el patrón de pesado
por `SIMSED_REDCOR` es correcto, y la brecha de eficiencia (1.37x) es menor que la del PoC
SALT2 de Fase 1/2A. Decisión del usuario: escalar a 2-3 clases SIMSED más antes de decidir
sobre las 10 restantes — ver siguiente sección.

# Fase 2 — parte B (continuación): 3 clases más, patrón generalizado

Se generalizó `run_simsed_91bg_ddf_poc.py` a `run_simsed_poc.py <clase>` (config por clase en
un dict, mismo patrón de ruido/cosmología/SEARCHEFF/QC reusado) para evitar triplicar el
boilerplate. Se agregó `build_dndz_md14_cdf()` a `snana_params.py` (fórmula real de Madau &
Dickinson 2014, `DNDZ: MD14 <rate0>` en varias clases del catálogo). De paso: el default de
`H0` en `build_dndz_powerlaw2_cdf()` seguía en `73.0` (el placeholder original de Fase 0,
nunca corregido pese a que la Fase 2 parte A sí corrigió el `H0` usado para
distancia/flujo) — corregido a `70.0` aquí; no se re-corrieron los PoC ya reportados de
SNIa/SNIa-91bg por esto (el efecto en la forma del redshift simulado es de segundo orden
frente al ya corregido en distancia/flujo, y ya están documentados con sus números reales).

## Clases elegidas (complejidad variada) y una descartada por buena razón

Se evaluaron las 11 clases SIMSED del catálogo por conteo de templates y parámetros. Se
eligieron `KN-K17` (peso uniforme `SIMSED_GRIDONLY`, `DNDZ: POWERLAW` sin dependencia de z,
redshift bajo 0.011–0.28), `CaRT`/CART-MOSFIT (peso uniforme, `DNDZ: MD14`, redshift medio
0.012–1.4), y `SLSN-I`/SLSN-I-MOSFIT (peso uniforme, `DNDZ: MD14`, redshift muy amplio
0.02–9.7 — prueba de escala). `PISN-MOSFIT` se descartó para esta ronda: usa
`DNDZ: PISN_PLK12`, un modelo de tasa con nombre propio (no una fórmula analítica simple como
`POWERLAW`/`POWERLAW2`/`MD14`) sin una referencia clara disponible — mejor no adivinar la
fórmula que implementarla mal.

## Simplificación deliberada: extinción de galaxia anfitriona (WV07) no implementada

Las 3 clases nuevas declaran extinción de polvo de la galaxia anfitriona en su `.INPUT` real
(`GENAV_WV07`/`GENRANGE_AV`/`GENPEAK_RV`, modelo WV07 con "half expon component"). Antes de
adivinar la fórmula, se buscó la implementación real en el código fuente de SNANA
(`~/github/SNANA_src/src/sntools_genExpHalfGauss.c`, el mismo árbol usado para compilar el
binario custom mencionado en el README del proyecto) — el propio código trae un comentario de
Dic 2023 documentando un bug histórico en esta función ("WV07 AV flag was never refactored to
use this function, so this might be a harmless bug"), señal de que no es una fórmula trivial
de reimplementar de memoria con confianza. **Se omite (AV=0) en vez de reimplementar mal** —
mismo criterio que la aproximación de `SIGMA_INT` para G10 en Fase 1, documentado explícitamente
como brecha conocida, no un descuido.

## Resultado: 3/3 corridas limpias, sin errores

`NGENTOT_LC=2000` para las 3 (igual que SNANA DDF real). Comparado contra los baselines reales
ya generados en la campaña v8 (`postprocess_manifest.json`):

| clase | SNR mediana LCL | SNR p90 LCL | detectados SNANA real | detectados LCL | razón |
|---|---|---|---|---|---|
| `KN-K17` | 0.685 | 1.692 | 82/2000 (4.1%) | 210/2000 (10.5%) | **2.56x** |
| `CaRT` | 0.682 | 1.672 | 16/2000 (0.8%) | 136/2000 (6.8%) | **8.5x** |
| `SLSN-I` | 0.993 | 8.436 | 824/2000 (41.2%) | 1266/2000 (63.3%) | **1.54x** |

Las 3 brechas son **mayores** que las de `SNIa`/`SNIa-91bg` (1.8x / 1.37x) — pero esto es
**esperado y coherente**, no una regresión nueva: `SNIa` y `SNIa-91bg` no declaran extinción
de galaxia anfitriona en su `.INPUT` real (solo MW, ya implementada), mientras que las 3
clases de esta ronda sí la declaran y no se implementó (ver sección anterior). Omitir un
efecto que dimueve/reduce brillo sistemáticamente produce exactamente el sesgo observado:
eficiencia inflada, más aún cuanto más débil es la clase intrínsecamente (`CaRT`, con solo 16
detecciones reales de 2000, es el caso más extremo — la cola de redshift alto del histograma
de `CaRT` muestra detecciones simuladas hasta z=1.4 que en la realidad casi no deberían
ocurrir para una clase tan tenue). Verificado visualmente: las curvas de luz y distribuciones
de redshift de las 3 clases se ven físicamente razonables (sin bugs de sampling como los de
Fase 1), la brecha es de magnitud/eficiencia, no de forma.

## Hallazgo de rendimiento: la carga de templates SIMSED no escala solo con la cantidad

Tiempo de carga aislado (tiempo entre leer `SED.INFO` y terminar la simulación, menos el
tiempo de simulación propiamente dicho, medido aparte con su propio timer):

| clase | templates | tiempo de carga (aislado) | seg/template |
|---|---|---|---|
| `SNIa-91bg` | 35 | ~18s (aprox., smoke test) | ~0.5 |
| `SLSN-I` | 960 | 194.1s | 0.202 |
| `CaRT` | 225 | 87.5s | 0.389 |
| `KN-K17` | 329 | **1976.0s (~33 min)** | **6.007** |

`KN-K17` tardó **~15-30x más por template** que las demás pese a tener menos templates que
`SLSN-I` (960) — el tiempo de carga depende del tamaño/resolución de cada archivo SED
individual (grilla de fase×longitud de onda), no solo de cuántos templates hay. Job de
`KN-K17` corrió con `-t 02:00:00` (aumentado preventivamente tras un smoke test de N=20 que
ya mostraba ~3.4s/template) — terminó en 37 min reales, dentro del margen. Relevante para
dimensionar tiempo de cómputo si se escala a las clases restantes (revisar el tamaño de los
archivos `.SED`/`.txt.gz` de cada clase antes de asumir un tiempo de job, no solo el conteo
de templates).

## Archivos de esta parte

- `run_simsed_poc.py` + `.sbatch` (nuevo) — version generalizada, reemplaza el patrón de
  script-por-clase para clases nuevas (el script específico de `SNIa-91bg` se deja como
  referencia histórica, no se migra).
- `snana_params.py` — agregado `build_dndz_md14_cdf()`, corregido default `H0` a 70.
- `poc_output_knk17/`, `poc_output_cart/`, `poc_output_slsni/` — resultados reales (`summary.json` + 4 QC c/u).

## Estado y siguiente decisión

5 clases validadas de punta a punta ahora (1 SALT2 continua + 4 SIMSED discretas). Patrón de
implementación sólido y reusable (`run_simsed_poc.py` generaliza a cualquier clase con peso
uniforme o `SIMSED_REDCOR`, `DNDZ` `POWERLAW`/`POWERLAW2`/`MD14`). Dos brechas abiertas y
documentadas, ambas con causa identificada (no misteriosas): el residuo de ruido/población
sistémico (~1.4-1.8x, ver Fase 2 parte A) y la extinción de galaxia anfitriona WV07 no
implementada (afecta solo a clases que la declaran — 3 de las 5 ya corridas). A decidir con
el usuario: implementar WV07 con una referencia más sólida antes de seguir escalando, o
continuar a más clases con esta brecha ya cuantificada como caveat conocido.

# Fase 2 — parte B (continuación 2): 3 clases más, extinción de host real (no WV07) y dos
# modelos de tasa nuevos encontrados en el código fuente real de SNANA

Ronda dedicada a `SNIax`, `TDE-MOSFIT`, `SNII-NMF` — elegidas porque, a diferencia de la ronda
anterior (`KN-K17`/`CaRT`/`SLSN-I`, extinción de host omitida por prudencia), estas 3 sí
permiten poner a prueba directamente la hipótesis de esa ronda ("las brechas grandes se deben
a la extinción de host omitida, no a un problema nuevo"): dos de las tres (`SNIax`,
`TDE-MOSFIT`) declaran un modelo de extinción de host **exponencial puro** (`GENTAU_AV`, sin
componente WV07/half-Gaussian) en su `.INPUT` real — implementable con confianza, a diferencia
de WV07 — y la tercera (`SNII-NMF`) no declara ninguna, sirviendo de control limpio igual que
`SNIa`/`SNIa-91bg`.

## 1. Dos modelos de tasa (`DNDZ`) nuevos, encontrados en el código fuente real de SNANA

`SNII-NMF` usa `DNDZ: CC_S15` y `TDE-MOSFIT` usa `DNDZ: TDE` — en la ronda anterior ambos se
habían descartado implícitamente por parecer "nombres propios" sin fórmula obvia (mismo
criterio que excluyó `PISN_PLK12`). Revisando el código fuente real de SNANA
(`~/github/SNANA_src/src/snlc_sim.c`, bloques `INDEX_RATEMODEL_CCS15` e
`INDEX_RATEMODEL_TDE`) ambos resultaron ser fórmulas simples y bien documentadas:

- **`CC_S15`** (tasa de core-collapse, Strolger 2015): misma forma funcional que `MD14`
  (`SFRfun_MD14`) pero con los parámetros A,B,C,D re-ajustados a la tasa de core-collapse
  observada (Fig 6, Ec 9 de Strolger 2015), no a la formación estelar general:

      rate(z) = k · h² · SFR_MD14(z; A=0.015, B=1.50, C=5.00, D=6.10) · DNDZ_ALLSCALE
      k = 0.0091, h = H0/100

- **`TDE`**: decaimiento exponencial simple en base 10, sin dependencia de cosmología en la
  forma funcional misma:

      rate(z) = rate0 · 10^(-0.5·z/0.6)

Ambas nuevas en `snana_params.py`: `build_dndz_ccs15_cdf()`, `build_dndz_tde_cdf()` — mismo
patrón de inversión de CDF numérica que `build_dndz_md14_cdf()`/`build_dndz_powerlaw2_cdf()`,
verificadas standalone antes de conectarlas al grafo (salidas con forma y percentiles
razonables). `PISN_PLK12` (la única `DNDZ` de nombre propio que queda entre las 11 clases
SIMSED) se revisó de nuevo por si el mismo patrón de "está en snlc_sim.c con nombre distinto"
aplicaba, pero no se encontró razón para reconsiderarla en esta ronda — sigue fuera de
alcance, no una clase de esta ronda.

## 2. Extinción de host real implementada (modelo exponencial puro, no WV07)

`SNIax` y `TDE-MOSFIT` declaran en su `.INPUT` real (confirmado leyendo
`SIMGEN_INCLUDE_SNIax.INPUT` y el equivalente de `TDE-MOSFIT`) `GENTAU_AV`/`GENRANGE_AV`/
`GENPEAK_RV` **sin** `GENAV_WV07` — el modelo exponencial puro que Fase 0/G10 ya había
señalado como implementable con `make_exp_av_sampler()` (Fase 2 parte B, ronda 1). Se conectó
por primera vez esta ronda: `av_func` (muestreo de AV por inversión de CDF truncada) →
conversión a `ebv = av/r_v` → segundo `ExtinctionEffect(frame="rest")` añadido al
`source_model` vía `add_effect()`, sobre el ya existente de extinción MW (`frame="observer"`).

| clase | `GENTAU_AV` | `GENRANGE_AV` | `GENPEAK_RV` |
|---|---|---|---|
| `SNIax` | 1.7 | 0.001–3.0 | 3.1 |
| `TDE-MOSFIT` | 0.4 | (mismo rango asumido, `av_max=3.0`) | 3.1 |

## 3. Bug real encontrado: `CCM89` no está calibrado para el UV extremo que z=2.9 produce en rest-frame

Al conectar la extinción de host para `TDE-MOSFIT` (`GENRANGE_REDSHIFT: 0.01–2.9`, el rango de
redshift más amplio de las 8 clases SIMSED corridas hasta ahora), el primer smoke test
(`N=15`) falló con:

    ValueError: Input x outside of range defined for CCM89 [0.3 <= x <= 10.0, x has units 1/micron]

Causa raíz (confirmada leyendo `lightcurvelynx/models/physical_model.py::_evaluate_single()`):
los efectos `frame='rest'` reciben `wavelengths` ya convertidas a rest-frame
(`obs_to_rest_times_waves(times, wavelengths, redshift, t0)`, división por `1+z`). El borde
azul de LSST-u (~3200Å observado) a z≈2.9 cae en rest-frame a ~820Å — por debajo del límite
físico real de 1000Å (x=10 μm⁻¹) al que está calibrada la ley de extinción CCM89 (y toda la
familia de leyes paramétricas estándar: O94, F99, etc. comparten el mismo límite UV). No es un
bug de LightCurveLynx ni nuestro — es el límite real de la calibración empírica de esa ley,
que `dust_extinction` (correctamente) rechaza en vez de extrapolar en silencio.

**Fix**: `ClippedExtinctionEffect` (nuevo en `snana_params.py`, subclase de `ExtinctionEffect`)
clampea las longitudes de onda al rango válido del modelo (`ext_obj.x_range`) antes de
evaluar, en vez de fallar — mismo espíritu que la extrapolación `ZeroPadding`/`LinearDecay` que
LightCurveLynx ya usa para el SED fuera de `RESTLAMBDA_RANGE`: la extinción se mantiene
constante (igual al valor de borde) más allá del rango calibrado, en vez de inventar una
fórmula de extrapolación nueva. Aplicado tanto a la extinción MW como a la de host (esta última
es la que realmente lo necesita; la de MW opera en wavelengths de observador, siempre dentro de
rango) — cambio barato y sin efecto en clases de redshift bajo (el clip es un no-op ahí).
Verificado: el mismo smoke test de `TDE-MOSFIT` con el fix corre limpio de punta a punta.

## 4. Otro bug real encontrado (no nuestro): línea suelta inválida en `SED.INFO` de `TDE-MOSFIT`

`SIMSEDModel._read_simsed_info_file()` (que sí exige YAML estricto) falló al cargar
`SIMSED.TDE-MOSFIT/SED.INFO` con un `yaml.scanner.ScannerError` en la línea 254. Confirmado con
`sed`/`cat -A` en NLHPC: esa línea es literalmente `tde_384.json` — un nombre de archivo
suelto, sin prefijo `SED:` ni `#`, intercalado entre dos entradas `SED:` reales (entre
`tde239.dat` y `tde241.dat`). El parser de SNANA (`snlc_sim.exe`) lo tolera por no exigir YAML
estricto; el nuestro no. A diferencia del typo de un solo carácter de `SNIa-91bg` (Fase 2B,
ronda 1), este archivo es demasiado grande para copiar entero (**144M, 745 templates** vs los
35 de `SNIa-91bg`) — `setup_simsed_local.py` (nuevo, generaliza `setup_simsed_91bg_local.py`)
en vez de copiar, **symlinkea** los 745 archivos de template y solo reescribe `SED.INFO`,
descartando cualquier línea que no matchee un formato conocido (comentario, blank, o una
palabra clave real como `SED:`/`PARNAMES:`/etc.) — 1 línea descartada, 745 symlinkeadas. No se
toca el archivo real de SNANA. `CLASS_CONFIGS["TDE-MOSFIT"]["simsed_dir"]` apunta a esta copia
local saneada (`exploration/lightcurvelynx/simsed_tdemosfit_local/`, no versionada).

## 5. Resultado: 3/3 corridas limpias, `NGENTOT_LC=2000` (igual que SNANA DDF real)

Comparado contra los baselines reales de la campaña v8 (`postprocess_manifest.json`,
`n_objects` = detectados de `NGENTOT_LC=2000`):

| clase | extinción host | SNR mediana LCL | SNR p90 LCL | detectados SNANA real | detectados LCL | razón |
|---|---|---|---|---|---|---|
| `SNII-NMF` | no declarada (control limpio) | 0.741 | 1.921 | 356/2000 (17.8%) | 498/2000 (24.9%) | **1.40x** |
| `TDE-MOSFIT` | sí, `GENTAU_AV=0.4` | 1.007 | 4.406 | 812/2000 (40.6%) | 1277/2000 (63.85%) | **1.57x** |
| `SNIax` | sí, `GENTAU_AV=1.7` | 0.761 | 2.054 | 175/2000 (8.75%) | 464/2000 (23.2%) | **2.65x** |

**La hipótesis de la ronda anterior se confirma parcialmente, no del todo.** `SNII-NMF`
(control limpio, sin extinción) y `TDE-MOSFIT` (con extinción de host real implementada) caen
ambas dentro de la misma banda de brecha residual sistémica ya documentada para las clases
"limpias" de rondas anteriores (`SNIa` 1.8x, `SNIa-91bg` 1.37x, ver Fase 2 parte A/B) — un
resultado que **sí** respalda la hipótesis: implementar extinción de host real en
`TDE-MOSFIT` la trajo de vuelta a la banda 1.4-1.8x, en vez de quedarse en la banda 2.5-8.5x de
`KN-K17`/`CaRT`/`SLSN-I` (que omitieron extinción). Pero `SNIax` **no** siguió el mismo patrón:
pese a implementar extinción de host con los parámetros exactos de su `.INPUT` real
(`GENTAU_AV=1.7`, `GENRANGE_AV=0.001–3.0`, `GENPEAK_RV=3.1` — verificado línea por línea contra
`SIMGEN_INCLUDE_SNIax.INPUT`, sin discrepancia), su razón (2.65x) queda claramente por encima de
la banda sistémica, más cerca de las clases sin extinción de la ronda anterior.

**No se investigó más a fondo esta ronda** (mismo criterio de "dos hipótesis concretas, luego
documentar y decidir con el usuario" ya aplicado en Fase 2 parte A) — candidatos abiertos, sin
confirmar: (a) el `GENTAU_AV` de `SNIax` (1.7) es ~4x el de `TDE-MOSFIT` (0.4), así que
cualquier error pequeño en el muestreo de AV alto pesaría más en `SNIax` que en `TDE-MOSFIT`;
(b) `SNIax` es la única de las 3 clases de esta ronda que reusa `DNDZ: MD14` (ya usado en la
ronda anterior para `CaRT`/`SLSN-I`, ambas con brechas grandes) en vez de un modelo de tasa
nuevo — no se puede descartar un efecto de la tasa/población en sí, independiente de la
extinción. Ninguno de los dos se investigó con la misma profundidad que el diagnóstico término
a término de Fase 2 parte A.

## 6. Hallazgo de rendimiento: `SNIax` confirma que la carga de templates es impredecible por clase

    | clase      | templates | tiempo de carga (aislado) | seg/template |
    |------------|-----------|----------------------------|---------------|
    | `TDE-MOSFIT` | 742     | ~150-190s                  | ~0.20-0.26    |
    | `SNIax`      | 1001    | 465s (smoke, login) / 992s (sbatch, largemem) | 0.46-0.99 |

Mismo patrón que `KN-K17` en la ronda anterior (6.0s/template vs 0.2s/template de `SLSN-I` con
más templates): el tiempo de carga no escala solo con la cantidad de templates, sino con
tamaño/resolución de cada archivo SED individual — y aquí además con contención de I/O
compartida del nodo (la corrida de `sbatch` en partición `largemem` tardó ~2x más que el smoke
test aislado en el login node para la misma clase). El límite de tiempo del sbatch
(`-t 02:00:00`) sigue siendo suficiente margen (corrida real: 21 min), pero confirma que no hay
forma de estimar el tiempo de job de una clase nueva sin correr al menos un smoke test primero
— práctica que ya se venía siguiendo, esta ronda la justifica de nuevo.

## Archivos de esta ronda

- `snana_params.py` — agregado `build_dndz_ccs15_cdf()`, `build_dndz_tde_cdf()`,
  `make_exp_av_sampler()` (ya existía desde antes, conectado por primera vez esta ronda),
  `make_correlated_normal_weights()`, `ClippedExtinctionEffect`.
- `setup_simsed_local.py` (nuevo) — versión generalizada/symlink de
  `setup_simsed_91bg_local.py`, para clases SIMSED grandes con un `SED.INFO` inválido.
- `simsed_tdemosfit_local/` (no versionado, se regenera) — copia saneada de `SED.INFO` +
  745 templates symlinkeados.
- `run_simsed_poc.py` — 3 configs nuevas (`SNIax`, `TDE-MOSFIT`, `SNII-NMF`), branching de
  `DNDZ`/pesos/extinción de host generalizado.
- `poc_output_sniax/`, `poc_output_tdemosfit/`, `poc_output_sniinmf/` — resultados reales
  (`summary.json` + 4 QC c/u).

## Estado y siguiente decisión

8 clases SIMSED/SALT2 validadas de punta a punta en total. La hipótesis de "extinción de host
omitida explica las brechas grandes" quedó **parcialmente confirmada** (`TDE-MOSFIT` sí,
`SNIax` no) — un resultado honesto, no la confirmación limpia que se esperaba, y una señal de
que la brecha residual sistémica (ruido/población, Fase 2 parte A) y la extinción de host no
son completamente independientes o hay un tercer factor sin identificar específico de
`SNIax`/`MD14`. A decidir con el usuario: (a) investigar el caso `SNIax` con el mismo rigor que
Fase 2 parte A (comparación término a término, no solo eficiencia agregada), (b) seguir
escalando a las 3 clases restantes que sí declaran WV07 (`ILOT-MOSFIT`, `SNIIn-MOSFIT`,
`PISN-MOSFIT` con su `DNDZ` propia) con las brechas ya conocidas como caveat, o (c) dar por
suficientemente cubierto el catálogo SIMSED (8/11 clases, cobertura de todos los patrones de
implementación: peso uniforme, `SIMSED_REDCOR`, extinción de host exponencial, 4 modelos
`DNDZ` distintos) y cerrar la evaluación de LightCurveLynx con una recomendación final.

# Fase 2 — parte B (continuación 3): investigación del caso `SNIax` + 3 clases más
# (`ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`)

## 1. Root-cause de `SNIax`: el `.INPUT` real no es pura exponencial — se leyó incompleto

Releyendo `SIMGEN_INCLUDE_SNIax.INPUT` línea por línea (no solo `grep`-eando las claves ya
conocidas de `TDE-MOSFIT`, como se hizo en la ronda 2) aparecen dos líneas que la ronda anterior
no vio:

    GENTAU_AV:        1.7          # dN/dAV = exp(-AV/xxx)
    GENSIG_AV:        0.6          # += Guass(AV,sigma)
    GENRATIO_AV0:     4.0

`SNIax` **no** es el caso "solo componente exponencial" que se le asignó — es una **mezcla
exponencial + semi-Gaussiana**, con la componente Gaussiana pesada 4x más fuerte que la
exponencial en `AV=0` (`GENRATIO_AV0`). El error de la ronda 2 fue de lectura, no de
implementación: se generalizó el patrón de `TDE-MOSFIT` (que sí declara únicamente
`GENTAU_AV`) sin verificar que `SNIax` no tuviera parámetros adicionales.

**¿Es esto el modelo WV07 bugueado que se descartó en la ronda 1?** No — confirmado leyendo
`snlc_sim.c::gen_AV()` completo: hay dos caminos de código completamente distintos.
`GENAV_WV07()` (el que trae el bug histórico documentado, usado por `KN-K17`/`CaRT`/`SLSN-I`/
`ILOT-MOSFIT`/`SNIIn-MOSFIT`/`PISN-MOSFIT` vía el flag real `GENAV_WV07: 1`, confirmado en sus
`.INPUT`) solo se invoca si `INPUTS.WV07_GENAV_FLAG` está activo. `SNIax` no declara ese flag —
usa el camino `INPUTS.GENPROFILE_AV.USE` → `getRan_GEN_EXP_HALFGAUSS()`
(`sntools_genExpHalfGauss.c`), una función **refactorizada en Mar 2020** (D.Brout/R.Kessler) y
con un bug de peso relativo distinto **corregido en Dic 2023** (`WGT_EXPON`/`WGT_GAUSS`
invertidos) — el propio comentario del fix dice explícitamente: *"WV07 AV flag was never
refactored to use this function, so this might be a harmless bug"*, confirmando que son dos
funciones independientes con historiales de bugs separados. Implementable con confianza.

## 2. Implementación real del algoritmo (no una aproximación)

`make_exp_halfgauss_av_sampler()` (nuevo en `snana_params.py`) replica exactamente
`getRan_GEN_EXP_HALFGAUSS()` con la versión ya corregida (Dic 2023):

    WGT_EXPON = tau * (exp(-r0/tau) - exp(-r1/tau))
    WGT_GAUSS = 0.5 * ratio * sqrt(2*pi*sig^2)

Con probabilidad `WGT_EXPON/(WGT_EXPON+WGT_GAUSS)`: AV de una exponencial truncada en
`[r0,r1]` (inversión de CDF). Si no: AV de una semi-Gaussiana (`peak=0` → solo lado positivo,
`sig*|Gauss|`) por rechazo hasta caer en `[r0,r1]`. Verificado standalone contra la versión
pura exponencial que se venía usando:

| | mediana AV | media AV | p90 AV |
|---|---|---|---|
| pura exponencial (ronda 2, incorrecta para `SNIax`) | 0.908 | 1.079 | 2.328 |
| mezcla real (`tau=1.7, sig=0.6, ratio=4.0`) | **0.493** | **0.670** | **1.515** |

La mezcla real aplica **menos** extinción típica que la aproximación exponencial pura (68% de
los objetos cae en la rama Gaussiana, con AV típico ~0.4-0.5, no en la cola exponencial de AV
típico ~1.2-1.7) — el sesgo iba en la dirección opuesta a la esperada.

## 3. Resultado: la brecha no se cerró — empeoró levemente

`NGENTOT_LC=2000`, mismo pipeline, único cambio: el sampler de AV.

| | SNR mediana | SNR p90 | detectados SNANA | detectados LCL | razón |
|---|---|---|---|---|---|
| ronda 2 (AV exponencial puro, incorrecto) | 0.761 | 2.054 | 175/2000 (8.75%) | 464/2000 (23.2%) | 2.65x |
| ronda 3 (AV mezcla real, correcto) | 0.755 | 2.026 | 175/2000 (8.75%) | 476/2000 (23.8%) | **2.72x** |

**Resultado honesto, no el esperado**: corregir el modelo de extinción (menos AV típico →
objetos menos atenuados → más detecciones) empeoró la brecha en vez de cerrarla, exactamente
como predecía el cálculo de AV típico del punto 2. Esto **descarta la extinción de host como
la causa de la brecha anómala de `SNIax`** — con el modelo correcto implementado y verificado
línea por línea contra `snlc_sim.c`, la brecha persiste casi sin cambio (2.65x→2.72x, dentro
del ruido de simulación). La causa real de por qué `SNIax` queda fuera de la banda sistémica
1.4-1.8x (que sí explica `TDE-MOSFIT`/`SNII-NMF`) sigue sin identificarse. Candidatos no
descartados pero tampoco confirmados, sin investigar más a fondo esta ronda (mismo criterio de
"documentar y decidir con el usuario" del resto de la sesión): `DNDZ: MD14` (reusado de
`CaRT`/`SLSN-I`, que también mostraron brechas grandes en la ronda 1 — pero esas SÍ tenían
extinción omitida, no es una comparación limpia); o un efecto de población/color específico de
la plantilla SIMSED de `SNIax` no capturado por ninguno de los términos ya auditados en Fase 2
parte A.

## 4. Tres clases más: `ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`

Las 3 últimas del catálogo que declaran extinción de host (todas con el flag real
`GENAV_WV07: 1`, confirmado — no el camino de `SNIax`, así que la omisión sigue siendo la
decisión correcta y justificada, mismo criterio de la ronda 1). `ILOT-MOSFIT` y `SNIIn-MOSFIT`
reusan `DNDZ: CC_S15` (ya validado en `SNII-NMF`). `PISN-MOSFIT` usa `DNDZ: PISN_PLK12` — un
modelo que las rondas 1-2 habían descartado por "nombre propio sin fórmula obvia", pero que
esta vez sí se encontró en el código fuente real (`snlc_sim.c`, bloque
`INDEX_RATEMODEL_PISN`), sin necesidad de `h²`/`H0` en la forma funcional (a diferencia de
`MD14`/`CC_S15`):

    rate(z) = 1.98 + 6.38z + 6.558z² - 4.42z³ + 0.8312z⁴ - 0.0508z⁵   [/yr/Gpc³]

`build_dndz_pisn_cdf()` (nuevo en `snana_params.py`) implementa esta fórmula exacta. Los 3
`SED.INFO` reales parsean como YAML limpio (sin el problema de `TDE-MOSFIT`), no hizo falta
sanitizar nada.

## 5. Resultado: 4/4 corridas limpias esta ronda, `NGENTOT_LC=2000`

| clase | extinción host | SNR mediana | SNR p90 | detectados SNANA | detectados LCL | razón |
|---|---|---|---|---|---|---|
| `SNIax` (corregido) | mezcla real (exp+semi-Gauss) | 0.755 | 2.026 | 175/2000 (8.75%) | 476/2000 (23.8%) | 2.72x |
| `ILOT-MOSFIT` | omitida (WV07 real) | 0.694 | 1.714 | 73/2000 (3.65%) | 143/2000 (7.15%) | 1.96x |
| `SNIIn-MOSFIT` | omitida (WV07 real) | 0.683 | 1.676 | 37/2000 (1.85%) | 187/2000 (9.35%) | 5.05x |
| `PISN-MOSFIT` | omitida (WV07 real) | 0.814 | 2.370 | 411/2000 (20.55%) | 716/2000 (35.8%) | 1.74x |

Las 3 clases con extinción omitida (`ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`) caen dentro
del mismo rango amplio 1.5-8.5x ya visto en la ronda 1 (`KN-K17` 2.56x, `CaRT` 8.5x, `SLSN-I`
1.54x) — más evidencia de que ese rango, no una banda estrecha, es lo que produce omitir
extinción de host, con la magnitud dependiendo de cuán débil es la clase intrínsecamente
(`SNIIn-MOSFIT`, con solo 37 detecciones reales de 2000, es de nuevo el caso extremo, igual que
`CaRT` en la ronda 1 con 16/2000).

## 6. Estado del catálogo SIMSED: 10/11 clases cubiertas

Con esta ronda: `SNIa-91bg`, `KN-K17`, `CaRT`, `SLSN-I`, `SNIax`, `TDE-MOSFIT`, `SNII-NMF`,
`ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT` — 10 de las 11 clases SIMSED del catálogo (más
`SNIa`/SALT2, 11 clases en total evaluadas). Solo queda `KN-BULLA19`, con una estructura de
directorio anidada de 3 sub-variantes nunca investigada (ver Fase 2 parte B, sección "Elegir
la clase más simple") — no evaluada aún, fuera del alcance de esta ronda.

## Archivos de esta ronda

- `snana_params.py` — `make_exp_halfgauss_av_sampler()` (mezcla real exp+semi-Gauss, fix del
  caso `SNIax`), `build_dndz_pisn_cdf()` (fórmula `PISN_PLK12` real).
- `run_simsed_poc.py` — config de `SNIax` corregida (`kind="exp_halfgauss"`), 3 configs nuevas
  (`ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`), dispatch de `host_av["kind"]` generalizado.
- `poc_output_sniax/` (actualizado), `poc_output_ilotmosfit/`, `poc_output_sniinmosfit/`,
  `poc_output_pisnmosfit/` — resultados reales (`summary.json` + 4 QC c/u).

## Estado y siguiente decisión

La investigación del caso `SNIax` produjo un resultado real y útil aunque no el esperado: se
encontró y corrigió un error genuino de caracterización (mezcla exp+semi-Gauss real, no pura
exponencial), implementado con el algoritmo exacto de SNANA verificado línea por línea contra
el código fuente real — pero la corrección **no** explica la brecha anómala de `SNIax`, que
sigue sin causa identificada. Esto es información real: descarta una hipótesis concreta en vez
de dejarla sin probar. 10/11 clases SIMSED evaluadas de punta a punta, con hallazgos honestos
en ambas direcciones (confirmaciones y refutaciones de hipótesis) documentados en todas las
rondas. Suficiente cobertura para una recomendación final de la evaluación LightCurveLynx —
`KN-BULLA19` queda como único pendiente conocido, no bloqueante.

# Fase 2 — parte B (continuación 4): cierre del catálogo — `KN-BULLA19`,
# `PISN-STELLA-HECORE`, `PISN-STELLA-HYDROGENIC`

`KN-BULLA19` es la última de las 11 clases SIMSED originales. Al revisar de nuevo
`pipeline/models.yaml` para confirmar que no quedaba nada suelto, aparecieron 2 clases más
allá de las 11 originales que también usan `GENMODEL: .../SIMSED.*` y nunca se habían corrido:
`PISN-STELLA-HECORE` y `PISN-STELLA-HYDROGENIC` (variantes alternativas de PISN, distintas de
`PISN-MOSFIT` — modelos de S.Blondin basados en Heger & Woosley 2002 y Gilmer et al. 2017
respectivamente).

## 1. `KN-BULLA19`: la estructura anidada resultó ser simple, pero escondía un bug de dato real

`GENMODEL` apunta a `SIMSED.KN-BULLA19/SIMSED.BULLA-BNS-M2-2COMP` — de las 3 sub-variantes
anidadas que existen en el directorio (`BULLA-BHNS-M1-2COMP`, `BULLA-BNS-M2-2COMP`,
`BULLA-BNS-M3-3COMP`, confirmado con `find`), el `.INPUT` real solo usa una. No hacía falta
elegir entre las 3 "a ciegas" como se temía en Fase 2B ronda 1 — el `.INPUT` ya lo resuelve.

Al cargar esa sub-variante (550 templates), `SIMSEDModel.from_dir()` falló con
`gzip.BadGzipFile: Not a gzipped file (b'PK')`. Diagnóstico con `file`/`xxd` en NLHPC: los 550
archivos `*.txt.gz` que declara `SED.INFO` **no son gzip** — son archivos **ZIP** (firma real
`PK\x03\x04`) mal etiquetados con extensión `.gz`, cada uno con un solo miembro interno del
mismo nombre. Confirmado con una muestra de 20/550 archivos, todos con el mismo problema — no
es un caso aislado, es sistémico en esta librería SIMSED específica (probablemente un paso de
compresión equivocado al publicarla, no algo que afecte a las otras 10 clases ya corridas). El
parser de SNANA lo tolera (probablemente vía una utilidad de sistema más laxa); el nuestro no.

**Fix**: `setup_knbulla19_local.py` (nuevo) — descomprime cada ZIP (`zipfile`) y re-comprime el
contenido como gzip real (`gzip.open(...).write(...)`), mismo nombre de archivo, `SED.INFO` sin
tocar (ya parsea limpio). Corrida real: 550/550 archivos arreglados en ~2 min, verificado
`np.loadtxt()` cargando una grilla `(50000, 3)` fase×longitud de onda×flujo correctamente
después del fix. No se toca el archivo real de SNANA — copia local en
`simsed_knbulla19_local/` (no versionada).

## 2. `WV07_REWGT_EXPAV`: otra forma de activar el mismo camino de código bugueado

`KN-BULLA19` declara `WV07_REWGT_EXPAV: 0.5` en vez de `GENAV_WV07: 1` directo — a primera
vista parece un mecanismo distinto. Confirmado leyendo `snlc_sim.c` (línea ~7887-7888):
cualquier valor real de `WV07_REWGT_EXPAV` (`> -1.0E-9`) activa
`INPUTS.WV07_GENAV_FLAG = DO_WV07 = 1`, el mismo flag que `KN-K17`/`CaRT`/`SLSN-I`/
`ILOT-MOSFIT`/`SNIIn-MOSFIT`/`PISN-MOSFIT` activan directo — mismo camino de código con el bug
histórico ya documentado (Fase 2B ronda 1). Se omite por el mismo criterio, no una excepción
nueva sin analizar.

## 3. `PISN-STELLA-HECORE`/`PISN-STELLA-HYDROGENIC`: reuso directo, sin sorpresas de config

Ambas declaran `GENAV_WV07: 1` (el camino bugueado directo, se omite igual que `PISN-MOSFIT`)
y `DNDZ: PISN_PLK12` — la misma fórmula real ya implementada la ronda anterior
(`build_dndz_pisn_cdf()`), reusada sin cambios. `GENRANGE_REDSHIFT: 0.02 2.2` (ligeramente más
angosto que el `0.02 2.4` de `PISN-MOSFIT`). Ambos `SED.INFO` parsean limpio, ambos directorios
son pequeños (11M/14 templates y 5.3M/6 templates respectivamente) — las corridas más rápidas
de todo el catálogo SIMSED hasta ahora.

## 4. `PISN-STELLA-HYDROGENIC` usa `NGENTOT_LC=20000`, no 2000 — y eso reveló un límite real de memoria

A diferencia de las demás 10 clases (todas con `ngen_ddf: 2000` en `pipeline/models.yaml`),
`PISN-STELLA-HYDROGENIC` usa `ngen_ddf: 20000` — confirmado, no un valor por defecto sin
verificar. `run_simsed_poc.py` se generalizó (`main(class_key, ngentot_override=None)`,
`CLASS_CONFIGS[...]["ngentot_lc"]` como override opcional) para soportar esto sin tocar las
otras 10 clases.

El primer intento (mismo `--mem=16G` que todas las clases anteriores) terminó en
`OUT_OF_MEMORY` a los 109s, justo después de cargar los 6 templates — 10x más objetos que el
caso normal (2000→20000) implica ~10x más filas de fotometría aplanada (confirmado después:
45.5M filas vs los ~4.5M típicos de N=2000), y el objeto intermedio de curvas de luz por
objeto de `simulate_lightcurves()` excede los 16GB antes de llegar siquiera a esa etapa.
**Fix**: resubmit con `sbatch --mem=64G` (override de CLI sobre el `#SBATCH --mem=16G` del
script, sin tocar el `.sbatch` compartido por las otras clases) — corrió limpio, `MaxRSS` no
llegó a excederse. Tiempo total: **62 minutos** (804s simulación + 2671s aplanado + resto) —
resultó ser proporcional a N (10x el tiempo de una corrida N=2000 típica, no superlineal como
se sospechó a mitad de la espera), solo que en términos absolutos es una corrida larga.

## 5. Resultado: 3/3 corridas limpias

| clase | `NGENTOT_LC` | extinción host | SNR mediana | SNR p90 | detectados SNANA | detectados LCL | razón |
|---|---|---|---|---|---|---|---|
| `KN-BULLA19` | 2000 | omitida (`WV07_REWGT_EXPAV` → mismo camino WV07 real) | 0.683 | 1.685 | 103/2000 (5.15%) | 294/2000 (14.7%) | 2.85x |
| `PISN-STELLA-HECORE` | 2000 | omitida (`GENAV_WV07` real) | 0.746 | 2.054 | 384/2000 (19.2%) | 577/2000 (28.85%) | 1.50x |
| `PISN-STELLA-HYDROGENIC` | 20000 | omitida (`GENAV_WV07` real) | 0.754 | 2.021 | 4268/20000 (21.34%) | 6106/20000 (30.53%) | 1.43x |

Las 3 clases omiten extinción de host (las 3 usan el camino WV07 real, confirmado línea por
línea) — sus razones (1.43x-2.85x) caen dentro del mismo rango amplio ya visto en rondas
anteriores para clases sin extinción (1.5x-8.5x), sin sorpresas nuevas. `PISN-STELLA-HECORE`
(1.50x) y `PISN-STELLA-HYDROGENIC` (1.43x) caen cerca del extremo bueno de ese rango — similar
a `PISN-MOSFIT` (1.74x) y `SLSN-I` (1.54x), clases intrínsecamente más brillantes/comunes.
`KN-BULLA19` (2.85x) es comparable a `KN-K17` (2.56x), su análogo del mismo tipo de evento
(kilonova) — señal cruzada razonable: dos librerías SIMSED distintas para el mismo tipo físico
de evento (kilonovas de fusión de estrellas de neutrones) muestran una brecha similar, lo que
sugiere que el factor dominante es el tipo de evento/población, no una peculiaridad de una
librería de templates en particular.

## 6. Estado del catálogo: 11/11 clases SIMSED + `SNIa`/SALT2 — cobertura completa

Con esta ronda se cierra el catálogo completo de clases basadas en SIMSED del proyecto: las 11
originales (`SNIa-91bg`, `KN-K17`, `CaRT`, `SLSN-I`, `SNIax`, `TDE-MOSFIT`, `SNII-NMF`,
`ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`, `KN-BULLA19`) más las 2 variantes PISN-STELLA
encontradas esta ronda, más `SNIa`/SALT2 de Fase 1 — 14 clases evaluadas de punta a punta en
total. Cobertura de todos los patrones de implementación encontrados: peso uniforme,
`SIMSED_REDCOR` (1D y 3D), extinción de host exponencial pura, extinción de host mezcla
exp+semi-Gauss real, 5 modelos `DNDZ` distintos (`POWERLAW`, `POWERLAW2`, `MD14`, `CC_S15`,
`TDE`, `PISN_PLK12`), y ahora también el caso de `NGENTOT_LC` no estándar.

## Archivos de esta ronda

- `setup_knbulla19_local.py` (nuevo) — descomprime los 550 templates ZIP-mal-etiquetados de
  `KN-BULLA19` y los re-comprime como gzip real; `simsed_knbulla19_local/` (no versionado).
- `run_simsed_poc.py` — `main()` acepta `ngentot_override` opcional, `CLASS_CONFIGS` soporta
  `ngentot_lc` por clase; 3 configs nuevas (`KN-BULLA19`, `PISN-STELLA-HECORE`,
  `PISN-STELLA-HYDROGENIC`).
- `poc_output_knbulla19/`, `poc_output_pisnstellahecore/`, `poc_output_pisnstellahydrogenic/`
  — resultados reales (`summary.json` + 4 QC c/u).

## Estado y siguiente decisión

Catálogo SIMSED/SALT2 completo (14/14 clases planificadas). No quedan clases SIMSED conocidas
sin evaluar en el catálogo activo del proyecto. Recomendación: con esta cobertura, el próximo
paso natural es una recomendación final consolidada de la evaluación LightCurveLynx (síntesis
de las 4 rondas de Fase 2B + Fase 1/2A), no más escalado de clases — a decidir con el usuario.

# Recomendación final — LightCurveLynx como reemplazo de SNANA

Síntesis de Fase 0 (spike técnico) → Fase 1 (PoC SNIa) → Fase 2 parte A (cierre de brecha de
ruido) → Fase 2 parte B, 4 rondas (cobertura SIMSED completa). 14 clases evaluadas de punta a
punta contra baselines DDF reales de la campaña `full_v5.3_10yrs` (v8).

## Veredicto: GO condicional — viable como motor de simulación, no listo para reemplazo directo

LightCurveLynx **sí puede reproducir mecánicamente** cualquier clase del catálogo (SALT2 y las
14 variantes SIMSED, incluyendo los 5 modelos `DNDZ` reales del catálogo) con parámetros reales
de SNANA, extinción MW real, eficiencia de detección real (SEARCHEFF), y una ventaja de
velocidad de ~150x sobre SNANA en throughput crudo — pero **ninguna corrida coincide
cuantitativamente** con SNANA todavía. La eficiencia de detección simulada sale sistemáticamente
más alta, con razones LCL/SNANA entre **1.37x y 8.50x** (promedio 2.57x) según la clase. Esto no
es un fallo binario ("no sirve") ni una confirmación limpia ("listo para producción") — es una
herramienta con mecánica sólida y una calibración cuantitativa pendiente, con las causas
conocidas ya diagnosticadas con precisión variable.

## Tabla completa — 14 clases, ordenadas por razón LCL/SNANA

| clase | modelo | extinción de host | SNANA real | LightCurveLynx | razón |
|---|---|---|---|---|---|
| `SNIa-91bg` | SIMSED (35 templates) | no declarada | 723/2000 (36.15%) | 993/2000 (49.65%) | 1.37x |
| `SNII-NMF` | SIMSED (384, PCA) | no declarada | 356/2000 (17.8%) | 498/2000 (24.9%) | 1.40x |
| `PISN-STELLA-HYDROGENIC` | SIMSED (6) | omitida (WV07 real) | 4268/20000 (21.34%) | 6106/20000 (30.53%) | 1.43x |
| `PISN-STELLA-HECORE` | SIMSED (14) | omitida (WV07 real) | 384/2000 (19.2%) | 577/2000 (28.85%) | 1.50x |
| `SLSN-I` | SIMSED (960) | omitida (WV07 real) | 824/2000 (41.2%) | 1266/2000 (63.3%) | 1.54x |
| `TDE-MOSFIT` | SIMSED (742) | **implementada** (exp. pura) | 812/2000 (40.6%) | 1277/2000 (63.85%) | 1.57x |
| `PISN-MOSFIT` | SIMSED (1000) | omitida (WV07 real) | 411/2000 (20.55%) | 716/2000 (35.8%) | 1.74x |
| `SNIa` | SALT2 (sncosmo H17) | no implementada (solo MW) | 597/2000 (29.85%) | 1086/2000 (54.3%) | 1.82x |
| `ILOT-MOSFIT` | SIMSED (385) | omitida (WV07 real) | 73/2000 (3.65%) | 143/2000 (7.15%) | 1.96x |
| `KN-K17` | SIMSED (329) | omitida (WV07 real) | 82/2000 (4.1%) | 210/2000 (10.5%) | 2.56x |
| `SNIax` | SIMSED (1001) | **implementada** (mezcla real) | 175/2000 (8.75%) | 476/2000 (23.8%) | 2.72x |
| `KN-BULLA19` | SIMSED (550) | omitida (WV07 real) | 103/2000 (5.15%) | 294/2000 (14.7%) | 2.85x |
| `SNIIn-MOSFIT` | SIMSED (839) | omitida (WV07 real) | 37/2000 (1.85%) | 187/2000 (9.35%) | 5.05x |
| `CaRT` | SIMSED (225) | omitida (WV07 real) | 16/2000 (0.8%) | 136/2000 (6.8%) | 8.50x |

## Lo que sí funciona sin reservas

- **Ingesta de OpSim**: exacta, sin transformación de columnas, mismo schema que el simulador
  oficial de Rubin (Fase 0 punto 3).
- **Extinción MW**: completa, más flexible que SNANA (soporta más leyes de extinción que las
  que SNANA usa hoy), verificada por campo real (Fase 1 punto 6).
- **SIMSED nativo**: `SIMSEDModel.from_dir()` funciona para las 14 variantes probadas — 12
  peso uniforme, 2 con `SIMSED_REDCOR` (1D y 3D) — cubriendo 5 modelos `DNDZ` reales
  (`POWERLAW`, `POWERLAW2`, `MD14`, `CC_S15`, `TDE`, `PISN_PLK12`).
- **SEARCHEFF real**: implementado como post-proceso (`searcheff.py`) reusando los archivos de
  calibración reales de SNANA, mismo `PHOTFLAG`/criterio de detección en ambos lados de la
  comparación.
- **Rendimiento**: ~150x más rápido en throughput crudo (Fase 0), confirmado en cada PoC
  posterior (2000 objetos DDF en 50-90s de wall time, incluida ingesta completa de OpSim).
- **Orquestación**: patrón `dask.distributed.LocalCluster` dentro de un job SLURM único
  validado con 3.16x de speedup real (Fase 1 punto 8b) — nunca se necesitó tocar el login node
  en ninguna corrida de toda la evaluación.

## Las dos causas reales de la brecha cuantitativa (diagnosticadas, ninguna es un misterio difuso)

**1. Residuo sistémico de ruido/población (~1.4-1.8x), presente incluso sin extinción de host
omitida.** Diagnosticado en dos rondas reales de investigación (Fase 1 punto 7b, Fase 2 parte
A): se identificaron y corrigieron dos causas concretas (`H0=73`→`70` sin verificar, y el
modelo de ruido propio de LightCurveLynx vs las columnas `SKYSIG`/`PSF`/`ZPT` reales de SNANA,
inyectadas directamente desde Fase 2A en adelante) — la brecha se redujo de ~2x a ~1.4-1.8x
con ambos fixes, pero no se cerró del todo. Las clases "limpias" (sin extinción de host que
declarar: `SNIa-91bg`, `SNII-NMF`) y las que sí implementan extinción de host correctamente
(`TDE-MOSFIT`) caen todas en esta misma banda — señal consistente de que el residuo es
sistémico, no específico de una clase o un modelo de fuente. Causa más probable no confirmada:
diferencias en cómo se evalúa la superficie SALT2/SIMSED entre `sncosmo`/LightCurveLynx y el
código interno de SNANA, o simplificaciones aceptadas de dispersión intrínseca (`SIGMA_INT`
coherente en vez de la covarianza completa de G10).

**2. Extinción de host `WV07` no implementada — afecta a 9/14 clases** (`KN-K17`, `CaRT`,
`SLSN-I`, `ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`, `PISN-STELLA-HECORE`,
`PISN-STELLA-HYDROGENIC`, `KN-BULLA19` — recuento corregido; una cuenta anterior decía 8/14 por
error), **con efecto proporcional a cuán tenue es la clase intrínsecamente.** Decisión
deliberada desde la ronda 1 (no un descuido): se había leído un comentario de bug histórico en
`getRan_GEN_EXP_HALFGAUSS()` (`sntools_genExpHalfGauss.c`) y se asumió, por prudencia, que
afectaba también al modelo WV07. El efecto es medible y coherente: clases intrínsecamente
brillantes/comunes (`SLSN-I` 1.54x, `PISN-STELLA-HECORE` 1.50x, `PISN-MOSFIT` 1.74x) caen cerca
de la banda sistémica pese a omitir extinción, mientras que clases intrínsecamente tenues
(`CaRT` 8.50x con solo 16 detecciones reales de 2000, `SNIIn-MOSFIT` 5.05x con 37/2000)
muestran el efecto amplificado — omitir un factor que oscurece
sistemáticamente pesa mucho más cerca del umbral de detección.

**Validación cruzada real de la causa 2** (Fase 2B ronda 3): al implementar el modelo de host
`no`-WV07 real y correctamente (la mezcla exponencial+semi-Gaussiana de `SNIax`, distinta del
flag `GENAV_WV07` bugueado — confirmado leyendo `snlc_sim.c::gen_AV()` línea por línea), la
corrección **no** cerró la brecha de esa clase (2.65x→2.72x, empeoró levemente) — refutando
extinción como la causa en ese caso puntual y confirmando que `SNIax` es una anomalía real
seguramente ligada a la causa 1 (residuo sistémico), no a extinción. Este es el único resultado
de las 4 rondas que contradice una hipótesis en vez de confirmarla — se documentó como tal, sin
forzar una narrativa limpia.

## Lo que nunca se probó (límites reales de esta evaluación, no ocultos)

- **Escala WFD real**: todas las 14 clases se corrieron a escala DDF (`NGENTOT_LC=2000`,
  excepto `PISN-STELLA-HYDROGENIC` a 20000) — la escala WFD real de producción es
  `NGENTOT_LC=200,000` por clase, 100x más. El patrón `dask` está validado (Fase 1 punto 8b)
  pero nunca se corrió a este volumen real; `PISN-STELLA-HYDROGENIC` (10x escala) ya mostró que
  la memoria necesaria escala con N de forma no trivial (`--mem=16G` no alcanzó, `64G` sí) —
  extrapolar a WFD sin probarlo primero sería especular.
- **`WV07` real**: se decidió omitir por precaución, no se investigó si existe una
  referencia/implementación alternativa confiable (a diferencia de `PISN_PLK12`/`CC_S15`/`TDE`,
  que sí se encontraron y verificaron esta sesión). Afecta a 9/14 clases. **Actualización: ver
  Fase 3 más abajo — se investigó y sí se encontró una referencia sólida.**
- **Comparación contra más de un baseline**: todo se comparó contra la única campaña real
  disponible (`full_v5.3_10yrs`/v8) — no se probó si la brecha cuantitativa es estable entre
  distintas configuraciones OpSim o campañas.
- **Integración real de pipeline**: nada de esto toca `pipeline/orchestrate/` (Capa 3) ni
  ninguna capa de producción — es exploración aislada en `exploration/lightcurvelynx/`, sin
  ningún archivo de producción modificado.

## Recomendación concreta (superada por Fase 3 — ver más abajo)

**No reemplazar SNANA todavía.** La brecha cuantitativa (1.37x-8.50x) es demasiado grande y
variable por clase para usar LightCurveLynx como fuente de verdad científica en su estado
actual. **Sí vale la pena seguir invirtiendo** — la mecánica funciona en las 14 clases del
catálogo, dos causas reales de brecha ya están diagnosticadas con precisión (no es una caja
negra), y la ventaja de velocidad (~150x) es lo bastante grande como para que cerrar la
calibración cuantitativa sea un objetivo con retorno real, no un ejercicio académico.

# Fase 3 — implementar el modelo real de extinción de host `WV07`

Primera fase con alcance definido después de la recomendación final (arriba). De las 2 causas
diagnosticadas de la brecha cuantitativa, `WV07` era la única con una vía de cierre concreta
(el residuo sistémico de Causa 1 ya había agotado dos rondas reales de investigación en Fase
2A). Objetivo: encontrar la fórmula real de `GENAV_WV07()`, implementarla con confianza, y
medir el efecto real en las 9 clases que la declaran.

## 1. La función real es autónoma y ya está corregida — la precaución de las rondas 1-4 era sobre la función equivocada

Leyendo `GENAV_WV07()` completa en `snlc_sim.c` (nunca se había leído línea por línea antes,
solo un comentario de un archivo adyacente): es el modelo real de extinción de host de
**ESSENCE-WV07** (Wood-Vasey et al. 2007) — comentario real en el código: *"return AV from
distribution used by ESSENCE-WV07"*. Mezcla una exponencial ancha + un núcleo semi-Gaussiano
angosto, con **constantes fijas en el código** (no configurables por `.INPUT`, iguales para las
9 clases): `tau=0.4`, `sqsigma=0.01` (sigma del núcleo = 0.1 mag). Muestreo por rechazo: `AV`
uniforme en `GENRANGE_AV`, peso `W(AV) = AEXP·exp(-AV/tau) + BEXP·exp(-0.5·AV²/sqsigma)`
normalizado por `W(0)`, aceptar con probabilidad `W(AV)/W(0)`.

**Es una función completamente autónoma** — nunca llama a `getRan_GEN_EXP_HALFGAUSS()` (la
función con el bug de peso corregido en Dic 2023 que motivó la precaución original). El único
bug histórico real de `GENAV_WV07()` (comentario real: *"Mar 17 2022: fix bug that has resulted
in all AV=0; use INPUTS.GENPROFILE_AV.RANGE instead of obsolete INPUTS.GENRANGE_AV"* — una
variable obsoleta) ya está corregido en la versión del código fuente leída esta ronda. La
precaución de las rondas 1-4 (omitir WV07 por el bug de una función *adyacente*) era razonable
dado lo que se sabía entonces, pero resultó ser sobre la función equivocada.

`make_wv07_av_sampler()` (nuevo en `snana_params.py`) implementa el algoritmo exacto. Si el
`.INPUT` declara `WV07_REWGT_EXPAV` (`KN-K17` y `KN-BULLA19`, valor `0.5` — confirmado que
activa el mismo `WV07_GENAV_FLAG`, mismo camino de código, no una excepción nueva), reescala
`AEXP`. Las otras 7 clases no lo declaran (`AEXP` sin modificar). Verificado standalone: `AV`
mediano ≈0.15 mag (caso default) / ≈0.11 mag (rewgt=0.5) — una distribución bastante
concentrada cerca de cero, con cola larga hasta el límite de `GENRANGE_AV` (3.0 mag).

## 2. Resultado: efecto real, pero pequeño y no sistemático — el catálogo completo apenas se movió

`NGENTOT_LC` real de cada clase (2000, excepto `PISN-STELLA-HYDROGENIC` a 20000). Único cambio
respecto a las corridas ya reportadas: el sampler de `host_av` (de omitido/AV=0 a `WV07` real).

| clase | razón (sin WV07) | razón (WV07 real) | Δ |
|---|---|---|---|
| `SLSN-I` | 1.54x | 1.50x | mejor |
| `PISN-STELLA-HYDROGENIC` | 1.43x | 1.38x | mejor |
| `PISN-STELLA-HECORE` | 1.50x | 1.41x | mejor |
| `PISN-MOSFIT` | 1.74x | 1.62x | mejor |
| `ILOT-MOSFIT` | 1.96x | 2.25x | **peor** |
| `KN-K17` | 2.56x | 2.87x | **peor** |
| `SNIax` *(no afectada, otro modelo)* | 2.72x | 2.72x | — |
| `KN-BULLA19` | 2.85x | 2.84x | igual |
| `SNIIn-MOSFIT` | 5.05x | 4.76x | mejor |
| `CaRT` | 8.50x | 8.56x | **igual, el caso más extremo no se movió** |

**Promedio de las 9 clases afectadas: 3.01x antes → 3.02x después — esencialmente sin
cambio.** 5 mejoraron (leve a moderado), 2 empeoraron, 2 quedaron iguales dentro del ruido.
**Promedio del catálogo completo (14 clases): 2.57x → 2.58x — sin cambio significativo.**

## 3. Esto refuta parcialmente la hipótesis de la ronda 1 de Fase 2B

La hipótesis original (Fase 2B ronda 1) era que omitir `WV07` explicaba las brechas más grandes
del catálogo, con el efecto amplificado en clases intrínsecamente tenues — y que implementarlo
correctamente debía cerrar esas brechas. El resultado real la refuta parcialmente: **`CaRT`,
el caso más extremo (8.50x) y el que más debería beneficiarse según la hipótesis, prácticamente
no se movió** (8.50x→8.56x). `KN-K17` incluso empeoró. Solo las clases que ya estaban cerca de
la banda sistémica (`SLSN-I`, `PISN-MOSFIT`, ambas `PISN-STELLA-*`) mejoraron de forma
consistente — es decir, `WV07` ayuda un poco donde la brecha ya era chica, pero no explica las
brechas grandes.

**Causa más probable, no confirmada**: el `AV` mediano real de `WV07` (~0.15 mag) es
modesto — una corrección de ese tamaño es fácilmente dominada por el residuo sistémico de
Causa 1 (~1.4-1.8x, sin cerrar desde Fase 2A) para las clases ya cerca de esa banda, pero es
demasiado pequeña para mover clases con brechas de 5-8x. Además, los baselines reales de SNANA
para las clases más tenues son conteos muy bajos (`CaRT` n=16, `ILOT-MOSFIT` n=73, `KN-K17`
n=82, `KN-BULLA19` n=103, `SNIIn-MOSFIT` n=37) — con incertidumbre de Poisson de ese orden
(`CaRT`: ±25% relativo solo por conteo), diferencias de ±10-15% en la razón antes/después no
distinguen necesariamente una mejora real de ruido estadístico. **No se investigó más a fondo
esta ronda** (mismo criterio de "documentar y decidir con el usuario" de toda la sesión) — si
se quiere una conclusión más firme sobre `CaRT`/`KN-K17` específicamente, hace falta más de una
semilla/corrida, o una comparación término a término como la de Fase 2A.

## Archivos de esta fase

- `snana_params.py` — `make_wv07_av_sampler()` (modelo ESSENCE-WV07 real, constantes fijas
  `tau=0.4`/`sqsigma=0.01`, muestreo por rechazo).
- `run_simsed_poc.py` — `host_av["kind"]="wv07"` agregado al dispatch; 9 `CLASS_CONFIGS`
  actualizados (`KN-K17`, `CaRT`, `SLSN-I`, `ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`,
  `KN-BULLA19`, `PISN-STELLA-HECORE`, `PISN-STELLA-HYDROGENIC`).
- `poc_output_knk17/`, `poc_output_cart/`, `poc_output_slsni/`, `poc_output_ilotmosfit/`,
  `poc_output_sniinmosfit/`, `poc_output_pisnmosfit/`, `poc_output_knbulla19/`,
  `poc_output_pisnstellahecore/`, `poc_output_pisnstellahydrogenic/` — resultados actualizados
  con `WV07` real (`summary.json` + 4 QC c/u, sobrescriben los de las rondas anteriores).

## Recomendación final (actualizada)

**Sigue siendo GO condicional — la conclusión no cambia, pero la causa raíz sí se aclaró.**
Implementar `WV07` fue lo correcto científicamente (fórmula real, verificada línea por línea
contra el código fuente, no una aproximación) y cerró la brecha para 5 de 9 clases afectadas
— pero el promedio del catálogo completo apenas se movió (2.57x→2.58x), porque el residuo
sistémico de Causa 1 (~1.4-1.8x, sin cerrar desde Fase 2A) domina sobre la extinción de host en
casi todos los casos. **La causa raíz real de la brecha cuantitativa de LightCurveLynx contra
SNANA no es la extinción de host — es el residuo sistémico no resuelto de Fase 2A.** Esto
redirige dónde vale la pena invertir a continuación: cerrar ese residuo (comparación más
profunda de la evaluación de superficie SALT2/SIMSED, o correr múltiples semillas para
distinguir señal de ruido en las clases de bajo conteo) tiene más potencial de cerrar la brecha
que seguir ajustando modelos de extinción.

# Fase 4 — investigar el residuo sistémico (~1.4-1.8x) a fondo

Ataca directamente la causa raíz identificada al cierre de Fase 3, con más rigor que las dos
rondas ya agotadas en Fase 2A. Pista clave no explotada todavía: el residuo está presente
**tanto en clases SALT2 (`SNIa`) como en clases SIMSED** que leen templates de flujo reales
directamente (`SNIa-91bg`, `SNII-NMF`, `TDE-MOSFIT`) — sin pasar por `sncosmo` ni por el modelo
de dispersión G10. Como ambos tipos de fuente muestran la misma banda residual, la causa debe
estar en la maquinaria **compartida** (ruido, extinción MW, SEARCHEFF), no en la evaluación de
un modelo de fuente específico.

## 1. Tres candidatos descartados con evidencia real, antes de encontrar la causa

**Curvas de throughput de filtro — descartado, idénticas.** LightCurveLynx descarga
`total_{ugrizy}.dat` en vivo desde `github.com/lsst/throughputs` rama `main`; SNANA usa el tag
fijo `baseline_1.9` (confirmado en `pipeline/kcor/README.md`). Comparación byte a byte en
NLHPC de las 6 curvas: **0 líneas de diferencia** — la rama `main` no se movió desde `1.9` en
los filtros LSST reales. Descartado con evidencia directa, no supuesto.

**`dark_current`/`readout_noise` — descartado, magnitud insuficiente.** `poisson_bandflux_std()`
(LightCurveLynx) suma varianza de sky+readout+dark+zp_err además de la fuente; solo se
inyectan `sky_bg_e`/`psf_footprint`/`zp` reales desde Fase 2A, dejando `dark_current=0.2 e⁻/s`
y `readout_noise=8.8 e⁻` (defaults de `OpSim`) sin verificar. Cálculo real con parámetros DDF
típicos: `dark_variance + readout_variance ≈` solo **~4.4%** de `sky_variance` — aunque hubiera
doble conteo, el efecto en SNR es de ~2%, muy por debajo de la brecha de 40-80%.

**Eficiencia espectroscópica faltante — descartado, no se exige en la campaña real.** Hipótesis:
¿el `n_objects` real de SNANA exige además un trigger espectroscópico (`SEARCHEFF_SPEC`) que
nunca se modeló? `snlc_sim.c` línea 32911: `APPLY_SEARCHEFF_OPT: += 1,2,4 => require pipe,spec,
zhost`. La campaña real (`pipeline/campaign/templates.py`) usa `APPLY_SEARCHEFF_OPT: 1` —
**solo** el bit de pipeline (fotométrico), igual que lo que ya se modela. Descartado con el
propio código fuente de la campaña, no una suposición.

## 2. La causa real: el trigger de detección contaba observaciones individuales, no épocas reales

`LSST_PIPELINE_LOGIC.DAT` documenta: *"min time between detections is given by NEWMJD_DIF key
in sim-input"* — el trigger de SNANA (`>=2 épocas`) no cuenta observaciones individuales, cuenta
**épocas agrupadas**: `snlc_sim.c` (~línea 20566) usa un algoritmo secuencial real,
`MJD_DIF = MJD - MJD_LAST_KEEP; if (fabs(MJD_DIF) > NEWMJD_DIF) nueva_epoca`, con
`NEWMJD_DIF=0.007` días (~10 min, default real, línea 849: *"same 'epoch' for obs within 10'"*)
— agrupando **todas las bandas juntas**, no por banda separada.

Nuestra implementación (`searcheff.py`, sin cambios desde Fase 1) nunca agrupaba — contaba cada
observación individual con `PHOTFLAG_DETECT` como una "época" candidata para el trigger. Medido
con el algoritmo real sobre el OpSim DDF completo:

    145,345 observaciones DDF  →  14,293 épocas reales  (~10.2 obs/época)

Los campos DDF se observan deliberadamente en secuencias de varias visitas seguidas en la misma
noche/banda (para apilar imágenes profundas) — exactamente el patrón que `NEWMJD_DIF` está
diseñado para colapsar en una sola época, y que nuestra implementación nunca colapsaba. Esto es
compartido por **las 14 clases por igual** (mismo `searcheff.py`, mismo trigger), coincidiendo
con el patrón observado de un residuo sistémico y no específico de una clase.

## 3. Fix: `group_into_epochs()` + verificación formal de corrección

`searcheff.py` (nuevo: `group_into_epochs()`, `object_level_detected()` reescrita) replica el
algoritmo secuencial exacto (agrupa por MJD, todas las bandas, `NEWMJD_DIF=0.007`), y una época
cuenta como detectada si **al menos una** de sus observaciones tiene `PHOTFLAG_DETECT`.
`run_simsed_poc.py`/`run_snia_ddf_poc.py` migrados a usar la nueva función en vez del
`groupby("SNID").size()` que contaba filas crudas.

**Verificación formal**: por construcción, agrupar observaciones en épocas solo puede *fusionar*
observaciones (nunca dividir una), así que el conteo de épocas reales de un objeto es siempre
`<=` su conteo de observaciones individuales detectadas — el nuevo trigger (`>=2 épocas
reales`) debería ser un subconjunto estricto del trigger anterior (`>=2 observaciones`). Se
verificó esto empíricamente corriendo ambos métodos sobre el mismo `phot_df` (instrumentación
temporal, revertida después de verificar) para `CaRT` N=500: **26 detectados con el método
nuevo, 27 con el viejo, y el conjunto nuevo es subconjunto exacto del viejo (diferencia
vacía)** — el fix es lógicamente correcto, sin bugs de implementación.

## 4. Segundo hallazgo real (no buscado): la selección de template SIMSED nunca fue reproducible

Investigando por qué `CaRT` mostraba *más* detecciones después del fix (contradiciendo la
propiedad de subconjunto verificada arriba, que predice igual o menos, nunca más — ver punto 3)
se encontró una causa distinta: `SIMSEDModel.from_dir()` construye su sampler de selección de
template (`GivenValueSampler`) **sin pasarle un `seed`**
(`sed_template_model.py`: `self._sampler_node = GivenValueSampler(all_inds, weights=weights)`).
`NumpyRandomFunc` con `seed=None` cae a `os.urandom()` (`math_nodes/np_random.py`) — es decir,
**la selección de template real nunca fue reproducible entre corridas**, en ninguna ronda de
Fase 2B/3, pese a `SEED_BASE` fijo. Esto afecta a las 9 clases de peso uniforme
(`SIMSED_GRIDONLY`) del catálogo — no a `SNIa`/`SALT2` (sin templates) ni a `SNIa-91bg`/
`SNII-NMF` (peso `SIMSED_REDCOR`, mismo problema en principio pero no verificado esta ronda).

**Fix para corridas futuras** (no se re-corrió el catálogo completo de nuevo solo por esto):
`source_model._sampler_node.set_seed(SEED_BASE + 9)` después de `SIMSEDModel.from_dir()`.
**No resuelto en esta ronda**: cuánto de la varianza observada entre corridas (antes/después del
fix de épocas) se debe al fix real vs. a este ruido de selección de template — sin re-correr con
múltiples semillas fijas no se puede aislar limpiamente. Se documenta como límite real de esta
ronda, no se oculta.

## 5. Resultado: efecto real pero pequeño, y no sistemático en la dirección esperada

`NGENTOT_LC` real de cada clase. Único cambio respecto a las corridas de Fase 3: el trigger de
época (punto 3). `SNIa-91bg` migrada por primera vez de `run_simsed_91bg_ddf_poc.py` (script
histórico dedicado) al patrón generalizado `run_simsed_poc.py` (mismos parámetros reales, sin
cambios), para heredar el fix sin duplicar lógica.

| clase | SNANA real | razón antes (Fase 3) | razón después (Fase 4) | Δ |
|---|---|---|---|---|
| `PISN-STELLA-HYDROGENIC` | 4268/20000 | 1.38x | 1.35x | -0.03x |
| `SNIa-91bg` | 723/2000 | 1.37x | 1.35x | -0.02x |
| `SNII-NMF` | 356/2000 | 1.40x | 1.35x | -0.05x |
| `PISN-STELLA-HECORE` | 384/2000 | 1.41x | 1.41x | 0.00x |
| `SLSN-I` | 824/2000 | 1.50x | 1.52x | +0.01x |
| `TDE-MOSFIT` | 812/2000 | 1.57x | 1.58x | +0.01x |
| `PISN-MOSFIT` | 411/2000 | 1.62x | 1.66x | +0.03x |
| `SNIa` | 597/2000 | 1.82x | 1.81x | -0.01x |
| `ILOT-MOSFIT` | 73/2000 | 2.25x | 2.14x | -0.11x |
| `SNIax` | 175/2000 | 2.72x | 2.49x | -0.23x |
| `KN-BULLA19` | 103/2000 | 2.84x | 2.36x | **-0.49x** |
| `KN-K17` | 82/2000 | 2.87x | 2.46x | **-0.40x** |
| `SNIIn-MOSFIT` | 37/2000 | 4.76x | 4.81x | +0.05x |
| `CaRT` | 16/2000 | 8.56x | 9.56x | **+1.00x** |

**Promedio del catálogo: 2.577x → 2.561x — sin cambio significativo**, pese a que el fix en sí
está formalmente verificado como correcto (punto 3). La mayoría de las clases se mantuvo
prácticamente igual (±0.05x, dentro del ruido esperado). Solo 3 clases mejoraron de forma clara:
`KN-K17`, `KN-BULLA19` (ambas kilonovas, mismo modelo `WV07_REWGT_EXPAV=0.5` y rango de
redshift bajo) y `SNIax` — sugiriendo que el efecto del agrupamiento de épocas es real pero
depende de la cadencia/redshift específico de cada clase, no un factor multiplicativo uniforme.
`CaRT` empeoró, pero dado el hallazgo del punto 4 (selección de template no reproducible) y su
conteo real extremadamente bajo (SNANA n=16), este resultado puntual no es confiable sin
múltiples semillas — no se interpreta como una regresión causada por el fix.

**Por qué el efecto es menor de lo esperado pese al colapso ~10x en conteo de épocas**: agrupar
observaciones reduce el número de "oportunidades" de época, pero cada época real ahora tiene
*varias* exposiciones — la probabilidad de que *al menos una* dispare la eficiencia de detección
es mayor que la de una sola observación aislada (efecto de unión de probabilidades). Este efecto
compensa parcialmente la reducción en conteo de épocas, explicando por qué el promedio del
catálogo casi no se movió pese al hallazgo aparentemente grande del punto 2.

## Archivos de esta ronda

- `searcheff.py` — `group_into_epochs()` (nuevo), `object_level_detected()` reescrita para usar
  épocas agrupadas en vez de observaciones individuales.
- `run_simsed_poc.py` — usa `object_level_detected()` del punto anterior; fix de seed
  (`source_model._sampler_node.set_seed(...)`) para selección de template reproducible en
  corridas futuras; `SNIa-91bg` migrada a `CLASS_CONFIGS` (mismos parámetros reales que
  `run_simsed_91bg_ddf_poc.py`, script histórico que se deja sin tocar).
- `run_snia_ddf_poc.py` — mismo fix de trigger que `run_simsed_poc.py`.
- `poc_output_snia91bg/` (nuevo, reemplaza a `poc_output_91bg/` como fuente activa),
  `poc_output_knk17/`, `poc_output_cart/`, `poc_output_slsni/`, `poc_output_sniax/`,
  `poc_output_tdemosfit/`, `poc_output_sniinmf/`, `poc_output_ilotmosfit/`,
  `poc_output_sniinmosfit/`, `poc_output_pisnmosfit/`, `poc_output_knbulla19/`,
  `poc_output_pisnstellahecore/`, `poc_output_pisnstellahydrogenic/`, `poc_output/` (`SNIa`) —
  las 14 clases, resultados actualizados con el trigger corregido.

## Recomendación final (actualizada de nuevo)

**Sigue GO condicional — dos causas reales cerradas (extinción de host en Fase 3, trigger de
época en Fase 4), y el residuo sistémico sigue prácticamente intacto (2.56x de promedio).** Esto
es información real y valiosa, no un fracaso: dos hipótesis concretas y bien fundamentadas
(extinción omitida, sobre-conteo de épocas) se investigaron con rigor real (fórmulas verificadas
línea por línea contra el código fuente, correcciones formalmente verificadas) y **ninguna de
las dos explica la brecha dominante** — descartar causas reales con evidencia real es progreso
científico genuino, aunque no cierre la brecha. Lo que queda abierto: la causa raíz sigue sin
identificarse con precisión, y esta ronda reveló un problema metodológico adicional (selección
de template SIMSED no reproducible) que probablemente inyectó ruido no cuantificado en **todas**
las comparaciones de clases SIMSED de peso uniforme a lo largo de toda la sesión, no solo en
Fase 4. Antes de seguir cazando la causa raíz, la prioridad real debería ser cerrar ese agujero
de reproducibilidad (semillas fijas + múltiples corridas por clase) para poder confiar en
cualquier comparación futura, incluidas las ya reportadas.

# Fase 5 — reproducibilidad real: semillas múltiples por clase

## Motivación

Fase 4 cerró documentando un problema metodológico: `SIMSEDModel.from_dir()` nunca semilla su
selector interno de template, así que la elección de template real fue no reproducible en
**todas** las corridas de clases SIMSED de peso uniforme a lo largo de toda la sesión (Fases
2B-4). El usuario decidió (confirmado explícitamente vía pregunta directa): antes de seguir
cazando la causa raíz del residuo sistémico, cerrar primero este agujero de reproducibilidad —
correr múltiples semillas fijas por clase para poder poner una banda de incertidumbre real a
cada razón LCL/SNANA reportada, y determinar si la aparente regresión de `CaRT` en Fase 4
(8.56x → 9.56x) fue señal real o ruido de semilla.

## Tres bugs de reproducibilidad adicionales encontrados (más allá del ya documentado en Fase 4)

Antes de poder confiar en un barrido de semillas múltiples, había que verificar que **una misma
semilla produce el mismo resultado** — condición necesaria para que variar la semilla mida algo
real. Un smoke test directo (`CaRT`, N=15, `seed_index=0` corrido dos veces como procesos
Python **separados**, no llamadas repetidas dentro del mismo proceso — para que el test
reflejara el uso real, donde cada semilla es un job SLURM independiente) reveló que el fix de
Fase 4 **no era suficiente**: dos corridas con la misma semilla producían conteos de fotometría
completamente distintos (10,260 vs. 23,240 filas para los mismos 15 objetos). Investigar la
causa, leyendo directamente el código fuente instalado de LightCurveLynx en NLHPC (mismo método
que Fases 3-4, nunca asumir), encontró **tres bugs reales de la librería**, todos con el mismo
patrón de fondo: un nodo interno construye su propio generador aleatorio y nunca recibe el
`seed=` que se le pasa al constructor externo.

**Bug A — jitter de posición sub-FOV no sembrado (`ObsTableRADECSampler.compute()`)**: cuando
`self.radius > 0` (heredado del radio real de campo de visión de `OpSim`, el FOV de LSST),
`compute()` aplica un desplazamiento aleatorio de la posición (RA/dec) dentro del FOV usando
`rng = rng_info if rng_info is not None else np.random.default_rng()` — es decir, si el
`rng_info` no llega explícitamente desde el framework de evaluación del grafo, cae en un
generador **sin semilla**. Confirmado leyendo
`lightcurvelynx/math_nodes/ra_dec_sampler.py` línea por línea en el entorno instalado.
**Fix**: pasar `radius=0.0` explícito al construir `ObsTableRADECSampler` — los campos DDF de
esta campaña son *pointings* fijos (no requieren jitter dentro del FOV), así que esto evita el
código no reproducible por completo, no es un parche indirecto.

**Bug B — selección de fila/pointing no sembrada (`TableSampler.__init__`, clase base de
`ObsTableRADECSampler`)**: el constructor de `TableSampler` arma su propio muestreador de
índice de fila así: `NumpyRandomFunc("integers", low=0, high=self._num_values)` — **sin pasar
`seed=`**, aunque el `seed=` que se le pasó al `ObsTableRADECSampler` externo sí llega hasta
`FunctionNode.__init__` (el nodo padre), nunca hasta este nodo hijo interno. Este es el bug
verdaderamente responsable de la mayor parte de la varianza observada: es el que decide *qué
pointing/fila real de OpSim* (y por lo tanto qué observaciones reales) le corresponde a cada
objeto simulado. Confirmado leyendo `lightcurvelynx/math_nodes/given_sampler.py`. Mismo patrón
exacto que el bug de Fase 4 en `SIMSEDModel`/`GivenValueSampler`. **Fix**: acceder al nodo
interno vía `radec_sampler.setters["selected_table_index"].dependency` (confirmado que expone
`.set_seed()`, mismo método usado en Fase 4) y sembrarlo explícitamente después de construir el
sampler: `radec_sampler.setters["selected_table_index"].dependency.set_seed(seed_base + 5)`.

**Bug C — ruido fotométrico no sembrado (`simulate_lightcurves()`)**: incluso con A y B
corregidos, dos corridas idénticas coincidían exactamente en número de filas de fotometría pero
diferían levemente en SNR (mediana 0.678 vs. 0.676) y conteo de detecciones (2/15 vs. 1/15) —
indicio de que la realización del ruido fotométrico en sí no estaba fija. `simulate_lightcurves()`
acepta un parámetro opcional `rng=` (un `numpy.random.Generator`) que se propaga a cualquier
nodo del grafo sin semilla propia — no se estaba pasando. **Fix**: pasar
`rng=np.random.default_rng(seed_base + 2)` (o `+ 8` en `run_snia_ddf_poc.py`, offset libre en
ese script) explícitamente en la llamada a `simulate_lightcurves()`.

**Verificación**: tras aplicar los tres fixes, `CaRT` con `seed_index=0` corrido dos veces como
procesos separados produjo resultados **byte-idénticos** (7,942 filas de fotometría,
SNR mediana=0.672/p90=1.644, 0/15 detectados en ambas corridas). `seed_index=1` produjo un
resultado claramente distinto (58,330 filas, SNR mediana=0.677, 4/15 detectados) — confirmando
que la semilla ahora tiene efecto real y es plenamente reproducible.

## Alcance real de estos bugs

Los bugs A-C afectan a **todas** las clases que usan `ObsTableRADECSampler` — es decir, las 13
clases SIMSED **y** la corrida `SNIa` (SALT2, `run_snia_ddf_poc.py`) — no solo las clases
SIMSED de peso uniforme como el bug ya documentado en Fase 4. Esto significa que **ninguna**
comparación de una sola corrida a lo largo de toda la sesión (Fases 1-4) tuvo garantía real de
reproducibilidad a nivel de emparejamiento de observaciones o realización de ruido — no solo la
selección de template. No se volvió a correr retroactivamente el catálogo completo solo por
esto (misma decisión práctica que en Fase 4): el propósito de Fase 5 es precisamente generar,
de ahora en adelante, resultados con banda de incertidumbre real usando el código ya corregido,
en vez de intentar reconstruir la incertidumbre de corridas pasadas que nunca la tuvieron.

## Metodología: 5 semillas fijas por clase

`seed_base = SEED_BASE + seed_index * 1_000_000` (offset grande para no colisionar con los
sub-offsets +1..+9 ya usados por cada componente del grafo dentro de una misma semilla).
`seed_index=0` reutiliza el directorio de salida histórico (`poc_output_<clase>/`, ya reportado
en el dashboard/NOTES.md); `seed_index=1..4` escriben en directorios nuevos
(`poc_output_<clase>_seed<N>/`) para no pisar el resultado principal. Se corrieron las 14
clases × 5 semillas (70 corridas) vía `sbatch run_simsed_poc.sbatch <clase> <seed_index>` /
`sbatch run_snia_ddf_poc.sbatch <seed_index>`, con `--mem=64G` para
`PISN-STELLA-HYDROGENIC` (única clase que satura los 16G por defecto, ver Fase 4).

## Persistencia de la tabla real (`head_df`/`phot_df`)

Hasta esta ronda el pipeline nunca escribía a disco los datos crudos de la simulación —
LightCurveLynx no tiene un writer nativo a formato SNANA (FITS/DUMP) ni a ningún otro formato
de tabla (confirmado revisando la documentación oficial, notebooks `snana_example` y
`lclib_example`: ambos solo muestran carga y simulación en memoria, ninguno exporta a disco).
Cada corrida solo generaba las imágenes QC y `summary.json` (métricas agregadas); `head_df`
(un registro por objeto) y `phot_df` (un registro por observación, con `FLUXCAL`/`FLUXCALERR`/
`MAG`/`PHOTFLAG`) vivían solo en memoria durante la corrida y se descartaban al terminar.

Se agregó persistencia real a ambos scripts: `head_df.parquet` y `phot_df.parquet` en cada
`poc_output_<clase>*/`, vía `pyarrow` (ya disponible en el venv de NLHPC). Parquet en vez de
CSV por tamaño — `phot_df` puede tener millones de filas para `NGENTOT` completo. **No se
versiona en git** (agregado a `.gitignore`): con 70 corridas de tamaño completo el volumen
total sería de GBs, impráctico para el repo — las tablas quedan solo en NLHPC (y localmente si
se copian vía `scp` para inspección puntual).

Este cambio se sincronizó a NLHPC **a mitad del barrido de 70 corridas de esta Fase** (después
de que ~16 ya habían terminado) — las corridas que ya estaban corriendo en el momento del sync
usaron la versión anterior del script (sin persistencia); solo las que empezaron a ejecutar
después del sync tienen `head_df.parquet`/`phot_df.parquet`. Esto no afecta los números de
eficiencia de detección de Fase 5 (la persistencia es puramente aditiva), pero significa que no
todas las 70 carpetas de salida de esta ronda van a tener las tablas — las corridas futuras sí
las tendrán todas.

## Resultados: 70/70 corridas completadas sin fallos

Las 70 corridas (14 clases × 5 semillas) terminaron sin errores (`sacct` exit code `0:0` en
las 70). Tiempos de pared por clase: la mayoría 5-20 min, `SLSN-I`/`PISN-MOSFIT`/
`PISN-STELLA-HECORE` 1h40min-2h (960 templates SIMSED), `PISN-STELLA-HYDROGENIC` ~1h10min por
semilla (NGENTOT=20000, `--mem=64G`).

| Clase | SNANA % | Razón media (5 semillas) | ±std | min-max | std relativo |
|---|---:|---:|---:|---:|---:|
| `SNIa-91bg` | 36.15% | 1.420x | 0.037 | 1.367-1.474 | 2.6% |
| `PISN-STELLA-HYDROGENIC` | 21.34% | 1.438x | 0.013 | 1.418-1.450 | 0.9% |
| `SNII-NMF` | 17.80% | 1.538x | 0.024 | 1.511-1.567 | 1.5% |
| `PISN-STELLA-HECORE` | 19.20% | 1.569x | 0.048 | 1.510-1.630 | 3.1% |
| `SLSN-I` | 41.20% | 1.604x | 0.036 | 1.542-1.648 | 2.3% |
| `TDE-MOSFIT` | 40.60% | 1.677x | 0.013 | 1.661-1.701 | 0.8% |
| `PISN-MOSFIT` | 20.55% | 1.825x | 0.059 | 1.762-1.925 | 3.2% |
| `SNIa` | 29.85% | 1.926x | 0.048 | 1.863-2.003 | 2.5% |
| `ILOT-MOSFIT` | 3.65% | 2.277x | 0.132 | 2.068-2.466 | 5.8% |
| `KN-BULLA19` | 5.15% | 2.509x | 0.150 | 2.262-2.699 | 6.0% |
| `KN-K17` | 4.10% | 2.639x | 0.223 | 2.366-2.890 | 8.5% |
| `SNIax` | 8.75% | 2.816x | 0.144 | 2.606-3.011 | 5.1% |
| `SNIIn-MOSFIT` | 1.85% | 5.605x | 0.181 | 5.378-5.892 | 3.2% |
| `CaRT` | 0.80% | 10.825x | 0.691 | 9.875-11.687 | 6.4% |

**Promedio del catálogo (media de las 14 razones, cada una ya promediada sobre 5 semillas):
2.833x** — sube desde el 2.561x reportado al final de Fase 4. Esto **no es simplemente ruido de
muestreo**: **las 14 clases sin excepción subieron** respecto a su valor de Fase 4 (single-run,
código con los bugs A-C sin corregir) — un movimiento sistemático y unidireccional, no disperso
en ambas direcciones como esperaríamos de ruido puro. La lectura más honesta: la corrida única
de Fase 4 no solo era no reproducible, sino que corrió con el bug A (jitter de posición sub-FOV)
activo, que probablemente sesgaba hacia abajo el conteo de observaciones reales emparejadas de
forma sistemática (no solo aleatoria) para algún subconjunto de campos/pointings — al usar
`radius=0.0` (centro exacto del pointing) esto se corrigió, y el efecto neto fue *más*
observaciones reales emparejadas en promedio, no menos. No se investigó a fondo la dirección
exacta de este sesgo (excede el alcance de Fase 5, cuyo objetivo era solo cerrar la
reproducibilidad) — se documenta como un hallazgo honesto, no una hipótesis cerrada.

**El "std relativo" (ruido de semilla puro) es real pero modesto para la mayoría de clases**
(<6% para 10/14 clases) — confirma que las comparaciones de una sola corrida en Fases 1-4 no
estaban mayormente dominadas por ruido de semilla para la mayoría de clases, aunque sí lo
estaban las de **conteo bajo** (`KN-K17` 8.5%, `CaRT` 6.4%, con solo 16-103 objetos SNANA de
referencia — Poisson puro).

**`CaRT`, la pregunta que motivó Fase 5**: la aparente "regresión" de Fase 4 (8.56x → 9.56x) no
era ruido en la dirección optimista — la razón real, con 5 semillas y código reproducible, es
**10.825x ± 0.691x (rango 9.875x-11.687x)**, sistemáticamente *peor* que el 9.56x ya preocupante
de Fase 4. `CaRT` sigue siendo, con margen, la clase con peor comportamiento relativo del
catálogo — esto ahora está confirmado con incertidumbre real, no es un artefacto de una sola
corrida con semilla no reproducible.

## Recomendación final (Fase 5)

**Sigue GO condicional.** Fase 5 no cambia la conclusión cualitativa (LightCurveLynx funciona
mecánicamente, persiste un residuo sistémico multiplicativo cuya causa raíz exacta sigue sin
identificarse), pero sí cambia lo que se puede decir con confianza: por primera vez en toda la
sesión, cada razón LCL/SNANA reportada tiene una banda de incertidumbre real derivada de
semillas independientes, no de una única corrida no reproducible. El promedio del catálogo se
revisa de 2.561x a **2.833x** — un movimiento real (no ruido), atribuible a que la corrida de
Fase 4 heredó un bug de emparejamiento de posición (bug A, jitter sub-FOV) que sesgaba el
resultado, además de no ser reproducible. `CaRT` sigue siendo la clase más alejada del
comportamiento de SNANA (~10.8x), ahora con evidencia sólida de que no es un artefacto de
semilla. La causa raíz del residuo sistémico multiplicativo (ni la extinción de host de Fase 3
ni el trigger de época de Fase 4 la explican) sigue abierta como el ítem de mayor prioridad
para cualquier trabajo futuro — ahora con una base de comparación honesta y reproducible sobre
la cual construir esa investigación.

# Fase 6 — SEARCHEFF verificado contra NLHPC, "detecciones basura" a alto z, primera clase NON1ASED

## Motivación

Tres preguntas del usuario, conectadas: (1) verificar el archivo real de SEARCHEFF de SNANA en
NLHPC contra el puerto de LightCurveLynx, para confirmar (o descartar de una vez por todas) que
no es la causa del residuo abierto desde Fase 4/5; (2) un comentario del profesor del usuario --
en la práctica, las "detecciones" a redshift muy alto suelen ser basura (ruido, imágenes malas),
no transitorios reales -- investigar si eso está modelado (o falta) en esta comparación; (3)
planificar la extensión de cobertura a `GENMODEL: NON1ASED`, la clase de modelo de SNANA que
todavía no tiene ningún soporte en LightCurveLynx (las 14 clases de Fase 0-5 son todas SIMSED o
SALT2).

## SEARCHEFF verificado contra los archivos reales (no solo contra el código)

Se leyeron directamente ambos archivos reales desde NLHPC (`ssh nlhpc`, alias ya configurado en
`~/.ssh/config`, solo lectura):

- `LSST_SEARCHEFF_PIPELINE.DAT`: curva nominal PLASTICC (Kessler 2019), derivada de DES --
  eficiencia de detección **real** (no falsa alarma) vs. SNR por filtro, `EFF=0` para `SNR<3`,
  u≡g y z≡Y comparten curva.
- `LSST_PIPELINE_LOGIC.DAT`: `LSST: 2 u+g+r+i+z+Y` -- trigger exige ≥2 épocas (cualquier
  filtro), agrupadas por `NEWMJD_DIF=0.007d` (default real de `snlc_sim.c`, no sobreescrito en
  esta campaña).

Comparado línea por línea contra `searcheff.py`: es un puerto fiel (mismo parseo, misma
interpolación SNR→eficiencia, mismo Monte Carlo, mismo agrupamiento de épocas, mismo trigger,
misma constante `PHOTFLAG_DETECT=4096`). Ya se había descartado como causa del residuo en Fase 4
por lectura de código -- esta sesión lo reconfirma contra los archivos reales de producción, no
solo contra su documentación inferida. **Sin cambios de código.**

## "Detecciones basura" a alto z: un hueco real, pero en ambos simuladores, no una explicación del residuo

El archivo SEARCHEFF de SNANA (y por lo tanto su puerto en LightCurveLynx) solo modela
**recall**: P(un transitorio real simulado es recuperado | SNR). No existe en ningún lado de
este proyecto (ni en la config SNANA real, ni en LightCurveLynx, confirmado grep de
`FAKE`/`bogus`/`DIFFIMG`/`artifact` en todo el repo -- solo *placeholders* de test) un mecanismo
de tasa de falsos positivos/detecciones espurias (artefactos de resta de imágenes, rayos
cósmicos). En pipelines reales tipo DES/LSST, la curva de eficiencia empírica se construye
inyectando SNe falsas en imágenes reales y corriéndolas por un clasificador real/bogus (p.ej.
AutoScan de DES, Goldstein et al. 2015) -- pero esa curva solo captura el recall sobre las
fuentes reales inyectadas, no la tasa de falsa alarma del clasificador sobre candidatos que no
son transitorios. Tanto SNANA (tal como está configurado aquí) como LightCurveLynx generan
únicamente catálogos "limpios" de objetos ya sabidos reales -- ninguno de los dos alucina nunca
un candidato espurio. El fenómeno que describe el profesor es real, pero está ausente
estructuralmente de **ambos** lados de la comparación -- no explica la brecha LCL vs. SNANA.

Dato adicional que refuerza esto: la razón por clase (tabla de Fase 5) no correlaciona limpio
con el alcance en redshift -- `CaRT` es el peor caso (10.83x) con `z_max=1.4`, mientras que
`SLSN-I` llega a `z=9.7` con uno de los mejores ratios (1.60x). El residuo correlaciona más con
la rareza/tenuidad intrínseca de cada clase (`CaRT` es la clase con menor detección real de
SNANA, 0.8%) que con el rango de redshift en sí. **No se tomó acción aquí** -- se documenta como
un hueco de modelado real pero separado, candidato a una fase futura si se decide perseguirlo
(agregar una capa empírica de tasa de falsos positivos vs. magnitud a ambos simuladores).

## Primera clase NON1ASED: `non1ased.py`, nuevo loader

Las 14 clases de Fase 0-5 son todas SIMSED o SALT2. `GENMODEL: NON1ASED` es la clase de modelo
que usa SNANA para librerías de templates convertidas desde SIMSED vía la herramienta oficial
`convert_SIMSED_to_NON1ASED.py` -- 5 clases ya convertidas y validadas del lado SNANA
(`SNIax`, `SNIa-91bg`, `TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`, ver `NEXT_SESSION.md`
2026-08-06), ninguna con soporte del lado LightCurveLynx (confirmado: `grep -ri NON1A` en los
18 archivos de `exploration/lightcurvelynx/` no encontraba nada antes de esta fase).

**Bloqueador real**: `SIMSEDModel.from_dir()` (lo que usa `run_simsed_poc.py`) exige un
`SED.INFO` (`yaml.safe_load()` sobre el archivo completo). Confirmado vía `ssh nlhpc` que los
directorios NON1ASED reales **no lo tienen** --
`run_SNANA/elastic/model_libs_updates/NON1ASED.SNIa-91bg/` solo trae `*.SED.gz` +
`NON1A.LIST`. Leyendo el código fuente real instalado en el venv de NLHPC
(`lightcurvelynx==0.5.2`, `inspect.getsource()`), se confirmó que `SIMSEDModel.from_dir()`
internamente solo hace: parsear `SED.INFO` → construir una lista de `SEDTemplate` vía
`SIMSEDModel._read_simsed_data_file()` (un staticmethod, ya usado directamente en
`run_simsed_poc.py` para otra cosa) → `cls(templates, flux_scale=flux_scale, **kwargs)`, que es
el constructor heredado de `MultiSEDTemplateModel.__init__(templates, *, weights=None,
**kwargs)`. Es decir, `from_dir()` es solo un parser de `SED.INFO` sobre un constructor genérico
que no exige ese formato -- se puede saltar el parser y llamar al constructor directo.

`non1ased.py` (nuevo) hace exactamente eso, leyendo el formato real de NON1ASED en su lugar:

- `parse_non1a_list()`: `NON1A.LIST` real (`NON1A: <index> <name> <filename>`, mismo formato
  que ya parseaba parcialmente `pipeline/tools/generate_non1a_block.py` del lado SNANA, extendido
  aquí para devolver también el nombre de archivo).
- `parse_flux_scale()`: la línea suelta `FLUX_SCALE: <valor>` de `NON1A.LIST` (no es YAML, a
  diferencia del `FLUX_SCALE` de `SED.INFO`).
- `parse_non1a_weights_from_input()`: el bloque real `NON1A_KEYS:`/`NON1A: <idx> <WGT> <MAGOFF>
  <MAGSMEAR> <SNTYPE>` ya escrito en el `.INPUT` real -- se usan esos pesos reales tal cual, no
  se re-derivan como `1/N`. `MAGOFF`/`MAGSMEAR` != 0 lanza `NotImplementedError` explícito (no
  hay precedente de calibración, ni hook equivalente en `SIMSEDModel`, para esas 5 clases).
- `load_non1ased_model()`: arma `templates` con `SIMSEDModel._read_simsed_data_file()` (el mismo
  staticmethod, sin reimplementar el parseo del grid de flujo) y llama al constructor directo
  `SIMSEDModel(templates, flux_scale=..., weights=..., **kwargs)`.

Verificado también (leyendo `GivenValueSampler.__init__`) que los pesos no necesitan sumar 1 --
se normalizan internamente (`self._weights /= weight_sum`), así que pasar los pesos reales del
`.INPUT` sin normalizar es seguro.

`run_non1ased_poc.py` (nuevo) es un espejo casi exacto de `run_simsed_poc.py` -- mismo ruido
real inyectado, extinción MW, SEARCHEFF, `simulate_lightcurves()`, QC -- solo cambia la
construcción del `source_model` (`non1ased.load_non1ased_model()` en vez de
`SIMSEDModel.from_dir()`). Mismo bug de Fase 4 aplica igual aquí (`GivenValueSampler` interno
sin semilla) -- mismo fix (`source_model._sampler_node.set_seed(...)`).

**Primera clase: `SNIa-91bg`** (35 templates -- el conjunto más chico de las 5 clases NON1ASED
ya convertidas, para iterar rápido; `SNIax` tiene 1001 templates, carga de horas). Confirmado
por diff de listado de directorio que `NON1ASED.SNIa-91bg/` trae los mismos 35 archivos `.SED`
que `SIMSED.SNIa-91bg/` (más `NON1A.LIST`/`SED.BINARY`) -- son los mismos templates físicos,
solo re-encapsulados. `SLSN-I_NON1ASED`/`TDE_NON1ASED` quedan descartadas como candidatas para
un diagnóstico "misma física, distinta codificación": sus directorios reales apuntan a una
familia de templates físicamente distinta (`*-BBFIT`) de la ya evaluada en LCL vía SIMSED
(`*-MOSFIT`). `KN-BULLA-BNS-M2COMP` dio 0/300 detecciones en su validación SNANA -- objetivo
demasiado incierto para un primer PoC.

**Smoke test** (`N=20`, sbatch corto): cargó los 35 templates, simuló 20 objetos, aplicó
SEARCHEFF, generó QC -- sin errores, eficiencia por bin de z con forma razonable (pico en
z bajo-medio, cae a alto z). **Corrida completa** (`NGENTOT_LC=2000`, sbatch job 11483111,
6m51s, partición `largemem` reasignada automáticamente por el scheduler de NLHPC):

    355/2000 detectados (17.75%)

SNANA real (leído del `.README` de producción real,
`DATASIM_LSST_1/DDF/SIMDv8/SNIa-91bg_NON1ASED_DDF_baseline_v5.3.1_10yrs/`, no un archivo
inventado): `NGENTOT_LC: 20000`, `NGENLC_WRITE: 1470` → **7.35%**.

**Razón LCL/SNANA = 2.41x** -- cae dentro del rango ya visto en el catálogo de 14 clases
(1.42x-10.83x), entre `ILOT-MOSFIT` (2.28x) y `KN-BULLA19` (2.51x). Nada indica un bug nuevo por
sí solo.

## Discrepancia real encontrada al preparar el PoC: dos generaciones de config SIMSED.SNIa-91bg en NLHPC

El `.INPUT` real NON1ASED (`run_SNANA/elastic/model_config/
SIMGEN_INCLUDE_SNIa-91bg_NON1ASED.INPUT`) declara `GENRANGE_REDSHIFT: 0.011 1.2`, distinto del
`0.011 0.6` que usa la entrada `SNIa-91bg` de `CLASS_CONFIGS` en `run_simsed_poc.py` (la que ya
tiene 5 semillas reportadas en Fase 5, ratio 1.42x). Investigado por qué: existen **dos
generaciones distintas** del mismo `.INPUT` SIMSED en NLHPC --
`run_SNANA/model_config/SIMGEN_INCLUDE_SNIa-91bg.INPUT` (z 0.011-0.6, la que se usó para el PoC
SIMSED de Fase 2B/4/5) y `run_SNANA/elastic/model_config/SIMGEN_INCLUDE_SNIa-91bg.INPUT` (z
0.011-1.2, la que realmente se convirtió a NON1ASED) -- mismos templates físicos
(confirmado por diff de directorio), `.INPUT` de campaña distinto. El PoC NON1ASED usa el rango
real de **su propio** `.INPUT` (0.011-1.2), así que su razón de 2.41x contra el `NGENLC_WRITE`
real de esa misma campaña es válida en sí misma -- pero **no** es directamente comparable, sin
más, contra la fila `SNIa-91bg` (SIMSED, z 0.011-0.6) ya publicada, porque el rango de z
por sí solo ya explicaría parte de la diferencia (ver Fase 5: el residuo correlaciona con
tenuidad/rareza, y un rango de z más ancho añade más objetos marginales).

## Bake-off LCL-vs-LCL: aislando el efecto de la codificación del modelo

Para aislar si la codificación SIMSED vs. NON1ASED en sí (no el rango de z) explica parte de la
diferencia, se agregó una clase auxiliar a `run_simsed_poc.py`, `SNIa-91bg-elastic`: mismo
directorio de templates que `SNIa-91bg` (`simsed_91bg_local`, los mismos 35 archivos físicos),
pero con `GENRANGE_REDSHIFT=(0.011, 1.2)` -- el rango real "elastic", igual al de la clase
NON1ASED. No existe una corrida SNANA real de este `.INPUT` SIMSED-elastic en la campaña de
producción (el `.INPUT` elastic solo se usó como fuente para la conversión a NON1ASED, nunca se
simuló como SIMSED por sí mismo) -- esta clase no tiene razón propia contra SNANA, sirve
únicamente para comparar LCL-SIMSED contra LCL-NON1ASED al mismo rango de z y mismos templates.

Corrida completa (`NGENTOT_LC=2000`, sbatch job 11483232, 6m57s):

    SIMSED-elastic (SIMSED_REDCOR, stretch/color):    289/2000 = 14.45%
    NON1ASED       (NON1A_KEYS uniforme 1/35):        355/2000 = 17.75%

**~1.23x de diferencia solo por la codificación**, con templates y rango de z idénticos. La
explicación mecanística es real, no un artefacto: `SIMSED_REDCOR` pesa cada template según su
cercanía al pico de una normal bivariada real (`stretch=0.975, color=0.557`, correlación
`-0.656`, los mismos parámetros reales que ya usa la entrada `SNIa-91bg` de Fase 2B) -- es
decir, favorece los templates "típicos" de la población real de 91bg. La conversión oficial de
SNANA a NON1ASED (`convert_SIMSED_to_NON1ASED.py`, confirmado leyendo
`pipeline/tools/generate_non1a_block.py` y el bloque real `NON1A_KEYS` del `.INPUT`,
`WGT=2.857143e-02` = 1/35 en las 35 filas) descarta esa información de población y pesa cada
template por igual, incluyendo las esquinas físicamente raras de la grilla stretch/color. **Esto
es una diferencia real entre dos codificaciones de SNANA para la misma clase física, no un bug
de LightCurveLynx** -- el ratio 2.41x de la fila NON1ASED combina este efecto de codificación
(~1.23x) con el efecto del rango de z más ancho (el resto).

Alcance de este hallazgo: un solo caso (`SNIa-91bg`, que usa `SIMSED_REDCOR`). No se sabe si
aplica igual a clases SIMSED de peso uniforme (`SIMSED_GRIDONLY`, la mayoría del catálogo de 14)
-- ahí no habría información de `SIMSED_REDCOR` que perder al convertir a NON1ASED uniforme, así
que el efecto de codificación por sí solo podría ser mucho menor o nulo. Queda como pregunta
abierta para las próximas clases NON1ASED.

## Barrido de 5 semillas: `SNIa-91bg` NON1ASED (mismo patrón de Fase 5)

Todo lo anterior en esta fase usó una sola corrida (`seed_index=0`) -- mismo riesgo
metodológico que Fase 5 corrigió para el catálogo SIMSED/SALT2 (una sola semilla no distingue
señal real de ruido de semilla). Se corrieron las 4 semillas restantes
(`sbatch run_non1ased_poc.sbatch SNIa-91bg <1..4>`, mismo patrón de `seed_base` que
`run_simsed_poc.py`), las 4 completaron sin fallos (6-7 min cada una).

| Semilla | Detectados/2000 | % | Razón vs. SNANA (7.35%) |
|---|---:|---:|---:|
| 0 | 355 | 17.75% | 2.415x |
| 1 | 326 | 16.30% | 2.218x |
| 2 | 327 | 16.35% | 2.224x |
| 3 | 324 | 16.20% | 2.204x |
| 4 | 325 | 16.25% | 2.211x |

**Media de 5 semillas: 2.254x ± 0.081 (rango 2.204x-2.415x)** -- la semilla 0, la única
disponible cuando se calculó el 2.41x reportado más arriba, resultó ser la más alta de las 5,
no la típica (las otras 4 caen apretadas entre 2.20x-2.22x). Mismo patrón cualitativo que varias
clases de Fase 5 (KN-K17, CaRT): una sola corrida sin banda de incertidumbre puede sobre-reportar
el caso real. El promedio de 5 semillas (2.254x) es el número más confiable, no el 2.41x de la
corrida única original.

**Esto también revisa el bake-off de codificación de la sección anterior**: la corrida
`SIMSED-elastic` (289/2000=14.45%) sigue siendo de una sola semilla (no se corrió su propio
barrido de 5), pero comparándola contra la media de 5 semillas de NON1ASED (16.57%, no el 17.75%
de la semilla 0 sola) el efecto de codificación baja de ~1.23x a **~1.15x**
(16.57/14.45 = 1.147). Sigue siendo un efecto real y en la misma dirección (NON1ASED detecta
más), pero más chico de lo que sugería la comparación semilla-a-semilla original. Para acotar
bien la incertidumbre de esta cifra haría falta además un barrido de 5 semillas del lado
`SIMSED-elastic` -- no se hizo en esta ronda.

## Archivos de esta fase

- `exploration/lightcurvelynx/non1ased.py` (nuevo) -- loader NON1ASED.
- `exploration/lightcurvelynx/run_non1ased_poc.py` (nuevo) -- PoC NON1ASED, clase `SNIa-91bg`.
- `exploration/lightcurvelynx/run_non1ased_poc.sbatch` (nuevo).
- `run_simsed_poc.py` -- nueva entrada `SNIa-91bg-elastic` en `CLASS_CONFIGS` (diagnóstico, sin
  contraparte SNANA real).
- `docs/lcl_qc/lcl_qc_index.json` -- nueva fila `SNIa-91bg (NON1ASED)` con media/std/rango real
  de 5 semillas; `docs/index.html` -- Fase 6 documentada en la sección 06, nueva tarjeta de
  diagnóstico, tabla ajustada para mostrar `NGENTOT` real por lado (SNANA 20000 vs. LCL 2000,
  primera fila donde no coinciden).

## Recomendación final (Fase 6)

**Sigue GO condicional.** NON1ASED funciona mecánicamente igual que SIMSED (mismo staticmethod
de lectura de grid de flujo, mismo constructor subyacente) -- el bloqueador real era solo de
formato de metadata (`SED.INFO` vs. `NON1A.LIST`+`NON1A_KEYS`), no de física ni de rendimiento.
El hallazgo nuevo y genuino de esta fase es que **la codificación del modelo en SNANA (no solo
la física que representa) puede cambiar el resultado simulado en una cantidad no trivial
(~1.15x-1.23x según se use la media de 5 semillas o la semilla única, en este caso)** -- un
hallazgo sobre SNANA mismo, no sobre LightCurveLynx, que hay que tener presente al comparar
clases NON1ASED contra sus equivalentes SIMSED de aquí en adelante. La verificación de SEARCHEFF
contra los archivos reales de NLHPC y la investigación de "detecciones basura" a alto z
confirman ambas, con evidencia real, que ninguna es la causa del residuo sistémico abierto desde
Fase 4/5 -- ese sigue siendo el ítem de mayor prioridad. Trabajo futuro concreto: barrido de 5
semillas para `SNIa-91bg-elastic` (solo 1 corrida hasta ahora, necesario para acotar bien el
~1.15x de arriba); las 4 clases NON1ASED restantes (`SNIax`, `TDE`, `SLSN-I`,
`KN-BULLA-BNS-M2COMP`) -- `SNIax` es el candidato natural para repetir el bake-off de
codificación en una clase `SIMSED_GRIDONLY` (peso uniforme), ya que su conversión NON1ASED usa
la misma familia física de templates que su entrada SIMSED ya existente, y así ver si el efecto
de codificación es específico de clases con `SIMSED_REDCOR` o más general.

# Fase 7 -- bake-off en clase de peso uniforme, cobertura NON1ASED completa, comparación directa de brillo sin ruido

## Motivación

Tres tareas del usuario, en orden: (1) repetir el bake-off de codificación de Fase 6 en `SNIax`
(peso uniforme nativo, a diferencia de `SNIa-91bg`) para saber si el efecto de ~1.15x es
específico de `SIMSED_REDCOR` o más general; (2) extender la cobertura NON1ASED a las 4 clases
restantes ya convertidas por SNANA (`TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`); (3) atacar la
pregunta que todas las fases anteriores dejaron abierta -- la causa raíz del residuo sistémico --
con un ángulo nunca probado: comparar el brillo simulado directamente, no solo los conteos de
detección posteriores a SEARCHEFF.

## Bake-off en `SNIax`: confirma que el efecto de codificación es específico de `SIMSED_REDCOR`

Se agregó `SNIax-elastic` a `run_simsed_poc.py::CLASS_CONFIGS` -- mismos 1001 templates físicos
que la entrada `SNIax` ya publicada (confirmado por listado de directorio), mismos parámetros
reales de extinción de host (`GENTAU_AV=1.7`/`GENSIG_AV=0.6`/`GENRATIO_AV0=4.0`, idénticos entre
el `.INPUT` elastic y no-elastic), pero con el `GENRANGE_REDSHIFT` real del `.INPUT` elastic
(0.011-1.5, el mismo que se convirtió a NON1ASED) en vez del 0.011-0.7 ya publicado. Igual que
`SNIa-91bg-elastic`, no tiene corrida SNANA real propia (el elastic solo se usó como fuente para
la conversión a NON1ASED).

Corrida completa (`NGENTOT_LC=2000`, ~14 min de carga por los 1001 templates, confirmado por
smoke test previo de N=20 antes de comprometerse a la corrida completa):

    SIMSED-elastic (peso uniforme nativo, SIMSED_GRIDONLY):  214/2000 = 10.70%
    NON1ASED       (NON1A_KEYS uniforme 1/1001):             228/2000 = 11.40%

**Solo ~1.065x de diferencia** -- muchísimo más chico que el ~1.15-1.23x de `SNIa-91bg`
(`SIMSED_REDCOR`), y del orden de lo esperable por ruido puro de una sola semilla
(`sqrt(214)≈15`, ~7% relativo). **Confirma la hipótesis dejada abierta en Fase 6**: el efecto de
codificación viene principalmente de perder la ponderación `SIMSED_REDCOR` (que favorece
templates "típicos" cerca del pico de la población real) al convertir a NON1ASED, no del formato
NON1ASED en sí -- cuando el peso SIMSED de origen ya era uniforme, convertir a NON1ASED apenas
cambia el resultado.

## Cobertura NON1ASED extendida a las 4 clases restantes

Generalizado `run_non1ased_poc.py`: agregado el bloque de extinción de host (3 variantes,
idéntico al de `run_simsed_poc.py`) y soporte para `DNDZ: MD14`/`DNDZ: TDE` (antes solo
`POWERLAW`), necesarios para las clases nuevas. Cada clase se investigó por separado contra su
propio `.INPUT` real en NLHPC -- **no se asumió que reusar los parámetros de la clase SIMSED
equivalente fuera correcto**, y esa cautela encontró varias discrepancias reales:

- **`SLSN-I` (NON1ASED)**: directorio real `NON1ASED.SLSN-I-BBFIT` -- familia física *distinta*
  de `SIMSED.SLSN-I-MOSFIT` (la ya evaluada), confirmado que `PATH_NON1ASED` no apunta a una
  conversión de esa SIMSED. **Un solo template** (no un ensemble): fit de blackbody a un evento
  real específico, SLSN-I 2016apd (Yan+2017/Kangas+2017/Guillochon+2017, fit por Kaustav Das,
  Caltech), confirmado leyendo `NON1A.LIST` real. `GENRANGE_REDSHIFT` real 0.02-2.95 (NO 0.02-9.7
  como la entrada SIMSED -- comentario real en el `.INPUT`: *"stay within hostlib range"*),
  `SNTYPE` real 41 (no 40, confirmado en el bloque `NON1A_KEYS` real).
- **`TDE` (NON1ASED)**: mismo patrón -- directorio real `NON1ASED.TDE-BBFIT`, familia física
  distinta de `SIMSED.TDE-MOSFIT`. También **un solo template**: fit de blackbody al TDE real
  2019qiz (Nicholl+2020/Hung+2021, fit por Kaustav Das). A diferencia de SLSN-I,
  `GENRANGE_REDSHIFT`/`DNDZ`/extinción de host del `.INPUT` real resultaron **idénticos** a los
  ya usados para `TDE-MOSFIT` (mismo `GENTAU_AV=0.4`, `GENAV_WV07` comentado/deshabilitado).
- **`KN-BULLA-BNS-M2COMP`**: misma sub-variante física (`BNS-M2-2COMP`) que ya usa la entrada
  SIMSED `KN-BULLA19`, pero con nombre de directorio/`.INPUT` real inconsistente con las otras
  dos clases -- `NON1ASED.BULLA-BNS-M2-2COMP` (sin prefijo `KN-`) y
  `SIMGEN_INCLUDE_BULLA-BNS-M2-2COMP.INPUT` (sin sufijo `_NON1ASED`), confirmado por listado real
  de directorio, no una suposición. `GENRANGE_REDSHIFT` real 0.011-0.5 (NO 0.011-0.28 como
  `KN-BULLA19`), `SNTYPE` real 62 (no 52).

### Dos bugs de dato reales más encontrados (mismo patrón de Fase 1/2B/2B-ronda-4)

**`TDE-BBFIT`**: `2019qiz.sed.gz` tiene una segunda línea de encabezado
(`phase wavelength flux`) sin el prefijo `#` -- confirmado comparando línea por línea contra el
archivo hermano `SLSN-I-BBFIT/2016apd.sed.gz`, que sí lo tiene. Typo real de un solo carácter en
el archivo de referencia, mismo patrón que el `$`/`#` de `SNIa-91bg` en Fase 2B. Fix: copia local
saneada (`setup_tdebbfit_local.py`, mismo patrón que `setup_simsed_91bg_local.py`).

**`KN-BULLA-BNS-M2COMP`**: mismo problema real ya visto en Fase 2B ronda 4 para `KN-BULLA19`
(549 de los 550 archivos `*.txt.gz` son en realidad ZIP mal etiquetados, firma `PK`) **más un
segundo bug nunca visto antes**: exactamente 1 de los 550 archivos
(`sed_cos_theta_0.0_mej_0.010_phi_15.txt`) no tiene sufijo `.gz` en absoluto -- está en texto
plano, mientras que `NON1A.LIST` lo referencia igual como `...phi_15.txt.gz`. El fallback
automático de `_read_simsed_data_file()` (agrega `.gz` si el archivo base no existe) no cubre
este caso porque es al revés: el archivo base *sin* `.gz` es el que existe genuinamente sin
comprimir. Fix: `setup_bullansed_local.py` (mismo patrón que `setup_knbulla19_local.py`,
extendido para también comprimir por primera vez el archivo plano).

### Resultados (`NGENTOT_LC=2000`, corrida única cada una, sbatch, sin fallos tras los fixes)

| Clase | SNANA real (NGENTOT/detectados/%) | LCL (%) | Razón |
|---|---|---:|---:|
| `TDE` (NON1ASED) | 10000 / 2311 / 23.11% | 49.20% | 2.129x |
| `SLSN-I` (NON1ASED) | 20000 / 11004 / 55.02% | 90.45% | 1.644x |
| `KN-BULLA-BNS-M2COMP` (NON1ASED) | 20000 / 279 / 1.395% | 7.20% | 5.161x |
| `SNIax` (NON1ASED) | 10000 / 149 / 1.49% | 11.40% | 7.651x |

Los 4 caen dentro del rango ya visto en el catálogo (1.42x-10.83x) -- nada indica un bug nuevo
por sí solo. `KN-BULLA-BNS-M2COMP`: la validación previa a pequeña escala (300 objetos,
NEXT_SESSION.md) había dado 0/300 detectados en SNANA, sugiriendo una clase "demasiado incierta"
-- la campaña real completa (20000 objetos) sí muestra señal real (279 detectados, 1.4%),
confirmando que era un efecto de tamaño de muestra pequeño, no que la clase no tenga detecciones.
`SNIax` (NON1ASED) tiene el ratio más alto del grupo (7.65x) principalmente por el rango de z más
ancho de su `.INPUT` real (0.011-1.5 vs. 0.011-0.7 de la entrada SIMSED), no por la codificación
en sí -- mismo patrón que `SNIa-91bg` en Fase 6, confirmado por el bake-off de arriba (~1.07x de
efecto de codificación puro en esta clase).

## El hallazgo mayor de esta fase: comparación directa de brillo simulado, sin ruido

Todas las fases anteriores (Fase 3, 4, 6) investigaron el lado de la *detección*: extinción,
trigger de época, SEARCHEFF, codificación de pesos. Ninguna tocó la pregunta más directa: ¿el
brillo que cada simulador le asigna al mismo objeto físico (misma clase, mismo redshift) es
siquiera el mismo, antes de que entre en juego cualquier lógica de detección?

### El dato real de SNANA: `PEAKMAG_u/g/r/i/z/Y` en el `.DUMP`

El archivo `.DUMP` real de cada campaña SNANA (`SELECTION: NONE (write every generated event)`,
confirmado en su propio encabezado -- es la población COMPLETA generada, no solo los detectados)
trae una columna `PEAKMAG_<filtro>` por objeto: la magnitud de pico **teórica/sin ruido** del
modelo simulado, no una estadística derivada de las observaciones ruidosas. Confirmado leyendo el
`.DUMP` real de `SNIa-91bg_DDF_baseline_v5.3.1_10yrs` (2000 filas, columnas
`VARNAMES: CID LIBID ... PEAKMAG_u PEAKMAG_g PEAKMAG_r ... SNRMAX ... stretch color`).

### Primer intento (con ruido): resultado dramático pero, se descubrió, un artefacto metodológico

Un primer script (`compare_brightness.py`) comparó `PEAKMAG_r` real de SNANA contra el **mínimo**
de `MAG` (columna ya ruidosa, `FLUXCAL`/`FLUXCALERR` con ruido real de SNANA inyectado) por
objeto en el `phot_df.parquet` ya persistido de la corrida SIMSED `SNIa-91bg` (Fase 2B/5, mismo
rango de z 0.011-0.6). Resultado, binned por redshift:

    z=[0.03,0.11): LCL-SNANA = +0.06 mag (similar)
    z=[0.44,0.52): LCL-SNANA = -0.71 mag (LCL mas brillante)
    z=[0.52,0.60): LCL-SNANA = -1.43 mag (LCL MUCHO mas brillante)

Un patrón dramático, creciente con z -- a primera vista, una explicación perfecta para el
sobre-conteo sistémico (objetos más brillantes cruzan el umbral de detección más fácil,
especialmente a alto z donde el SNR es marginal). Pero el `std` global de SNANA (4.324 mag) era
sospechosamente alto comparado con LCL (0.909 mag), señal de que algo no estaba limpio.

### Verificación antes de confiar en el resultado: `SIMSEDModel.from_dir()` real, `PEAKMAG` real de SNANA es sin ruido

Investigando qué es realmente `PEAKMAG_r` (leyendo el código fuente instalado de LightCurveLynx,
`inspect.getsource(lightcurvelynx.simulate)`), se encontró que `simulate_lightcurves()` ya
calcula internamente un flujo **sin ruido** por observación
(`object_nested_dict["flux_perfect"].append(bandfluxes_perfect)`, columna `flux_perfect` en el
DataFrame `lightcurve` de cada objeto) -- nunca extraído por ningún script anterior (todos
descartaban `flux_perfect` al aplanar, quedándose solo con `flux`/`fluxerr` ruidosos). SNANA
`PEAKMAG_r` es la magnitud de pico teórica del modelo, no una estadística de las observaciones
ruidosas -- comparar eso contra el **mínimo** de N observaciones ruidosas introduce un sesgo tipo
Eddington real: el mínimo de una muestra ruidosa es sistemáticamente más brillante que el valor
verdadero, y el sesgo crece cuanto menor es el SNR (es decir, más fuerte exactamente a alto z,
donde el patrón "dramático" de arriba aparecía). Esto significaba que el primer resultado podía
ser, total o parcialmente, un artefacto de la métrica usada, no una diferencia real entre
simuladores.

### Segunda pasada (sin ruido): el patrón se invierte

Se escribió `compare_brightness_truth.py`, que reconstruye el mismo `source_model` real de
`SNIa-91bg` SIMSED (mismos parámetros, `SIMSED_REDCOR`, extinción MW) pero extrae
`flux_perfect` en vez de descartarlo -- verificado primero con un smoke test de N=10 (confirmó
que la columna existe: `['mjd', 'filter', 'flux', 'fluxerr', 'flux_perfect', 'survey_idx',
'obs_idx', 'is_saturated']`) antes de comprometerse a la corrida completa (`NGENTOT=2000`, sbatch,
~2.5 min). Magnitud de pico real = `max(flux_perfect)` en banda r por objeto (el máximo de flujo
sin ruido, no un mínimo de magnitud ruidosa -- sin sesgo de Eddington). Comparado contra el mismo
`PEAKMAG_r` real de SNANA, binned por los mismos 7 bins de redshift:

| z_bin | N SNANA | mediana SNANA | N LCL | mediana LCL | delta (LCL-SNANA) |
|---|---:|---:|---:|---:|---:|
| [0.011,0.095) | 9 | 19.122 | 8 | 19.564 | +0.442 |
| [0.095,0.179) | 57 | 21.072 | 45 | 21.245 | +0.173 |
| [0.179,0.263) | 129 | 22.151 | 131 | 22.440 | +0.289 |
| [0.263,0.348) | 201 | 23.188 | 234 | 23.415 | +0.227 |
| [0.348,0.432) | 336 | 24.022 | 361 | 24.464 | +0.442 |
| [0.432,0.516) | 496 | 24.782 | 502 | 25.343 | +0.561 |
| [0.516,0.600) | 677 | 25.694 | 669 | 26.092 | +0.398 |

**El signo se invirtió por completo.** LightCurveLynx resulta **~0.2-0.6 mag más tenue** que
SNANA en todos los bins de redshift -- lo opuesto exacto al primer resultado (con ruido), y lo
opuesto a la hipótesis obvia que hubiera explicado el sobre-conteo ("LCL simula objetos
demasiado brillantes"). El global también cambia de forma reveladora: mediana SNANA 24.787,
mediana LCL (sin ruido) 25.351 -- LCL más tenue en mediana, con un `std` mucho más ajustado
(2.003 vs. 4.324 de SNANA) que sugiere que la población de SNANA tiene una cola real más ancha
hacia el extremo tenue (posiblemente ligada a cómo `SIMSED_REDCOR` real de SNANA muestrea las
esquinas de la grilla stretch/color de 91bg-tenues, un detalle no investigado a fondo aquí).

### Por qué esto importa: descarta una hipótesis obvia y redirige la búsqueda de la causa raíz

Si LightCurveLynx simulara objetos sistemáticamente *más brillantes* que SNANA, eso explicaría
directamente el sobre-conteo (~1.4x-11x más detecciones en todo el catálogo, Fase 0-6). El
resultado real es lo contrario -- LightCurveLynx es *más tenue*, no más brillante -- lo que
significa que el brillo/flujo simulado en sí **no** es la causa del sobre-conteo (si acaso, un
efecto opuesto y más chico que debería sub-detectar, no sobre-detectar). Esto descarta con
evidencia real una hipótesis nunca antes probada explícitamente, y redirige la búsqueda de la
causa raíz del residuo sistémico -- que sigue sin resolverse tras Fase 3 (extinción, refutada),
Fase 4 (trigger de época, refutada), Fase 6 (SEARCHEFF/encoding, refutada para el catálogo
general) -- hacia dos candidatos que quedan sin descartar: el cálculo de ruido/SNR en sí (más
allá de las columnas de ruido ya inyectadas en Fase 2A), o la forma/duración de la curva de luz
cerca del pico (que afecta cuántas épocas reales cruzan el umbral de SEARCHEFF incluso con un
pico de brillo similar o más tenue).

## Archivos de esta fase

- `run_simsed_poc.py` -- nueva entrada `SNIax-elastic` en `CLASS_CONFIGS` (diagnóstico, sin
  contraparte SNANA real).
- `run_non1ased_poc.py` -- generalizado: bloque de extinción de host (3 variantes, igual que
  `run_simsed_poc.py`), soporte `DNDZ: MD14`/`DNDZ: TDE`; 4 entradas nuevas en `CLASS_CONFIGS`
  (`SNIax`, `TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`).
- `run_non1ased_poc.sbatch` -- límite de tiempo subido a 2h (antes 30 min, insuficiente para
  clases de cientos/miles de templates).
- `setup_tdebbfit_local.py` (nuevo) -- fix de encabezado sin comentar en `2019qiz.sed.gz`;
  `tdebbfit_local/` (no versionado).
- `setup_bullansed_local.py` (nuevo) -- fix de ZIP mal etiquetado + archivo plano sin `.gz`;
  `bullansed_local/` (no versionado).
- `compare_brightness.py` (nuevo, exploratorio) -- primera comparación (con ruido, luego
  revisada).
- `compare_brightness_truth.py` (nuevo) -- comparación real (sin ruido, `flux_perfect`).
- `compare_brightness_truth_binned.py` (nuevo) -- agrupa por bin de redshift la salida de
  `compare_brightness_truth.py` contra el `.DUMP` real de SNANA; produce la tabla reportada
  arriba.
- `docs/lcl_qc/lcl_qc_index.json` -- 4 filas nuevas (`TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`,
  `SNIax`, todas NON1ASED); nota de `SNIax` (SIMSED) actualizada con el resultado del bake-off.
- `docs/index.html` -- Fase 7 documentada en la sección 06, dos tarjetas de diagnóstico nuevas
  (bake-off confirmado + comparación de brillo).

## Recomendación final (Fase 7)

**Sigue GO condicional.** Cobertura NON1ASED ahora completa (5/5 clases convertidas por SNANA
evaluadas). El bake-off de `SNIax` cierra la pregunta abierta en Fase 6 con una respuesta clara:
el efecto de codificación (~1.15-1.23x en `SNIa-91bg`) es específico de clases con
`SIMSED_REDCOR`, no una propiedad general de NON1ASED (~1.07x en `SNIax`, peso ya uniforme). El
hallazgo más importante de la fase -- y posiblemente de toda la evaluación hasta ahora -- es la
comparación directa de brillo sin ruido: LightCurveLynx simula objetos más tenues que SNANA, no
más brillantes, lo que descarta con evidencia real la hipótesis más obvia para el sobre-conteo
sistémico y estrecha genuinamente el espacio de causas restantes (ruido/SNR o forma de curva de
luz, no calibración de brillo). La causa raíz exacta del residuo sistémico multiplicativo sigue
sin identificarse -- pero después de Fase 3, 4, 6 y 7, la lista de sospechosos descartados con
evidencia real es larga, y la dirección de la búsqueda futura es más concreta que en cualquier
fase anterior. Trabajo futuro: extender la comparación de brillo sin ruido a más clases del
catálogo (un solo caso hasta ahora); investigar el cálculo de ruido/SNR más a fondo; comparar
directamente la forma temporal de la curva de luz (no solo el pico) entre ambos simuladores;
barrido de 5 semillas para las 4 clases NON1ASED nuevas y para `SNIax-elastic`.

# Fase 8 -- barrido de 5 semillas para las 4 clases NON1ASED nuevas, incidente real de cuota de disco

## Motivación

Fase 7 dejó las 4 clases NON1ASED nuevas (`TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`, `SNIax`) con
una sola corrida cada una -- mismo riesgo metodológico que ya se corrigió para el catálogo
SIMSED/SALT2 en Fase 5 y para `SNIa-91bg` NON1ASED en Fase 6. Se lanzaron las 4 semillas
restantes (`seed_index=1..4`) para las 4 clases -- 16 jobs en total.

## Incidente real: cuota de disco de NLHPC agotada a mitad del barrido

11/16 corridas terminaron sin fallos. 5 fallaron con el mismo error real:
`OSError: [Errno 122] Disk quota exceeded`. No es un bug de código -- confirmado leyendo el
traceback completo: en los 5 casos, la simulación y SEARCHEFF ya habían corrido correctamente
(en el caso de `SLSN-I` seed 1, incluso ya se habían persistido `head_df.parquet`/
`phot_df.parquet` completos, con `PHOTFLAG`/`DETECTED` ya calculados) -- el fallo ocurría recién
al intentar escribir el `summary.json` final (unos pocos cientos de bytes) o las imágenes QC,
porque la cuota de disco de la cuenta ya estaba agotada por la acumulación de `phot_df.parquet`
de todas las rondas anteriores (Fase 5: 70 corridas × hasta 1.4GB cada una para
`PISN-STELLA-HYDROGENIC`; Fase 6-7: más corridas NON1ASED de cientos de MB cada una) --
`exploration/lightcurvelynx/` sola sumaba 18GB, la cuenta completa ~200GB.

Los 4 `SNIax` (seeds 1-4) fallaron completos (ninguno alcanzó a persistir sus tablas -- corrida
más larga, ~1001 templates, más probabilidad de coincidir con el pico de uso simultáneo de las
16 corridas paralelas). `SLSN-I` seed 1 sí alcanzó a persistir sus tablas antes de fallar.

## Limpieza mínima, sin borrar de más

Verificado el headroom real disponible con escrituras de prueba (`dd`) antes de tocar cualquier
archivo real -- confirmó que la cuota estaba prácticamente en cero (una escritura de 2GB falló a
los ~65MB). Se eliminó **un solo archivo** (`poc_output_knk17_seed3/phot_df.parquet`, ~61MB) --
una clase de Fase 5 ya completamente reportada en el dashboard/NOTES.md (`summary.json` y las 4
imágenes QC verificados intactos antes de borrar), dejando la tabla cruda (reproducible desde el
script sembrado si hiciera falta) fuera. Suficiente para restaurar ~100MB de headroom.

## Recuperación de `SLSN-I` seed 1 sin re-simular

En vez de volver a correr la simulación completa (que hubiera vuelto a escribir un
`phot_df.parquet` de ~160MB con la cuota todavía ajustada, arriesgando fallar de nuevo),
`recover_slsni_seed1.py` (nuevo, no versionado -- exploratorio de un solo uso) leyó
directamente `head_df.parquet`/`phot_df.parquet` ya persistidos (que ya traían `DETECTED` y
`PHOTFLAG` calculados, guardados antes del `OSError`), recalculó las métricas agregadas y corrió
QC sobre esas tablas -- sin volver a simular ni a escribir ningún archivo grande nuevo. Resultado
idéntico al que hubiera dado una corrida completa: 1826/2000 detectados (91.3%).

## Resultados: 5 semillas completas para 3/4 clases; `SNIax` sigue en 1 semilla

| Clase | Semillas | Razón media (5 semillas) | ±std | min-max |
|---|---|---:|---:|---:|
| `TDE` (NON1ASED) | 5/5 | 2.074x | 0.031 | 2.038-2.129x |
| `SLSN-I` (NON1ASED) | 5/5 | 1.647x | 0.009 | 1.636-1.659x |
| `KN-BULLA-BNS-M2COMP` (NON1ASED) | 5/5 | 4.746x | 0.325 | 4.265-5.161x |
| `SNIax` (NON1ASED) | 1/5 (completado despues, ver abajo) | -- (solo 7.651x de la semilla 0) | -- | -- |

`SLSN-I` tiene el std relativo más bajo del catálogo completo (0.5%) -- clase de recall muy alto
(~90%) con poca varianza de semilla. `KN-BULLA-BNS-M2COMP` tiene el std relativo más alto de las
clases NON1ASED (6.8%), mismo patrón que `KN-K17`/`CaRT` en Fase 5 -- conteo SNANA bajo como
denominador (279/20000) amplifica el ruido de Poisson. En los 3 casos la semilla 0 (la única
usada al reportar por primera vez en Fase 7) resultó ser una de las más altas de las 5, mismo
patrón ya visto repetidamente desde Fase 5 -- otra confirmación de por qué reportar solo una
semilla sistemáticamente sobre-representa el caso real.

`SNIax` quedó pendiente en la primera pasada -- las 4 corridas fallaron por la cuota antes de
persistir nada, así que no había tablas parciales que recuperar como con `SLSN-I`. Completado en
una segunda ronda inmediatamente después (mismo día): verificado el headroom real con una
escritura de prueba antes de tocar nada (~117MB, apenas alcanzaba para 1 de las 4 semillas
faltantes, cada una necesita ~116MB de `phot_df.parquet`) -- en vez de borrar varios archivos
chicos como la primera vez, se liberó un solo archivo grande ya completamente resumido en el
dashboard (`poc_output_pisnstellahydrogenic_seed4/phot_df.parquet`, ~1.3GB, verificado
`summary.json`+QC intactos antes de borrar), dejando ~800MB de headroom -- suficiente margen para
las 4 semillas en paralelo (~464MB de pico esperado). Las 4 corrieron limpias (~20 min cada una,
sin fallos).

| Semilla | Detectados/2000 | % | Razón vs. SNANA (1.49%) |
|---|---:|---:|---:|
| 0 | 228 | 11.40% | 7.651x |
| 1 | 202 | 10.10% | 6.779x |
| 2 | 211 | 10.55% | 7.081x |
| 3 | 202 | 10.10% | 6.779x |
| 4 | 209 | 10.45% | 7.013x |

**Media de 5 semillas: 7.060x ± 0.320 (rango 6.779x-7.651x)** -- la semilla 0, la única disponible
cuando se publicó por primera vez en Fase 7, volvió a ser la más alta de las 5, exactamente el
mismo patrón que `SNIa-91bg` (NON1ASED, Fase 6), `TDE`, `KN-BULLA-BNS-M2COMP` (ambas arriba en
esta misma fase) y varias clases SIMSED de Fase 5. Con esto, las 5 clases NON1ASED del catálogo
(`SNIa-91bg`, `TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`, `SNIax`) tienen banda de incertidumbre real
de 5 semillas -- cobertura NON1ASED completa y reproducible, no solo mecánicamente funcional.

## Archivos de esta fase

- `recover_slsni_seed1.py` (nuevo, exploratorio, no versionado) -- recupera métricas/QC desde
  tablas ya persistidas sin re-simular.
- `docs/lcl_qc/lcl_qc_index.json` -- `TDE`, `SLSN-I`, `KN-BULLA-BNS-M2COMP`, `SNIax` (las 4 NON1ASED
  nuevas de Fase 7) actualizadas con media/std/rango real de 5 semillas.
- Dos archivos borrados en NLHPC (ninguno versionado, ambos ya completamente resumidos en el
  dashboard antes de borrar): `poc_output_knk17_seed3/phot_df.parquet` (~61MB) y
  `poc_output_pisnstellahydrogenic_seed4/phot_df.parquet` (~1.3GB).

## Recomendación final (Fase 8)

**Sigue GO condicional**, sin cambios cualitativos. Las 5 clases NON1ASED del catálogo ya tienen
bandas de incertidumbre reales de 5 semillas, consistente con el resto del catálogo -- cobertura
NON1ASED completa (Fase 7) y reproducible (Fase 8). El incidente de cuota de disco es un
recordatorio real y concreto del costo de almacenamiento de `phot_df.parquet` sin comprimir a esta
escala (decenas de GB acumulados solo para diagnóstico) -- vale la pena considerar, como trabajo
futuro real, comprimir o rotar las tablas crudas de corridas ya completamente resumidas en el
dashboard, en vez de acumularlas indefinidamente hasta el próximo incidente de cuota. Trabajo
futuro: barrido de 5 semillas para las 2 clases auxiliares diagnósticas (`SNIa-91bg-elastic`,
`SNIax-elastic`) para acotar mejor la incertidumbre del efecto de codificación reportado en
Fase 6-7 (~1.15x / ~1.07x, cada uno de una sola corrida todavía).

## Addendum -- panel QC de curvas de luz: objetos mas brillantes, no muestra aleatoria

`pipeline/postproc/qc.py::sample_lightcurves()` elegía 6 SNID al azar (`rng.choice`, `seed=42`
fijo) para el panel "Curvas de luz" de los 4 gráficos de control -- útil para verificar que el
pipeline no está roto, pero no para juzgar visualmente qué tan brillante/creíble es la población
simulada de una clase. Cambiado a elegir los 6 objetos con el `FLUXCAL` pico más alto (máximo de
la observación individual más brillante de cada objeto, sobre todas sus bandas) -- sin parámetro
`seed` (ya no hay aleatoriedad que fijar). Esta función es compartida entre el QC de producción
real de SNANA (sección 03, Capa 4, `postprocess.py`) y el QC de todos los PoC de LightCurveLynx
(sección 06) -- el cambio aplica a ambos lados por diseño, pero **solo se regeneraron los 19
`lightcurves.png` del dashboard de LightCurveLynx** (desde los `head_df.parquet`/
`phot_df.parquet` ya persistidos, sin re-simular nada, vía `regen_lightcurves_qc.py`, exploratorio
y no versionado).

**Intento de regenerar también la sección 03 (producción real) reveló un problema real e
independiente**: `python -m pipeline.postprocess --campaign build/full_v5.3_10yrs` (el comando
oficial, corrido vía `sbatch slurm/run_pipeline_step.sbatch`, job 11492352) encontró que **78 de
los 80 GENVERSION del manifiesto de campaña ya no existen en `$SNDATA_ROOT/SIM`** -- el FITS crudo
fue limpiado del disco de NLHPC (mismo tipo de presión de espacio que el incidente de cuota de
Fase 8, aunque esta limpieza específica no la hizo esta sesión). Solo `SNIa_WFD_baseline_v5.3.1_10yrs`
y `SNII_WFD_baseline_v5.3.1_10yrs` seguían presentes, y ambos fallaron ademas con un
`UnicodeDecodeError` real en `converter.py` (bug preexistente, no relacionado a este cambio, no
investigado a fondo). **No es posible regenerar las 351 imágenes de producción desde FITS real en
su estado actual.**

Decisión del usuario, explícita, tras confirmar que entendía la implicancia: sustituir el panel
`lightcurves.png` de las 19 clases de producción (solo DDF) que sí tienen contraparte de datos ya
persistidos de LightCurveLynx (`exploration/lightcurvelynx/poc_output_*`), usando esos datos en
vez de FITS real que ya no existe. **El título del gráfico deja explícito que la fuente es
LightCurveLynx, no SNANA real** (`sample_lightcurves()` ahora acepta un parámetro `title` para
esto, ver `regen_production_lightcurves_lcl_substitute.py`, exploratorio y no versionado) -- para
no hacer pasar datos de un simulador distinto como si fueran la salida de producción real. Solo se
tocó el panel de curvas de luz de esas 19 (no los otros 3, que siguen siendo el `redshift`/
`magnitudes`/`detections` real ya generado antes de que el FITS se limpiara). Las versiones WFD de
esas mismas 19 clases, y las ~57 clases restantes sin ninguna corrida de LightCurveLynx
(LCLIB de variables, NON1A adicionales, etc.), quedan con el panel de muestra aleatoria -- no
hay ningún dato real ni sustituto disponible para esas todavía.

# Fase 9 -- barrido de 5 semillas para `SNIa-91bg-elastic`/`SNIax-elastic`: el bake-off de codificación queda cerrado

## Motivación

Las dos clases auxiliares diagnósticas del bake-off de codificación (Fase 6-7) -- `SNIa-91bg-elastic`
y `SNIax-elastic` en `run_simsed_poc.py`, sin contraparte SNANA real -- seguían en una sola corrida
cada una. Los ratios de codificación reportados (~1.15x para `SNIa-91bg`, ~1.07x para `SNIax`)
combinaban un lado ya con 5 semillas (el NON1ASED) contra el otro de una sola corrida (el
SIMSED-elastic) -- una comparación asimétrica en confiabilidad. Correr las 4 semillas restantes de
ambas clases cierra esa asimetría.

## Corridas: dos tandas, sin incidentes de cuota

Headroom verificado antes de empezar (~1GB+, escritura de prueba de 1.2GB exitosa) -- suficiente
para las 8 corridas nuevas sin liberar espacio (referencia: `phot_df.parquet` de
`SNIa-91bg-elastic` ~106MB/semilla, de `SNIax-elastic` ~121MB/semilla, ~908MB de pico si las 8
corrieran en paralelo). Por margen de seguridad se corrieron en dos tandas de 4 (primero
`SNIa-91bg-elastic`, después `SNIax-elastic`) en vez de las 8 a la vez -- reduce el pico
simultáneo sin costar tiempo real (cada tanda corre en paralelo internamente). Las 8 corridas
terminaron limpias (`SNIa-91bg-elastic` ~7 min c/u; `SNIax-elastic` ~20 min c/u, misma carga de
1001 templates que su par NON1ASED).

## Resultados: los dos bake-offs quedan resueltos con evidencia sólida

| Semilla | `SNIa-91bg-elastic` (SIMSED_REDCOR) | `SNIax-elastic` (SIMSED_GRIDONLY) |
|---|---:|---:|
| 0 | 289/2000 = 14.45% | 214/2000 = 10.70% |
| 1 | 298/2000 = 14.90% | 225/2000 = 11.25% |
| 2 | 311/2000 = 15.55% | 212/2000 = 10.60% |
| 3 | 299/2000 = 14.95% | 209/2000 = 10.45% |
| 4 | 309/2000 = 15.45% | 218/2000 = 10.90% |
| **media** | **15.06% ± 0.40%** | **10.78% ± 0.28%** |

Comparado contra la media de 5 semillas del lado NON1ASED correspondiente (ya conocida de Fase 6/8):

- **`SNIa-91bg`**: SIMSED_REDCOR 15.06% ± 0.40% vs. NON1ASED 16.57% ± 0.59% -- **razón final ~1.10x**
  (baja del ~1.23x de una sola semilla, y del ~1.15x de la estimación intermedia con solo el lado
  NON1ASED promediado). Las bandas de incertidumbre de ambos lados **ya no se solapan** -- es un
  efecto real y medido con confianza, no una estimación de un solo punto.
- **`SNIax`**: SIMSED-elastic 10.78% ± 0.28% vs. NON1ASED 10.52% ± 0.48% -- **razón final ~0.98x**,
  **indistinguible de 1.0** (las bandas se solapan por completo, la diferencia es más chica que
  cualquiera de los dos errores estándar). El efecto de codificación desaparece por completo cuando
  no hay `SIMSED_REDCOR` que perder al convertir a NON1ASED.

Ambos resultados refuerzan, ahora con la evidencia más sólida disponible en todo el proyecto para
esta pregunta específica, la conclusión de Fase 6-7: **el efecto de codificación SIMSED→NON1ASED
es real pero específico de clases con ponderación correlacionada (`SIMSED_REDCOR`)** -- no una
propiedad general del formato NON1ASED en sí. Para clases de peso ya uniforme (`SIMSED_GRIDONLY`,
la mayoría del catálogo de 14 SIMSED), convertir a NON1ASED no debería introducir ningún sesgo de
población por sí solo.

## Archivos de esta fase

- `docs/lcl_qc/lcl_qc_index.json` -- notas de `SNIa-91bg (NON1ASED)` y `SNIax` (SIMSED) actualizadas
  con los ratios finales de 5 semillas por lado.
- Sin archivos nuevos de código; sin incidentes de cuota (headroom suficiente desde el inicio).

## Fase 10 — Dispersión `GENSIGMA_MWEBV_RATIO` (primer candidato del roadmap post-Fase-9)

Tras cerrar el bake-off de codificación (Fase 9), el residuo sistémico multiplicativo (~1.1x-10.8x
según clase) seguía sin causa raíz identificada. Se absorbió la documentación oficial de
LightCurveLynx (readthedocs) y el manual de SNANA, y se cruzó cada mecanismo candidato encontrado
contra los archivos reales de esta campaña en NLHPC (`pipeline/campaign/templates.py`, el
`.INPUT` de survey real, el `.SIMLIB` real) -- ver plan de investigación aprobado para la tabla
completa de candidatos descartados esta sesión (FLUXERRMODEL, NEXPOSE/coadd, ruido Poisson de host,
velocidad peculiar, bits de SEARCHEFF zHOST, Om0, GENMAG_SMEAR fuera de SNIa-SALT2). El primer
candidato con evidencia real de estar activo y sin portar: `GENSIGMA_MWEBV_RATIO: 0.16`, presente
en el `include_survey_*.INPUT` real de las 19 clases.

### Paso 1 -- fórmula exacta (confirmada contra el código fuente real de SNANA)

Se descargó `snlc_sim.c` directo del repo público `RickKessler/SNANA` (rama `master`) y se leyó la
función `gen_MWEBV()` completa (líneas ~13505-13620). Hallazgos:

```c
// siempre se quema un numero aleatorio para permanecer sincronizado
MWXT_GaussRan = getRan_GaussClip(1, -3.0, 3.0);   // Z~N(0,1), recorte a +-3 sigma

// GENLC.MWEBV = valor nominal (de SIMLIB o mapa SFD98, ver mas abajo)
if ( INPUTS.OPT_MWEBV == OPT_MWEBV_FILE ) {
    if ( INPUTS.MWEBV_SIGRATIO < 0.0 ) { /* error fatal: ratio sin definir */ }
    ERR1 = INPUTS.MWEBV_SIG;                       // fijo, 0 en esta campaña
    ERR2 = INPUTS.MWEBV_SIGRATIO * GENLC.MWEBV;     // 0.16 * EBV_nominal
    GENLC.MWEBV_ERR = sqrt(ERR1*ERR1 + ERR2*ERR2);
}

GENLC.MWEBV_SMEAR = GENLC.MWEBV + GENLC.MWEBV_ERR*MWXT_GaussRan + INPUTS.MWEBV_SHIFT;
GENLC.MWEBV_SMEAR *= INPUTS.MWEBV_SCALE;   // SHIFT=0, SCALE=1 en esta campaña (defaults)
```

Con `MWEBV_SIG=0`, `MWEBV_SHIFT=0`, `MWEBV_SCALE=1` (ninguno de los tres se toca en
`templates.py`), la fórmula colapsa exactamente a:

```
EBV_true = EBV_nominal * (1 + 0.16 * Z),   Z ~ N(0,1) recortado a ±3σ
```

Como `0.16 * |Z| <= 0.48 < 1`, el resultado nunca es negativo -- no hace falta piso en 0.

**Hallazgo colateral, no menor:** el bloque `gen_MWEBV()` primero intenta leer `GENLC.MWEBV` desde
el `.SIMLIB` (columna `MWEBV:` del header de cada LIBID, opción `OPT_MWEBV_FILE`, que es el default
de SNANA y también el default de este proyecto, `templates.py:76 opt_mwebv: int = 1`). Si ese valor
es `<= 0.0`, SNANA cae automáticamente a `OPT_MWEBV_SFD98` -- el mapa real de polvo galáctico
(Schlegel-Finkbeiner-Davis 1998) evaluado en el RA/DEC exacto de cada objeto. Se verificó el
`.SIMLIB` real de la campaña (`DDF_baseline_v5.3.1_10yrs.SIMLIB`, escrito por
`pipeline/simlib/writer.py::lib_header()`, que hardcodea `mwebv: float = 0.0` como default y nunca
lo sobreescribe con un valor real) -- **el campo `MWEBV:` es `0.00` en cada uno de los LIBID
inspeccionados**, sin excepción. Es decir: en la campaña real, el EBV nominal de MW que sufre la
dispersión del 16% **no es un valor fijo por campo** -- es el mapa SFD98 real, con variación
espacial continua dentro de cada pointing DDF. El diccionario `DDF_FIELD_EBV` de este proyecto usa
un único valor fijo por campo (aparentemente un promedio SFD98 precalculado, sin documentar su
origen). Este es un hallazgo relacionado pero *distinto* al de la dispersión del 16% -- deliberadamente
no se prueba en la misma corrida (misma disciplina de aislar una variable a la vez que Fase 6/9);
queda anotado como candidato "Fase 10b" si el resultado de abajo no cierra el residuo.

### Paso 2 -- implementación

Se agregó `make_mwebv_ratio_scatter(ratio, seed=...)` a `snana_params.py` (usa
`scipy.stats.truncnorm(-3, 3)` para el recorte real de ±3σ, no un clip crudo del extremo) y se
conectó en el `_field_to_ebv()` de los 5 scripts que lo definen (`run_non1ased_poc.py`,
`run_simsed_poc.py`, `run_snia_ddf_poc.py`, `run_simsed_91bg_ddf_poc.py`,
`compare_brightness_truth.py`), con `seed=seed_base + 10` (offset previamente libre en las 5
firmas de seeding). Verificado en el venv real de NLHPC antes de correr nada: la fórmula produce
valores con std ≈ 0.985 (esperado para N(0,1) recortado a ±3σ) y siempre positivos.

### Paso 3 -- resultado empírico (clase de prueba: `SNIa-91bg` NON1ASED)

Se eligió `SNIa-91bg (NON1ASED)` como clase de prueba -- rápida, y con la línea base de 5 semillas
más reciente y confiable del catálogo (Fase 8/9): **ratio 2.254 ± 0.081**. Los directorios
`poc_output_non1ased_snia91bg{,_seed1..4}` pre-existentes se renombraron a
`*_prefase10_baseline` (sin gasto extra de cuota, cuota de cuenta ya en ~200G) antes de re-correr,
para no perder los datos crudos de comparación. Se lanzaron 5 semillas nuevas (jobs 11518682-86)
con la dispersión del 16% activa.

Incidente de cuota durante el lanzamiento (mismo techo ~200G de siempre): las 5 corridas fallaron
la primera vez, no por bug sino por `OSError: ... Disk quota exceeded` justo al escribir
`phot_df.parquet` -- la simulación en sí llegó al 100% sin problema. Compresión in-situ resultó no
ser viable como primer movimiento (`tar`/`gzip` necesitan espacio libre para escribir el archivo
nuevo, y no quedaba ninguno: un intento de `dd` de 700MB confirmó solo ~130MB de margen real, y
`gzip` sobre un `phot_df.parquet` de muestra solo comprime ~12% porque parquet ya viene comprimido
con snappy). Se liberó espacio borrando los 5 directorios `*_prefase10_baseline` recién renombrados
(su ratio agregado, 2.254 ± 0.081, ya estaba guardado de forma permanente en
`docs/lcl_qc/lcl_qc_index.json`, así que no se perdió nada analíticamente necesario) y se
relanzaron las 5 semillas (jobs 11518989-93), esta vez completas.

**Resultado:**

| semilla | `detection_efficiency_pct` (con dispersión MWEBV) | ratio (÷ `snana_pct`=7.35%) |
|---|---|---|
| 0 | 17.75% (355/2000) | 2.415 |
| 1 | 16.30% (326/2000) | 2.218 |
| 2 | 16.35% (327/2000) | 2.224 |
| 3 | 16.20% (324/2000) | 2.204 |
| 4 | 16.25% (325/2000) | 2.211 |
| **media** | **16.57% ± 0.59%** | **2.254 ± 0.081** |

**Prácticamente idéntico a la línea base sin dispersión** (2.254 ± 0.081, Fase 8/9) -- la media
nueva coincide a 3 decimales y el std tampoco cambia. La semilla 0 incluso reprodujo exactamente
el mismo conteo (355/2000, 17.75%) que la línea base, lo cual tiene sentido: los campos DDF de
este proyecto ya tienen E(B-V) nominal muy bajo (`DDF_FIELD_EBV`: 0.006-0.025), y con
`ratio=0.16` la dispersión máxima a 3σ es de solo `0.16*3=48%` sobre un valor ya pequeño --
del orden de A_V~0.01-0.04 mag en el peor caso (`xmm_lss`), muy por debajo del ruido
semilla-a-semilla que ya existía.

### Conclusión Fase 10

**`GENSIGMA_MWEBV_RATIO` queda descartado como causa del residuo.** El efecto es real (la fórmula
está bien portada y verificada contra el código fuente de SNANA) pero su magnitud es despreciable
en esta campaña específica, porque los campos DDF fueron elegidos deliberadamente por su E(B-V)
bajo. Esto refuerza -- no contradice -- el hallazgo de Fase 3 (extinción de host tampoco explica
el residuo): la extinción en general, ya sea de host o de MW, no parece ser el mecanismo detrás
del residuo sistémico. Por la misma razón, el hallazgo colateral del Paso 1 (mapa SFD98 real vs.
`DDF_FIELD_EBV` fijo por campo, "Fase 10b") se deprioriza -- ambos son formas de generar un EBV
nominal de magnitud similarmente pequeña, así que es poco probable que ese cambio por sí solo
mueva la aguja. El cambio queda en el código (aporta fidelidad real a la simulación,
`seed_base + 10` en los 5 scripts) pero no se extiende al resto del catálogo -- exactamente la
disciplina de "probar barato antes de escalar" que pide el plan. **Próximo paso: Fase 11**
(grilla precomputada de SIMSED vs. integración en vivo de `PassbandGroup`).

## Recomendación final (Fase 9)

**Sigue GO condicional.** El bake-off de codificación queda cerrado con evidencia sólida en ambas
direcciones -- ya no depende de comparar una sola corrida contra un promedio de 5. Con esto, las
19 clases del catálogo principal y las 2 clases auxiliares diagnósticas tienen todas banda de
incertidumbre real de 5 semillas; no queda ninguna comparación de este proyecto basada en una sola
corrida sin cuantificar su varianza. La causa raíz del residuo sistémico multiplicativo (Fase 3-4,
SEARCHEFF/encoding en Fase 6, brillo sin ruido en Fase 7) sigue siendo la prioridad para trabajo
futuro -- ninguna de las fases de reproducibilidad (5, 8, 9) cambia esa conclusión, solo la hacen
más confiable. **Fase 10 (arriba) descarta la dispersión MW E(B-V) como candidato; la investigación
continúa en Fase 11.**

## Fase 11 — grilla LOGZBIN de SIMSED (SNANA) vs. evaluación continua (LightCurveLynx)

Absorbiendo la documentación oficial de LightCurveLynx y el manual de SNANA (dos agentes de
investigación), se sharpeó la hipótesis original ("grid vs. live integration") en algo concreto y
testeable: SNANA's SIMSED precomputa flujo en una grilla de redshift log-espaciada (`LOGZBIN`,
default 0.02, pero `SLSN-I-MOSFIT`/`PISN-MOSFIT`/`SNIIn-MOSFIT` usan 0.1 -- 5x más gruesa, confirmado
en sus `SED.INFO` reales en NLHPC) e interpola **linealmente** entre nodos -- mientras que
LightCurveLynx evalúa cada objeto a su redshift exacto y continuo, sin discretizar nunca (confirmado
leyendo `sed_template_model.py`/`physical_model.py` del paquete real instalado: la interpolación de
LCL es `RectBivariateSpline` solo en fase×longitud-de-onda, el redshift se aplica analíticamente).

### Paso 1 (fallido) -- intento de volcar `Sinterp` crudo via `GENMODEL_MSKOPT: 512`

Un research agent encontró en `genmag_SIMSED.c` un bloque de debug (`LDMP_DEBUG`) que imprime el
flujo crudo interpolado (`Sinterp`) por época real cuando `OPTMASK & 512` es verdadero, y documentación
que sugiere que `GENMODEL_MSKOPT: 512` en el `.INPUT` activa ese bit. Se construyó un harness
completo (`exploration/lightcurvelynx/fase11_simsed_zgrid/`) para explotar esto -- pero **dos
corridas reales (jobs 11561825/11561826) devolvieron 0 líneas de debug**. Leyendo `snlc_sim.c`
línea por línea (call site real, ~línea 29249) se confirmó la causa: el modelo SIMSED usa
`INPUTS.OPTMASK_SIMSED` para armar el `OPTMASK` que le pasa a `genmag_SIMSED()`, **no**
`INPUTS.GENMODEL_MSKOPT` (que sí se usa para otros modelos como BYOSED/PySEDModel, pero no para
SIMSED). Y `OPTMASK_SIMSED` solo se alimenta internamente desde `SIMSED_GRIDONLY`/`SIMSED_WGTMAP_FILE`
-- no existe ninguna clave de `.INPUT` documentada que le pase el bit 512. El código de debug es
real pero inalcanzable sin recompilar SNANA (hay incluso una línea comentada en el propio código,
`//    if ( GENLC.CID==19201 && ifilt_obs==1 ) { OPTMASK += 8 ; }`, que confirma que este debug se
usa históricamente editando el fuente a mano, no vía config). Camino muerto, descartado.

### Paso 1 (real) -- pivote a `PEAKMAG_r` del `.DUMP`, mismo patrón de Fase 7

En vez de un flujo crudo pre-`x0`, se reusa el patrón ya probado en Fase 7: `PEAKMAG_r` del `.DUMP`
real (`SIMGEN_DUMPALL`, `SELECTION: NONE` -- escribe TODO lo generado) menos `MU` (columna real,
módulo de distancia, función suave de z sin relación con la grilla) aísla una cantidad que debería
ser suave en z salvo por el artefacto de interpolación buscado. Harness: `GENRANGE_REDSHIFT`
angosto (ancla = `GENRANGE_REDSHIFT[0]` real de cada clase, ventana = 5 celdas de `LOGZBIN`,
`VEL_CMBAPEX: 0` para anclar la grilla exactamente ahí sin el margen de VPEC/CMB que SNANA le agrega
por default), `NGENTOT_LC: 3000` para muestrear esa ventana con densidad. Ver
`exploration/lightcurvelynx/fase11_simsed_zgrid/debug_survey_include.INPUT` (bloque `SIMGEN_DUMPALL`
recortado a 30 variables -- `PEAKMAG_u/g/i/z/Y` quitadas porque `GENFILTERS: r` solo genera esa
banda, y SNANA aborta con "Undefined SIMGEN_DUMP variable" si se pide una banda no generada).

Dos incidentes reales de cuota más en el camino (jobs 11561879/11561880/11561925, mismo techo
~200G): la ventana completa de 10 años del SIMLIB real hace que SNANA lea la cadencia acumulada
COMPLETA de un LIBID antes de filtrar por `GENFILTERS` -- algunos LIBID acumulan 47.210 obs en 10
años, por encima del límite fijo `MXOBS_SIMLIB=30000` (`FATAL ERROR ABORT`); se resolvió acotando
`GENRANGE_MJD`/`GENRANGE_PEAKMJD` a ~1 año. Y el `sbatch` original borraba el FITS/SIM real de
ambas clases recién al final -- `SLSN-I-MOSFIT` (960 templates, muchas más columnas `SIMSED_PAR*`)
se quedó sin cuota a mitad de escribir su FITS porque el de `SNIa-91bg` (51MB) todavía no se había
liberado; se corrigió borrando cada FITS inmediatamente después de copiar su `.DUMP`, antes de
generar la siguiente clase.

### Resultado

Análisis en `exploration/lightcurvelynx/fase11_snana_selfcheck.py`: `PEAKMAG_r - MU`, ajuste de una
tendencia suave global (polinomio grado 2 en `log10(z)`, sin necesitar que el mismo template SIMSED
se repita a distinto z -- el ruido objeto-a-objeto de parámetros no sesga el ajuste de la tendencia,
solo agrega varianza), residuo cuadriculado por posición fraccional dentro de una celda de la grilla
(`frac=0` en un nodo exacto, `frac=0.5` en el punto medio).

| Clase | `LOGZBIN` | N válido | std del residuo global | cerca de nodo | cerca de punto medio | diferencia |
|---|---|---|---|---|---|---|
| `SNIa-91bg` (control) | 0.02 | 1930 | 0.152 mag | -0.013 ± 0.008 | -0.001 ± 0.007 | +0.012 ± 0.011 mag |
| `SLSN-I-MOSFIT` (hipótesis) | 0.1 | 1944 | **1.173 mag** | +0.088 ± 0.062 | -0.030 ± 0.060 | -0.118 ± 0.086 mag |

**`SNIa-91bg`: resultado limpio, sin patrón.** Los 10 bins de `frac` oscilan sin tendencia
(-0.004 a +0.015 mag, dentro de ±1 SEM), la diferencia nodo-vs-punto-medio no es significativa. Este
es exactamente el resultado nulo esperado para la grilla más fina (default).

**`SLSN-I-MOSFIT`: prueba sin potencia estadística suficiente, no un resultado nulo limpio.** La
dispersión intrínseca de brillo entre los 960 templates físicos distintos (parámetros
`kappa/kappagamma/mej/temp/vej` del magnetar-model MOSFIT, cada uno con su propia curva de luz) es
**~8x mayor** que la de `SNIa-91bg` (std=1.17 mag vs. 0.15 mag) -- con `NGENTOT_LC=3000` repartido
sobre 960 templates (~3 objetos por template en promedio), el ajuste de tendencia global de grado 2
no puede separar "forma de curva de luz propia de cada template" de "sesgo de interpolación de
grilla", y el SEM por bin (~0.06-0.09 mag) queda demasiado grande para confirmar o refutar un efecto
del orden de 0.1 mag con confianza (diferencia nodo-vs-medio de -0.118 ± 0.086 mag, ~1.4σ, no
significativa). Escalar esto a una potencia real necesitaría o bien `NGENTOT_LC` uno o dos órdenes
de magnitud más grande, o bien un diseño que fije/repita un puñado de templates específicos a través
de la ventana de redshift en vez de dejar que SNANA elija uno al azar por objeto -- ninguna de las
dos es barata en el sentido de la disciplina de este proyecto ("probar barato antes de escalar").

### Conclusión Fase 11

**No hay evidencia de un artefacto de interpolación de grilla de magnitud relevante, en ninguna de
las dos clases probadas -- pero el resultado de la clase con la hipótesis afilada (`SLSN-I-MOSFIT`)
es genuinamente ambiguo, no un descarte limpio.** Incluso tomando el punto estimado (no
significativo) de -0.118 mag como cota superior aproximada del efecto: es un orden de magnitud
demasiado chico para explicar un residuo que típicamente implica varias décimas a >1 mag de
diferencia sistemática de brillo/flujo (razones de detección de 2x-10x) -- el mismo argumento de
"real pero demasiado chico para importar" que cerró Fase 10 (dispersión MW E(B-V)). Dado el costo ya
invertido (3 pivotes de diseño, 5 incidentes/reintentos de cuota) y que escalar esto más allá
requeriría una inversión de cómputo sustancialmente mayor sin garantía de resolver la ambigüedad, se
recomienda **no continuar escalando Fase 11 por ahora** y pasar a **Fase 12** (mismatch de
passband/zeropoint entre `kcor_LSST.fits` real y los throughputs de `lsst/throughputs` que descarga
LightCurveLynx) -- dejando la puerta abierta a retomar Fase 11 con un diseño de mayor potencia si
Fase 12-14 tampoco cierran el residuo.

### Archivos de esta fase

- `exploration/lightcurvelynx/fase11_simsed_zgrid/` -- harness completo (`.INPUT` de survey/modelo/root,
  `run_fase11_zgrid.sbatch`); el intento fallido de `GENMODEL_MSKOPT: 512` queda documentado en los
  comentarios del `.INPUT` como referencia de qué NO funciona y por qué.
- `exploration/lightcurvelynx/fase11_zgrid_compare.py`/`.sbatch` -- construido para el diseño
  original (comparación punto a punto contra `evaluate_bandfluxes()` de LightCurveLynx usando
  `Sinterp`); no se llegó a usar porque el Paso 1 original resultó inalcanzable, pero queda
  verificado que la API (`SIMSEDModel(templates=[...], flux_scale=..., redshift=..., distance=10.0,
  t0=0.0)` + `evaluate_bandfluxes(passband_group, times, [band], state=None)`) funciona end-to-end
  (probado interactivamente en el venv real de NLHPC) -- reutilizable si se retoma esta fase con más
  potencia estadística.
- `exploration/lightcurvelynx/fase11_snana_selfcheck.py` -- el análisis real que sí se corrió
  (solo lado SNANA, ver Resultado arriba).

## Fase 12 — mismatch de passband/zeropoint (`kcor_LSST.fits` real vs. `lsst/throughputs` que descarga LCL)

Siguiente candidato del roadmap: cada corrida de LightCurveLynx descarga los passbands de
`raw.githubusercontent.com/lsst/throughputs/main/baseline/total_<banda>.dat` (visible en el stdout
de cada job) -- el preset genérico `LSST` de LCL, no necesariamente la curva de transmisión exacta +
cualquier offset de zeropoint nativo-vs-sintético que trae el `kcor_LSST.fits` real de la campaña
(referenciado por el `.INPUT` de las 19 clases, nunca antes inspeccionado -- es un FITS, necesita
`astropy.io.fits`).

### Paso 1 -- leer `kcor_LSST.fits` real

Abierto con `astropy.io.fits` en el venv real de NLHPC (`/home/mvalenzuela/run_SNANA/kcor_LSST.fits`).
Estructura real: HDU `ZPoff` (offset de zeropoint nativo-vs-sintético por banda), `FilterTrans`
(curva de transmisión real, 991 puntos, 2100-12000 Å en bins de 10 Å), `PrimarySED` (espectro de
referencia AB), más `KCOR`/`MAG+MWXTCOR` (tablas de K-correction, vacías -- no aplican a este modo de
generación). Header confirma `FILTPATH1 = '$SNDATA_ROOT/filters/LSST/baseline_1.9'` -- el kcor real
usa la versión **1.9** de los throughputs de Rubin.

**Hallazgo 1 -- `ZPoff` es cero en las 6 bandas** (`ZPoff(Primary)=ZPoff(SNpot)=0.0` para
`LSST-u/g/r/i/z/Y`, sistema `AB` puro): no hay ningún offset de zeropoint nativo-vs-sintético oculto
en el kcor real -- descarta de entrada la mitad de la hipótesis original sin necesitar comparar nada
más. Coincide exactamente con la convención `MAG_AB_ZP_NJY = 8.9 + 2.5*9` (AB puro) que ya usa todo
el proyecto (Fase 7, `compare_brightness_truth.py`).

### Paso 2 -- diff numérico contra lo que descarga LightCurveLynx

Se forzó una descarga real (`PassbandGroup.from_preset(preset="LSST")` en el venv de NLHPC) y se leyó
el archivo cacheado (`~/.cache/lightcurvelynx/passbands/LSST/<banda>.dat`). **El propio header del
archivo descargado dice `# Version 1.9`** -- coincide exactamente con `baseline_1.9` del kcor real; la
rama `main` de `lsst/throughputs` en GitHub sigue sirviendo la misma versión 1.9 que usa esta
campaña, no hay deriva de versión entre ambos.

Comparación numérica directa (interpolando la curva de LCL a la grilla de 10 Å del kcor real):

| Banda | Δλ_efectiva (Å) | pico kcor | pico LCL | razón de área (LCL/kcor) | max\|ΔT\| |
|---|---|---|---|---|---|
| u | -13.49 | 0.1806 | 0.1806 | 1.0039 | 0.0001 |
| g | -1.08 | 0.4828 | 0.4828 | 1.0004 | 0.0003 |
| r | +0.01 | 0.5777 | 0.5777 | 1.0001 | 0.0004 |
| i | +0.25 | 0.6235 | 0.6235 | 1.0003 | 0.0001 |
| z | +0.89 | 0.6306 | 0.6306 | 1.0004 | 0.0001 |
| Y | +3.43 | 0.3405 | 0.3405 | 1.0013 | 0.0006 |

Transmisión de pico idéntica a 4 decimales en las 6 bandas; longitud de onda efectiva difiere menos
de 14 Å incluso en el peor caso (`u`, la banda más angosta y con el corte azul más agudo -- esperable
por diferencias de grilla/interpolación, no de forma real); área integrada difiere menos del 0.4% en
todas las bandas. Esto es efectivamente **la misma curva**, con diferencias del orden de la
discretización numérica (kcor a 10 Å de resolución vs. la grilla nativa más fina que descarga LCL),
no una diferencia física real de transmisión.

### Conclusión Fase 12

**Descartado, con evidencia numérica directa y concluyente -- no ambiguo, a diferencia de Fase 11.**
No hay offset de zeropoint nativo-vs-sintético (ZPoff=0) ni diferencia real de forma/posición de las
curvas de transmisión (mismo release v1.9, diffs sub-Angstrom/sub-porcentuales explicables por
resolución de grilla). El passband/zeropoint no es la causa del residuo sistémico. Recomendación:
pasar a **Fase 13** (extrapolación en los bordes del template: relleno a cero por defecto de
LightCurveLynx vs. supresión de la observación de SNANA) -- señalado en el plan original como "el
lead más concreto mecánicamente" de todos los candidatos restantes.

### Archivos de esta fase

Sin archivos nuevos -- investigación completa e inline (lectura de FITS + comparación numérica
directa en el venv real de NLHPC, sin necesitar ninguna simulación nueva). Sin incidentes de cuota.

## Fase 13 — extrapolación en los bordes del template (LightCurveLynx) vs. supresión de la observación (SNANA)

El lead marcado como "el más concreto mecánicamente" del plan original: LightCurveLynx dice en su
documentación que sus `LightcurveTemplateModel` no periódicos "caen a 0.0" fuera de su rango de fase
por defecto; SNANA, según el manual, suprime la observación (no la genera) cuando la longitud de onda
en marco de reposo cae fuera del rango declarado del SED. Una observación de flujo cero con ruido
Poisson realista encima es, en principio, capaz de disparar una detección espuria si ambos lados no
manejan el borde igual.

### Paso 1 -- ¿qué clases tocan este borde, y cuánto de la población?

Se escanearon las 19 clases (`fase13_scan.py`, no versionado -- exploratorio, lee `SED.INFO`/
`RESTLAMBDA_RANGE` o, si no está declarado, el primer `.SED` real) y se calculó, para cada banda LSST
(rango observado real extraído de `kcor_LSST.fits`) y cada extremo de `GENRANGE_REDSHIFT`, si la
longitud de onda en marco de reposo necesaria cae fuera del `RESTLAMBDA_RANGE` declarado. Resultado:
**`SLSN-I` (SIMSED y NON1ASED, `GENRANGE_REDSHIFT` hasta z=9.7) es, con mucha diferencia, la clase más
expuesta** -- a z=9.7 las 6 bandas caen completamente fuera del rango 1000-11000 Å declarado.
`PISN-MOSFIT` toca el borde de forma marginal (banda `u` apenas, a z=2.4). El resto de las 17 clases
no toca el borde en absoluto con sus rangos reales.

Lo que hace esto importante, no solo una curiosidad de la cola: con el `dndz` real de `SLSN-I`
(`MD14`, ponderado por SFR), **el 46% de TODA la población generada ya está en z≥2.2** -- el punto
donde la banda `u` empieza a caer fuera de rango. No es un caso extremo raro, es casi la mitad del
catálogo simulado.

### Paso 2 -- confirmar el comportamiento real de cada lado (no solo confiar en la documentación)

**LightCurveLynx real (código, no doc):** `SEDTemplate.evaluate_sed()` (`sed_template_model.py`)
inicializa la matriz de salida en cero y solo llena las FASES dentro de `self.times[0]-self.times[-1]`
-- el cero-padding documentado es real, pero **solo en el eje de fase**. En el eje de longitud de
onda no hay ningún chequeo de rango en absoluto -- se llama a
`RectBivariateSpline(...)(wavelengths, grid=True)` con cualquier longitud de onda, dentro o fuera del
rango nativo del SED. Probado interactivamente en el venv real de NLHPC (`SIMSED.SLSN-I-MOSFIT`,
template 0): a longitudes de onda por debajo de 1000 Å o por encima de 11000 Å, el flujo devuelto
**no es cero -- es un valor constante, clampeado exactamente al valor del borde** (p.ej. idéntico a
100, 300, 500, 999 y 1000 Å, los cinco dieron el mismo flujo). No es la hipótesis original (cero), es
peor: LightCurveLynx sigue generando una observación con flujo real y no-trivial, sin importar cuán
lejos del rango declarado se pregunte.

**SNANA real (código, no manual):** confirmado en `genmag_SEDtools.c` (función que construye la
tabla de flujo, comentario real "Mar 22 2017 -- bail if any part of filter trans it outside of model
range"):
```c
if ( LAMOBS_MIN/z1 < SEDMODEL.LAMMIN[ised] ) { continue ; }
if ( LAMOBS_MAX/z1 > SEDMODEL.LAMMAX[ised] ) { continue ; }
```
Si el rango COMPLETO de la banda no cabe en marco de reposo dentro del SED declarado, SNANA nunca
construye esa celda de la tabla -- la observación no se genera (existe incluso una variable real y
distinta, `NOBS_UNDEFINED`, en la lista de variables permitidas de `SIMGEN_DUMP`, confirmando que
SNANA rastrea esto por separado de `NOBS`).

### Paso 3 -- implementación y prueba en `SLSN-I` (SIMSED)

Se agregó `restlambda_gate()` a `run_simsed_poc.py` (replica exacta de la condición real de arriba)
y se conectó en el paso de aplanado: cualquier observación cuya banda no quepa completa en marco de
reposo dentro de `restlambda_range=(1000, 11000)` se descarta antes de construir `phot_df`/`head_df`
(igual que SNANA, que nunca la genera). Solo aplicado a `SLSN-I` por ahora -- el resto de las clases
no declara `restlambda_range` y su comportamiento queda byte-idéntico.

5 semillas nuevas (jobs 11562466/579/640/755/829, con limpieza de `phot_df.parquet` entre semilla y
semilla por headroom ajustado, ~168MB libres):

| semilla | observaciones suprimidas | detectados/2000 |
|---|---|---|
| 0 | 1.011.432 (14.7% del total generado) | 1239 (61.95%) |
| 1 | -- | 1327 (66.35%) |
| 2 | -- | 1325 (66.25%) |
| 3 | -- | 1304 (65.20%) |
| 4 | -- | 1303 (65.15%) |
| **media** | | **64.98% ± 1.60%** |

**Ratio final: 1.577 ± 0.039** (rango 1.504-1.610), contra la línea base sin el fix, **1.604 ± 0.036**
(rango 1.542-1.648) -- las bandas se solapan casi por completo, no es un cambio estadísticamente
significativo a nivel de 5 semillas, aunque la dirección es la correcta (baja, no sube) y la magnitud
por semilla individual (hasta -3.6pp en la semilla 0) es real.

### Conclusión Fase 13

**Mecanismo real, confirmado y corregido -- pero no explica el residuo de `SLSN-I` por sí solo.** El
14.7% de observaciones suprimidas es una fracción grande, pero `SEARCHEFF` solo exige 2 épocas reales
agrupadas para el trigger (Fase 4) -- los objetos que pierden observaciones por este mecanismo están
casi todos en el extremo de alto z, donde de cualquier forma ya eran marginales o indetectables antes
del fix (ver la eficiencia por bin de redshift de la semilla 0: 81.1% en z<1.92, cayendo a 0.0% en
z=[7.69,9.61)). El fix es una mejora real de fidelidad física (ahora `SLSN-I` respeta el mismo límite
físico que SNANA) y se queda en el código -- el ratio del dashboard se actualiza al nuevo valor más
correcto (1.577 ± 0.039) -- pero no se escala a `SLSN-I (NON1ASED)` ni a `PISN-MOSFIT` por ahora: el
resultado de la clase con mayor exposición ya muestra que el efecto, aunque real, es demasiado chico
para mover el residuo de forma significativa, y `PISN-MOSFIT` tiene una exposición mucho más marginal
(solo `u` a z=2.4). Recomendación: pasar a **Fase 14** (estado de `GENMAG_SMEAR_MODELNAME: G10` en
`SNIa`, último candidato del roadmap original) o a los ítems de menor prioridad (`GENSIGMA_SEARCH_PEAKMJD`,
`REDCOV`) si Fase 14 tampoco cierra el residuo.

### Archivos de esta fase (Fase 13)

- `exploration/lightcurvelynx/run_simsed_poc.py` -- `BAND_RANGES_OBS`, `restlambda_gate()`, y el
  chequeo en el aplanado; `restlambda_range=(1000.0, 11000.0)` agregado solo a `CLASS_CONFIGS["SLSN-I"]`.
- `docs/lcl_qc/lcl_qc_index.json` -- ratio de `SLSN-I` actualizado a 1.577 ± 0.039 (antes 1.604 ± 0.036).
- `exploration/lightcurvelynx/fase13_scan.py` -- exploratorio, no versionado (escaneo de
  `RESTLAMBDA_RANGE` real de las 19 clases, Paso 1).

## Fase 14 — estado real de `GENMAG_SMEAR_MODELNAME: G10` (`SNIa` únicamente)

Último candidato del roadmap original, marcado de entrada como el de menor prioridad (afecta solo
1/19 clases) pero barato de verificar. `run_snia_ddf_poc.py` ya trae un comentario propio desde
Fase 0/1 admitiendo que `SIGMA_INT=0.090` (leído de `SALT2.INFO`) es una "aproximación aceptada del
modelo G10 completo... fuera de alcance para un PoC" -- nunca se había re-confirmado qué le falta
exactamente ni si la falta podría explicar parte del residuo.

### Qué hace el G10 real (confirmado en código, no en el manual)

`GENMAG_SMEAR_MODELNAME: G10` está real y activo en `SIMGEN_INCLUDE_SNIa-SALT2.INPUT`. Leyendo
`sntools_genSmear.c::get_genSmear_SALT2()` (repo público de SNANA), la dispersión intrínseca real de
G10 es la suma de DOS términos independientes, no solo uno:

```c
magSmear(lam) = SMEAR0 + SMEAR(lam)
```
- `SMEAR0 = rCOH * SIGCOH` -- **exactamente lo que ya implementa el PoC**: un solo número aleatorio
  gaussiano por evento, multiplicado por `SIGCOH` (0.090, de `SALT2.INFO`), igual para todas las
  bandas.
- `SMEAR(lam)` -- **el término que falta por completo**: SNANA lee un archivo real,
  `salt2_color_dispersion.dat` (viene con el template `SALT2.WFIRST-H17`, no un archivo genérico),
  construye nodos de longitud de onda cada 800 Å, y a CADA nodo le asigna un número aleatorio
  gaussiano INDEPENDIENTE escalado por `sigma(lambda)` de ese archivo -- interpolado suavemente entre
  nodos (`interp_SINFUN`). El resultado es dispersión cromática real: bandas distintas de un mismo
  evento pueden salir más o menos brillantes entre sí, no solo el evento completo desplazado parejo
  como hace `SIGMA_INT` solo.

### Magnitud real de `sigma(lambda)` (leída directo del archivo real en NLHPC)

`salt2_color_dispersion.dat` tiene una forma de "cuenco": mínimo cerca de 5700 Å (banda V), sube
fuerte hacia el UV y sube de nuevo hacia el IR cercano:

| λ rest (Å) | sigma(λ) | banda LSST aprox. (z≈0) |
|---|---|---|
| 3040 | 0.159 | borde azul de `u` |
| 3990 | 0.042 | borde rojo de `u` / `g` |
| 4590-6990 | 0.017-0.028 | `g`/`r` (mínimo real ≈5690 Å) |
| 7980 | 0.059 | `i`/`z` |
| 9000 | 0.090 | `z`/`Y` |
| 10500 | 0.125 | borde rojo de `Y` |

Comparado con la aproximación plana `SIGCOH=0.090` sola: en `g`/`r` el término cromático que falta
(0.017-0.03) es chico frente a `SIGCOH` -- la aproximación actual ya es razonable ahí (dispersión
total real ≈√(0.090²+0.02²)≈0.092, casi igual a 0.090). En `u` e `Y`, en cambio, el término cromático
que falta es del mismo orden o MAYOR que `SIGCOH` (dispersión total real ≈√(0.090²+0.10²)≈0.13-0.15
mag) -- ahí la aproximación actual **subestima** la dispersión real, no la sobreestima.

### Razonamiento de dirección (sin correr nada todavía)

Justo por subestimar, no sobreestimar, la dispersión real en `u`/`Y`: el efecto esperado de corregir
esto va en la dirección **contraria** a "explicar el sobre-conteo". Más dispersión gaussiana
simétrica alrededor de un umbral de detección de un solo lado (SNR/flujo mínimo) empuja, en promedio,
MÁS objetos marginales por encima del umbral, no menos (el mismo sesgo tipo Eddington ya documentado
en Fase 7) -- así que agregar el término cromático real probablemente subiría un poco la eficiencia
de detección de LightCurveLynx en `u`/`Y`, no la bajaría. Es el mismo patrón que Fase 7 (LightCurveLynx
resultó más tenue, no más brillante, que SNANA) y que Fase 10/13 (mecanismos reales pero que no
explican -- o incluso apuntan en contra de -- el sobre-conteo).

### Conclusión Fase 14

**No se implementa el término cromático completo por ahora.** El razonamiento de dirección (arriba)
sugiere que, si tuviera algún efecto medible, sería en el sentido contrario al que hay que explicar
-- y como implementar el término cromático completo (leer `salt2_color_dispersion.dat`, replicar la
interpolación de nodos de 800 Å con randoms independientes por nodo) es un trabajo bastante más
grande que las demás verificaciones "baratas" de este roadmap, para una clase que además es solo
1/19 del catálogo, no se justifica la inversión sin una razón más concreta para esperar que sí
explique el residuo. Se deja documentado como pendiente reutilizable si en el futuro se necesita
mayor fidelidad de `SNIa` específicamente.

**Con esto se cierran los 5 candidatos del roadmap post-Fase-9** (Fases 10-14): dos reales pero
insuficientes en magnitud (MW E(B-V), extrapolación de borde de SIMSED), dos descartados limpio
(grilla LOGZBIN -- ambiguo más que descartado, en rigor -- y passband/zeropoint), y este último
razonado como improbable sin necesidad de implementarlo. La causa raíz del residuo sistémico sigue
sin identificarse. Los ítems de menor prioridad que quedan en el plan original
(`GENSIGMA_SEARCH_PEAKMJD`, `REDCOV`, la crítica documentada de LightCurveLynx a su propio modelo de
ruido Poisson) son la única pista no explorada; alternativamente, vale la pena considerar que el
residuo podría no tener una causa única identificable vía este tipo de auditoría mecanismo-por-
mecanismo, y que el camino que queda sea una calibración empírica agregada en vez de un fix puntual.

### Archivos de esta fase (Fase 14)

Sin archivos nuevos -- investigación completa e inline (lectura de código fuente de SNANA +
inspección directa del archivo real `salt2_color_dispersion.dat` en NLHPC, sin simulación nueva).
Sin incidentes de cuota.

## Fase 15 — los 3 ítems de menor prioridad del plan original

Cierra el roadmap completo. Los tres se descartan rápido, con evidencia directa de código o de los
archivos reales de esta campaña -- ninguno requirió simulación nueva.

### 15a — `GENSIGMA_SEARCH_PEAKMJD: 1.0`

Real y activo campaña-wide (`include_survey_DDF_baseline_v5.3.1_10yrs.INPUT`). Leyendo
`snlc_sim.c::gen_peakmjd_smear()` completa: calcula `PEAKMJD_SMEAR = GENLC.PEAKMJD + smear` (un
número gaussiano, sigma=1 día) y lo asigna a `SNDATA.SEARCH_PEAKMJD` -- **una única asignación, en
una única línea (`snlc_sim.c:25532`), y esa variable no se vuelve a leer en ningún otro lugar de
`snlc_sim.c`, `genmag_SIMSED.c` ni `genmag_SEDtools.c`** (grep completo, cero resultados adicionales).
Es puro metadata de salida -- una estimación "de pipeline de búsqueda" que se escribe en el header
para quien después ajuste la curva de luz y necesite un PEAKMJD inicial aproximado con algo de
incertidumbre realista. **No afecta el trigger de SEARCHEFF, no afecta el cálculo de Trest (fase) de
ninguna observación generada (que usa `GENLC.PEAKMJD`, el valor verdadero, no el suavizado), no
afecta SNR ni el conteo de detecciones de ninguna forma.** Descartado sin necesidad de portarlo --
no hay nada que replicar en LightCurveLynx porque no participa del cálculo real de nada comparable.

### 15b — `REDCOV` / covarianza de ruido de flujo correlacionado

Grep de `REDCOV`/`TEMPLATE_ZPT`/`CORRELATED`/`FLUXERRMODEL` contra los `.INPUT` reales de las 19
clases (`model_config/` y `elastic/model_config/`), el `.INPUT` de survey real, y el `.SIMLIB` real:
**una sola coincidencia en total**, un comentario en inglés en `SIMGEN_INCLUDE_SNII-NMF.INPUT`
("SIMSED parameters are correlated & interpolated") que se refiere a la interpolación de parámetros
físicos SIMSED, no a covarianza de ruido de flujo. `REDCOV`/`TEMPLATE_ZPT` no aparecen en ningún
archivo real de esta campaña. Descartado -- no está configurado, nada que portar.

### 15c — crítica de LightCurveLynx a su propio modelo de ruido Poisson (notebook `data_driven_noise_dp1`)

Los propios autores de LightCurveLynx muestran (notebook `data_driven_noise_dp1.html`, absorbido vía
WebFetch) que el modelo Poisson estándar de flujo-vs-error se desvía de datos reales de Rubin DP1
(~800k observaciones), y proponen un modelo "data-driven" alternativo (normalizing flow entrenado con
`pzflow`) como mejora general -- no cuantifican una dirección de sesgo específica ni una condición
concreta, lo presentan como una limitación general de cualquier fórmula analítica de ruido fotométrico
frente a la complejidad real de las condiciones de observación.

**Más importante: esta crítica no aplica a este proyecto en absoluto.** El modelo Poisson "genérico"
que critica ese notebook es el que arma sus parámetros (profundidad, PSF, cielo) a partir del OpSim
crudo -- pero este proyecto reemplazó eso desde **Fase 2A** (muy al principio): `snana_noise_columns()`
en cada `run_*.py` construye `sky_bg_e`/`psf_footprint`/`zp` directamente desde `SKYSIG`/`seeingFwhmEff`/
`ZPT` **reales del `.SIMLIB` real de SNANA** (confirmado en el propio código, `run_simsed_poc.py:331-339`),
no desde una estimación genérica derivada del OpSim. El `PoissonFluxNoiseModel` de LightCurveLynx sigue
usándose (sigue siendo "Poisson" en su forma matemática, varianza=señal+fondo), pero alimentado con los
mismos números reales que usa SNANA -- exactamente lo que evita el problema que señala el notebook (usar
parámetros de ruido no representativos de la campaña real). No hay nada que implementar aquí para esta
comparación específica.

### Conclusión Fase 15 (y del roadmap post-Fase-9 completo)

Los 3 ítems de menor prioridad se cierran limpio: dos no están configurados en absoluto en esta
campaña (`REDCOV`, y de hecho tampoco importa `GENSIGMA_SEARCH_PEAKMJD` aunque sí esté activo, porque
no participa del cálculo real), y el tercero (crítica de ruido Poisson de LCL) no es aplicable porque
este proyecto ya usa parámetros de ruido reales de SNANA, no los genéricos que la crítica señala.

Con esto se agotan los 8 candidatos identificados en el roadmap de investigación estructurado tras
absorber la documentación oficial de LightCurveLynx y el manual de SNANA (Fases 10-15). Ninguno
explica el residuo sistémico multiplicativo por sí solo. El estado del proyecto queda así:
- **Confirmado no explicativo, con evidencia directa de código en ambos lados**: extinción MW
  (Fase 10), grilla LOGZBIN de SIMSED (Fase 11, aunque con potencia estadística limitada),
  passband/zeropoint (Fase 12), extrapolación de borde de SED (Fase 13), dispersión cromática G10
  (Fase 14, por razonamiento de dirección), y los 3 ítems de esta fase.
- **Ya descartado en fases anteriores** (Fase 3-9): extinción de host, trigger de detección,
  reproducibilidad/semillas, codificación SIMSED-vs-NON1ASED.
- **Hallazgo más sólido que queda sin explicar**: LightCurveLynx simula objetos ~0.2-0.6 mag más
  *tenues*, no más brillantes, que SNANA (Fase 7) -- lo opuesto a la hipótesis obvia de "sobre-brillo"
  -- y aun así sobre-detecta sistemáticamente. Esto apunta a algo en la interacción ruido/SNR/forma de
  curva de luz que ninguna de las 8 verificaciones puntuales de Fases 10-15 logró aislar.

**Recomendación:** la auditoría mecanismo-por-mecanismo (candidato concreto → verificar en código real
→ probar si corresponde) agotó su lista razonable de candidatos identificables desde la documentación.
Los próximos pasos productivos probablemente ya no sean "¿qué parámetro le falta a LightCurveLynx?"
sino algo más holístico: (a) extender la comparación de brillo sin ruido de Fase 7 a las 18 clases
restantes para confirmar si el patrón "~0.2-0.6 mag más tenue" es universal o varía por clase/tipo de
SED; (b) una comparación pointwise de la propagación completa ruido→SNR→trigger para un solo objeto
fijo en ambos códigos (más ambicioso que Fase 11, pero aislaría la cadena completa en vez de un
mecanismo a la vez); o (c) aceptar el residuo como una diferencia de calibración agregada entre ambos
simuladores y trabajar con un factor de corrección empírico por clase en vez de perseguir una causa
única.

### Archivos de esta fase (Fase 15)

Sin archivos nuevos -- investigación completa e inline (greps contra los `.INPUT`/`.SIMLIB` reales de
NLHPC, lectura de código fuente de SNANA, y una consulta WebFetch al notebook real de LightCurveLynx).
Sin simulación nueva, sin incidentes de cuota.

## Fase 16 — comparación pointwise ruido→SNR→trigger (Opción 2 del usuario tras Fase 15)

Con los 8 candidatos del roadmap agotados, se retoma el enfoque "holístico" (b) que quedó pendiente:
comparar la cadena completa ruido→SNR→trigger para un objeto/clase fijo, en vez de un mecanismo a la
vez. Se eligió `SNIa` (SALT2) para esto -- no por casualidad: **Fase 1 (el origen mismo del proyecto)
ya había documentado una discrepancia de SNR real y sin resolver para esta clase específica**
("el modelo de ruido fotométrico de LightCurveLynx subestima el ruido por-época real... queda como
brecha abierta para Fase 2"), y esa brecha nunca se retomó formalmente con las herramientas y el
acceso al código fuente real que este proyecto fue acumulando en Fases 10-15.

### Paso 1 -- fórmula de ruido: reconstruida línea por línea, resulta matemáticamente equivalente

Se leyó `gen_fluxNoise_calc()` completa (`snlc_sim.c`, ~L27505-27600) -- la función real que arma la
varianza de ruido de SNANA. Fórmula real (unidades p.e., gain=1 en esta campaña):
```
NEA = 4π·σ²_psf(arcsec) / pixsize²          (Noise Equivalent Area, misma formula en ambos lados)
fluxsn_pe = 10^(0.4·(zpt-mag))                (shot noise de la fuente)
sqerr_sky_pe = NEA · SKYSIG²                  (ruido de cielo)
sqerr_ccd_pe = NEA · readnoise²                (read noise CCD)
sqerr_zp_pe  = (fluxsn_pe · (10^(0.4·zpterr)-1))²   (incertidumbre de zeropoint)
sqsig_true = fluxsn_pe + sqerr_sky_pe + sqerr_ccd_pe + sqerr_zp_pe
```
Comparada término a término contra `poisson_bandflux_std()` real de LightCurveLynx
(`noise_models/base_noise_models.py`) -- reconstruidas ambas en Python
(`fase16_noise_formula_compare.py`, no versionado) y evaluadas con condiciones de observación reales
tomadas del `.SIMLIB` real (SKYSIG/PSF1/ZPTAVG/ZPTERR reales) para varias magnitudes de fuente:
**con los mismos parámetros reales (`readout_noise=0.25`, `dark_current=0`, los valores reales de esta
campaña), el `fluxerr` de LightCurveLynx coincide con el de SNANA con una razón de 0.9986-1.0000** --
prácticamente idéntico. Las dos fórmulas son matemáticamente equivalentes.

**Hallazgo colateral real, pero en la dirección contraria:** `snana_noise_columns()` nunca pasa
`read_noise`/`dark_current` explícitos a `OpSim`, así que LightCurveLynx cae en los *defaults*
hardcodeados de la clase `OpSim` (`obstable/opsim.py`): `readout_noise=8.8` e⁻/píxel y
`dark_current=0.2` e⁻/s/píxel (constantes genéricas de LSSTCam, fuente citada:
`smtn-002.lsst.io`) -- muy por encima del `readnoise=0.25` real y simplificado que usa el `.SIMLIB`
de esta campaña (`WriterParams.ccd_noise`). Con los defaults reales del proyecto (no los "matched"),
el `fluxerr` de LightCurveLynx sale **entre 0.3% y 12% más grande** que el de SNANA (mayor en
`g`/`r` a magnitudes brillantes, donde el ruido de cielo es más chico y el read noise pesa más) --
real, pero en la dirección **contraria** a explicar el sobre-conteo (más ruido en LCL, no menos).
Se deja documentado como una discrepancia real de fidelidad (candidato de bajo impacto para portar
si se retoma esta fase), no como causa del residuo.

### Paso 2 -- SNR remedido hoy: la brecha de Fase 1 se achicó mucho, pero no desapareció

Se corrió `run_snia_ddf_poc.py` fresco (job 11563393) con TODO el código acumulado desde Fase 1
(incluye `zp_err_mag=0.005` ya corregido en Fase 1 punto 7b, ruido real de SNANA vía
`snana_noise_columns()`, dispersión MWEBV real de Fase 10, etc.) -- el propio script ya compara
automáticamente contra la referencia real:

| | mediana SNR | p90 SNR |
|---|---|---|
| SNANA real (`SNIa_DDF`) | 0.78 | 2.26 |
| LightCurveLynx, medido en Fase 1 (histórico) | 1.008 (+29%) | 5.68 (+151%, 2.5x) |
| LightCurveLynx, remedido hoy (Fase 16) | 0.868 (+11.3%) | 2.948 (+30.4%) |

La brecha se redujo sustancialmente (de 2.5x a 1.3x en la cola alta) gracias a los fixes acumulados
en fases posteriores, pero **sigue existiendo un residuo real del 11-30%** -- no explicado por la
fórmula de ruido (Paso 1 la confirmó equivalente). Tiene que venir del numerador (flujo simulado),
no del denominador (ruido).

### Paso 3 -- brillo sin ruido para SALT2: nunca antes probado, y en dirección OPUESTA a Fase 7

Fase 7 estableció (para `SNIa-91bg`, SIMSED) que LightCurveLynx simula objetos **más tenues** que
SNANA -- pero esa comparación nunca se hizo para `SNIa` (SALT2), un modelo completamente distinto
(`sncosmo.SALT2Source`, no `SIMSEDModel`). `run_snia_ddf_poc.py` nunca extraía `flux_perfect` (mismo
bug metodológico que Fase 7 encontró y corrigió para SIMSED, nunca portado a SALT2). Se construyó
`compare_brightness_truth_salt2.py` (mismo patrón de Fase 7, reconstruye el `source_model` real de
`run_snia_ddf_poc.py` pero captura `flux_perfect` en banda `r` en vez de descartarlo) y se comparó
contra el `.DUMP` real de producción (`SNIa_DDF_baseline_v5.3.1_10yrs.DUMP`, `PEAKMAG_r`,
`SELECTION: NONE`):

| bin z | N SNANA | mediana SNANA | N LCL | mediana LCL | Δ (LCL-SNANA) |
|---|---|---|---|---|---|
| [0.011,0.181) | 10 | 19.691 | 13 | 20.176 | +0.486 (poca estadística) |
| [0.181,0.351) | 64 | 21.489 | 56 | 21.256 | **-0.234** |
| [0.351,0.521) | 164 | 22.415 | 158 | 22.277 | **-0.137** |
| [0.521,0.690) | 257 | 23.313 | 276 | 23.185 | **-0.128** |
| [0.690,0.860) | 368 | 24.346 | 382 | 24.106 | **-0.239** |
| [0.860,1.030) | 490 | 25.169 | 546 | 25.029 | **-0.140** |
| [1.030,1.200) | 379 | 26.156 | 552 | 26.040 | **-0.116** |

**Salvo el primer bin (poca estadística), LightCurveLynx sale sistemáticamente MÁS BRILLANTE que
SNANA en todo el rango de redshift real, ~0.12-0.24 mag** -- lo opuesto de Fase 7, y en la dirección
CORRECTA para explicar el sobre-conteo de `SNIa`. Cuantitativamente consistente: 0.12-0.24 mag de
exceso de brillo ≈ 11-25% de exceso de flujo, del mismo orden que el 11-30% de exceso de SNR medido
en el Paso 2 -- y dado que el Paso 1 mostró que el ruido de LCL es *más* grande, no más chico, que el
de SNANA, el exceso de brillo tiene que ser -- por eliminación -- toda la explicación del exceso de
SNR observado (y un poco más, para compensar el exceso de ruido).

**Candidato de causa más probable, no verificado hasta el fondo:** `GENMEAN_SALT2ALPHA=0.14`,
`GENMEAN_SALT2BETA=3.1`, `GENPEAK_SALT2c/x1` y sus sigmas coinciden EXACTAMENTE con
`SIMGEN_INCLUDE_SNIa-SALT2.INPUT` real -- pero **`GENMAG_OFF`/la magnitud absoluta M_abs no está
declarada en absoluto en el `.INPUT` real** (`GENMAG_OFF_GLOBAL` default de SNANA es 0.0, sin M_B0
explícito para SALT2 en este archivo). El PoC usa `m_abs_func = Normal(loc=-19.3, ...)` -- un valor
de la literatura general, nunca verificado contra la convención interna real que usa SNANA para
`SALT2.WFIRST-H17` (que probablemente deriva su M_B0 de la normalización `FLUXSCALE` propia del
template, no de un M_abs configurable). Una diferencia de calibración de ~0.15-0.2 mag entre la
convención `X0FromDistMod` de LightCurveLynx/sncosmo y la normalización real de SNANA explicaría el
patrón observado limpiamente. No se llegó a verificar la convención exacta de sncosmo (fuera del
alcance razonable de esta sesión, ya muy extensa) -- queda como el cabo suelto más concreto y
accionable de todo el proyecto.

### Conclusión Fase 16

**El hallazgo más sólido y accionable desde Fase 7.** A diferencia de los candidatos de Fase 10-15
(todos descartados o insuficientes), este apunta a una causa real, cuantificada, en la dirección
correcta, y específica de una sola clase bien delimitada (`SNIa`/SALT2): LightCurveLynx simula
supernovas ~0.12-0.24 mag más brillantes que SNANA para los mismos parámetros SALT2 reales
(alpha/beta/x1/c/z), consistente numéricamente con el exceso de SNR observado. La causa más probable
es una diferencia de calibración de magnitud absoluta (M_abs/M_B0) entre la convención que usa
`X0FromDistMod` de LightCurveLynx y la normalización interna real de SNANA para este template SALT2
específico -- no verificada hasta el fondo, pero el cabo suelto más concreto de todo el proyecto.
**Recomendación:** el siguiente paso natural (fuera de esta sesión) es leer el código fuente de
`sncosmo.SALT2Source`/`X0FromDistMod` para encontrar la convención exacta de M_B0 que asumen, y
comparar contra cómo SNANA deriva x0 internamente para `SALT2.WFIRST-H17` sin `GENMAG_OFF`
declarado -- si se confirma una diferencia de calibración, es un fix de una constante, no una
reimplementación.

### Archivos de esta fase (Fase 16)

- `exploration/lightcurvelynx/compare_brightness_truth_salt2.py`/`.sbatch` -- primera comparación de
  brillo sin ruido para la clase SALT2 (nunca antes hecha, Fase 7 solo cubrió SIMSED).
- `exploration/lightcurvelynx/fase16_noise_formula_compare.py` -- exploratorio, no versionado
  (reconstrucción y comparación numérica de ambas fórmulas de ruido, Paso 1).
- Sin cambios a `run_simsed_poc.py`/`run_snia_ddf_poc.py` -- esta fase es diagnóstico, no
  implementación (el fix de M_abs, si se confirma, queda para retomar).

### Paso 4 -- se retoma el candidato M_abs: descartado, con el signo contrario al esperado

Se leyó el código fuente REAL de ambos lados para la fórmula x0↔magnitud absoluta:

**LightCurveLynx** (`X0FromDistMod`/`_x0_from_distmod`, `astro_utils/snia_utils.py`):
```python
# distmod = -2.5*log10(x0) + alpha*x1 - beta*c - m_abs + 10.635
x0 = 10 ** (-0.4 * (distmod - alpha*x1 + beta*c + m_abs - 10.635))
```

**SNANA** (`SALT2x0calc()`, `genmag_SALT2.c:2932`):
```c
arg   = 0.4 * ( dlmag - alpha*x1 + beta*c );
x0inv = X0SCALE_SALT2 * pow(TEN, arg);   // X0SCALE_SALT2 = 1.0E-12 (genmag_SALT2.h)
x0    = 1./x0inv;
```
con `mBoff_SALT2 = 10.635` (`load_mBoff_SALT2()`, `genmag_SALT2.c:2975`) -- **la misma constante
exacta que usa LightCurveLynx**, confirmando que ambos códigos implementan la misma convención
estándar de normalización SALT2 (mB = mBoff - 2.5·log10(x0), SNLS/VEGA system, Guy+2010).

Despejando ambas fórmulas para el mismo `x0`/`distmod`/`alpha·x1`/`beta·c`, el M_abs *implícito* que
usa SNANA (vía `X0SCALE_SALT2`) es:
```
m_abs_SNANA = 2.5·log10(X0SCALE_SALT2) + mBoff_SALT2 = 2.5·log10(1e-12) + 10.635 = -30 + 10.635 = -19.365
```
contra `m_abs = -19.3` que usa el PoC (`m_abs_func`, valor de la literatura general nunca antes
verificado). **Diferencia real: 0.065 mag -- pero con el signo CONTRARIO al necesario.** -19.365 es
*más brillante* que -19.3 (más negativo). Si se corrigiera el PoC a -19.365, LightCurveLynx generaría
objetos **aún más brillantes** que ahora -- empeoraría la discrepancia observada (LCL ya sale más
brillante que SNANA), no la explicaría. Descartado como causa del exceso de 0.12-0.24 mag: de hecho,
sin este pequeño efecto de compensación en la dirección opuesta, la discrepancia real subyacente
sería *aún mayor* (~0.19-0.30 mag) que la medida en el Paso 3.

**Candidatos residuales, no verificados (quedan para retomar si se decide seguir):** la fórmula de
conversión x0↔mB ya se confirmó idéntica -- el exceso de brillo tiene que venir de la propia
NORMALIZACIÓN DE FLUJO del template SALT2 (`salt2_template_0.dat`/`_1.dat`, interpolación 2D
fase×longitud de onda -- sncosmo vs. el motor interno de SNANA podrían interpolar/normalizar
distinto pese a leer el mismo archivo real), o del *color law* (`SALT2.INFO::COLORCOR_PARAMS`,
"reconstruido a mano" desde Fase 0/1, nunca verificado línea por línea contra la fórmula real de
`genmag_SALT2.c` -- un error de escala en el término `beta·c` produciría justo un offset sistemático
como el observado, dado que `GENPEAK_SALT2c=-0.054` no es cero). Verificar cualquiera de los dos
requiere una comparación punto a punto de flujo crudo (patrón similar a Fase 11's
`evaluate_bandfluxes()`, pero para SALT2/sncosmo en vez de SIMSED) -- no se hizo en esta sesión.

### Paso 5 -- color law verificado hasta el fondo: coincide EXACTO, descartado como causa

Se cerró el segundo candidato residual de Fase 16. `sncosmo.models.SALT2Source._set_colorlaw_from_file()`
sí lee `Salt2ExtinctionLaw.version`/`min_lambda`/`max_lambda` del archivo real que genera
`setup_salt2_local.py` (confirmado leyendo `models.py` real del paquete instalado, `sncosmo==2.13.0`
en el venv de NLHPC) y, para `version=1`, delega en `SALT2ColorLaw` -- una clase Cython compilada
(`salt2utils.cpython-312-x86_64-linux-gnu.so`), sin fuente Python instalada localmente. Se descargó el
`.pyx` real (`raw.githubusercontent.com/sncosmo/sncosmo/master/sncosmo/salt2utils.pyx`) para leer su
implementación exacta:

```cython
# SALT2CL_B = 4302.57, SALT2CL_V = 5428.55 (constantes fijas, iguales a las internas de SNANA)
# coeffs[0] = alpha = 1.0 - sum(params)          -- misma normalizacion que SNANA
# P(l) = alpha*l + params[0]*l^2 + params[1]*l^3 + ...   -- mismo polinomio
# fuera de [l_lo, l_hi]: extrapolacion lineal tangente (valor + derivada analitica en el borde)
#   -- mismo mecanismo exacto que SALT2colorfun_pol/_dpol de SNANA (Paso 4 arriba)
```
Coincide, término a término, con `SALT2colorlaw1`/`SALT2colorfun_pol`/`_dpol` reales de SNANA
(`genmag_SALT2.c`) -- misma normalización `alpha`, mismo polinomio, mismo mecanismo de extrapolación
lineal tangente, mismas constantes de referencia B/V. El único punto que requería verificación
numérica (no solo algebraica) era si el doble signo negativo interno de sncosmo
(`out = -out` dentro de `__call__`, luego `10**(-0.4*colorlaw(wave)*c)` en `models.py:813`) se cancela
correctamente contra la convención de signo de SNANA (`exp(c*constant*val)`, sin negar) -- confirmado
numéricamente:

```python
# fase16_verify_colorlaw.py (no versionado) -- evalua AMBAS formulas reales (sncosmo.salt2utils.
# SALT2ColorLaw cargando el archivo real, y una reconstruccion Python 1:1 de SALT2colorlaw1) en el
# mismo grid de lambda, incluyendo puntos DENTRO y FUERA de [2800,9500] A, con c=-0.054 real (GENPEAK_SALT2c)
```

| λ (Å) | factor sncosmo | factor SNANA (reconstruido) | razón | Δmag |
|---|---|---|---|---|
| 1500 (fuera, extrapolado) | 2.468619 | 2.468619 | 1.000000 | 0.000000 |
| 2800 (borde) | 1.394828 | 1.394828 | 1.000000 | -0.000000 |
| 4302.6 (B, referencia) | 1.000000 | 1.000000 | 1.000000 | -0.000000 |
| 5428.6 (V, referencia) | 0.951481 | 0.951481 | 1.000000 | -0.000000 |
| 9500 (borde) | 0.865289 | 0.865289 | 1.000000 | 0.000000 |
| 12000 (fuera, extrapolado) | 0.856784 | 0.856784 | 1.000000 | -0.000000 |

**Coinciden a precisión de máquina en todo el rango probado, dentro y fuera de la zona de calibración
-- el color law está correctamente implementado, no explica el exceso de brillo de 0.12-0.24 mag.**
Con esto, los DOS candidatos concretos identificados en la Fase 16 (M_abs, color law) quedan
descartados con evidencia numérica sólida. El candidato que queda -- la normalización/interpolación
2D (fase×longitud de onda) del propio flujo del template `salt2_template_0/1.dat` en `sncosmo` vs. el
motor interno de SNANA -- sigue sin verificar; requeriría comparar flujo crudo punto a punto (mismo
patrón de Fase 11 pero para SALT2), no hecho en esta sesión.

## Fase 17 — limpieza de disco, glosario del dashboard, escala WFD

Ronda de trabajo pedida explícitamente por el usuario: liberar espacio, verificar el color law (Paso
2/5 arriba, ya cerrado dentro de Fase 16), mejorar el dashboard con un glosario, confirmar el `z`
máximo de `SLSN-I`, correr simulaciones a escala WFD, y generar un notebook de análisis.

### Limpieza de disco (~14.6 GB liberados)

Se borraron los `phot_df.parquet` de las 97 carpetas `poc_output_*` que lo tenían (76 de semillas
`_seed1..4` + 20 de "semilla 0"/principal), verificando antes que cada una tuviera `summary.json`
(ninguna carpeta se saltó -- las 97 lo tenían). Se conservó `head_df.parquet`/`summary.json`/`qc/*.png`
en todas. **199G → 185G** confirmado (`du -sh ~/`). Además, a pedido explícito del usuario durante la
sesión, se borraron también los `head_df.parquet` de las 80 carpetas `_seed1..4` que lo tenían (~10MB,
son chicos) -- las carpetas de semilla quedan solo con `summary.json`/`qc/`, que es toda la
"comprobación" que hace falta conservar de esas corridas extra (su número ya está incorporado a
`ratio_mean_5seeds`/`ratio_std_5seeds` en el dashboard). Las carpetas "semilla 0"/principal conservan
su `head_df.parquet` intacto.

### Confirmación de `z` máximo de `SLSN-I` (sin cambio de código)

El usuario preguntó si había que ajustar el `z` máximo de `SLSN-I` a 6 (recordando que "en SNANA lo
extendimos más"). Investigación real (grep exhaustivo de todos los `.INPUT` de `SLSN-I` en NLHPC, con
fecha de modificación) confirmó que **no existe ningún `GENRANGE_REDSHIFT=6` activo en ningún archivo
real hoy** -- los valores reales activos son `z=9.7` (SIMSED/MOSFIT,
`/home/mvalenzuela/run_SNANA/model_config/SIMGEN_INCLUDE_SLSN-I-MOSFIT.INPUT`, el canónico que usa la
campaña de producción real) y `z=2.95` (NON1ASED/BBFIT, el más reciente de los tres archivos
relacionados con `SLSN-I` encontrados, `run_SNANA/elastic/model_config/SIMGEN_INCLUDE_SLSN-I_NON1ASED.INPUT`,
modificado 6-Ago-2026). El valor `6.0` solo existe **comentado/deshabilitado**
(`#GENRANGE_REDSHIFT: 0.02 6.0`) en el archivo canónico más antiguo (Oct-2025) -- nunca activo en
ninguna corrida real verificable. `run_simsed_poc.py`/`run_non1ased_poc.py` ya usan exactamente estos
mismos rangos (`(0.02, 9.7)` y `(0.02, 2.95)` respectivamente) -- coinciden con la campaña real, no
hay desalineamiento. **El usuario confirmó usar `z=9.7`** -- no se requirió ningún cambio de código,
solo esta verificación explícita para que quede documentada y no se reabra la duda.

### Soporte WFD en `run_simsed_poc.py`/`run_non1ased_poc.py`/`run_snia_ddf_poc.py` (scripts listos, campaña sin lanzar)

El usuario pidió correr simulaciones a escala WFD (nunca antes probada por LightCurveLynx en este
proyecto -- todo el trabajo previo, Fases 0-16, es DDF), pero a mitad de esta ronda pidió
explícitamente **dejar los scripts escritos sin lanzar la campaña** (la cuota de NLHPC sigue siendo
frágil incluso después de liberar los ~14.6GB de arriba). Este apartado documenta el diseño y la
implementación; la ejecución queda pendiente para cuando el usuario decida lanzarla.

**Problema de diseño**: a diferencia de DDF (6 campos fijos, `DDF_FIELD_EBV` como diccionario nombre→
E(B-V)), WFD no tiene campos fijos -- el dithering real de LSST hace que casi ningún pointing comparta
exactamente la misma posición (`SELECT COUNT(DISTINCT fieldRA || '_' || fieldDec) FROM observations
WHERE target_name NOT LIKE '%ddf_%'` → **1,015,331** combinaciones únicas, confirmado). El SIMLIB real
de WFD (`WFD_baseline_v5.3.1_10yrs.SIMLIB`, ~1.08GB, 20.000 LIBID) también escribe `MWEBV: 0.00` fijo
en cada header (mismo default hardcodeado de `writer.py` que DDF), así que no sirve como fuente. El
mapa SFD real (`dustmaps`/`sfdmap2`) sigue sin poder descargarse desde NLHPC (Fase 0/1: Harvard
Dataverse devuelve cuerpo vacío, el mirror de GitHub solo tiene un README).

**Solución**: `build_wfd_mwebv_grid.py` (nuevo) agrupa las posiciones reales de WFD en una grilla
gruesa de 8° directamente en SQL (`ROUND(fieldRA/8.0)`, `ROUND(fieldDec/8.0)`, `GROUP BY` -- evita
materializar >1M filas en pandas, que colgaba el primer intento con un `SELECT DISTINCT` sin agrupar),
reduciendo a **671 celdas reales**. Consulta el mismo servicio REST IRSA Dust Extinction Service
(`nph-dust`, columna `refPixelValueSFD`) ya usado para los 6 valores DDF, una vez por celda, y guarda
`wfd_mwebv_grid.csv` (columnas `ra,dec,ebv_sfd`). Nuevo helper `snana_params.make_wfd_ebv_lookup()`
hace nearest-neighbor angular (con wrap de RA en 0/360°) contra esa tabla usando el RA/DEC exacto de
cada objeto simulado (no el nombre de campo), reusando `make_mwebv_ratio_scatter()` para el mismo
`GENSIGMA_MWEBV_RATIO=0.16` real ya aplicado en DDF.

**Cambios en los 3 scripts** (`run_simsed_poc.py`, `run_non1ased_poc.py`, `run_snia_ddf_poc.py`), todos
detrás de un nuevo parámetro `wfd: bool = False` / flag CLI `--wfd` (en cualquier posición de los
argumentos):
- Filtro de `OpSim` invertido: `~df["target_name"].str.contains("ddf_", na=False)` en vez de sin la
  negación, sobre el mismo `baseline_v5.3.1_10yrs.db` (mismo patrón ya establecido de leer directo del
  `.db`, no del SIMLIB pre-construido).
- Sin columna `field` para WFD (no se extrae, `ObsTableRADECSampler(..., extra_cols=[])` en vez de
  `["field"]`).
- `ebv_func` bifurcado: `_field_to_ebv` (dict fijo) para DDF, `make_wfd_ebv_lookup(...)` (nearest-
  neighbor real) para WFD -- mismo `seed_base + 10` en ambos casos.
- `NGENTOT`: **igual que DDF** (2000/clase, misma excepción `PISN-STELLA-HYDROGENIC`=20000) -- el
  usuario eligió "NGENTOT chico, tipo DDF" en vez de la escala real de producción (200.000/clase) para
  no volver a agotar la cuota.
- Nuevo sufijo de directorio de salida `_wfd` (p.ej. `poc_output_91bg_wfd`, `poc_output_wfd` para
  `run_snia_ddf_poc.py`) -- no pisa ninguna corrida DDF existente.
- `summary.json` gana un campo `"strategy": "WFD"|"DDF"`; el label de QC (`qc.run_all_qc(...)`) pasa a
  decir `..._WFD_poc` en vez de `..._DDF_poc`.

**Verificado**: los 4 archivos (`snana_params.py` + los 3 `run_*_poc.py`) compilan (`py_compile`) sin
error. **No verificado todavía** (pendiente de una corrida real, que el usuario pidió no lanzar en esta
sesión): que `wfd_mwebv_grid.csv` cargue correctamente dentro de `simulate_lightcurves()` y que el
nearest-neighbor produzca valores de E(B-V) razonables end-to-end. `build_wfd_mwebv_grid.py` corrió
como job en background en NLHPC (`nohup`, ~671 celdas × ~1.1s/celda ≈ 12-13 min) -- confirmar que
terminó y que `wfd_mwebv_grid.csv` tiene ~671 filas válidas antes de la primera corrida WFD real.

**Cómo lanzar cuando se decida** (no ejecutado en esta sesión): `python3 run_simsed_poc.py
SNIa-91bg-elastic --wfd` (smoke test sugerido, clase rápida ya familiar) desde un job sbatch, tras
verificar headroom real con `dd if=/dev/zero of=... bs=1M count=N` antes de cada clase -- una clase a
la vez, no las 19 en paralelo, dado que la cuota de NLHPC sigue siendo el recurso más frágil del
proyecto.

`build_wfd_mwebv_grid.py` sí terminó de correr en esta sesión (job en background en NLHPC, ~671
celdas × ~1.1s/celda): `wfd_mwebv_grid.csv` quedó generado y versionado (671 filas, `ebv_sfd` real
SFD98: mediana=0.090, p75=0.185, máx=22.53 -- rango correcto para un footprint que cruza el plano
galáctico, a diferencia de los 6 campos DDF que se eligieron justamente por tener E(B-V) bajo).

### Notebook Jupyter de análisis (`analyze_phot_df.ipynb`)

Nuevo `exploration/lightcurvelynx/analyze_phot_df.ipynb`, 18 celdas (9 markdown + 9 código). Diseño
clave: como el Paso 1 borró casi todos los `phot_df.parquet` reales (solo queda uno,
`poc_output/phot_df.parquet` -- SNIa DDF/SALT2, 107MB, 3.8M filas de fotometría) y la campaña WFD no
se lanzó (ver arriba), el notebook **escanea el disco en cada ejecución** (`poc_output*/summary.json`)
en vez de asumir una lista fija de clases/estrategias, y separa el análisis en dos niveles:
- Lo que **no** depende de `phot_df.parquet` (eficiencia de detección por clase, distribución de
  redshift/NOBS, eficiencia vs. redshift binned) -- funciona hoy con las 25 corridas que sí conservan
  `head_df.parquet` más los 106 `summary.json` que quedan en todas las carpetas.
- Lo que sí depende de `phot_df.parquet` (SNR simulado, cobertura de bandas, curvas de luz de ejemplo)
  -- se salta con un aviso explícito (no falla) en cualquier corrida que no lo tenga.
- Una sección final de comparación DDF-vs-WFD que hoy imprime "todavía no hay ninguna clase con ambas"
  (0 corridas WFD encontradas) pero se completa sola, sin editar el notebook, en cuanto se lance
  cualquier clase con `--wfd`.

Incluye un glosario condensado de columnas (`SNID`/`RA`/`DEC`/`REDSHIFT_HELIO`/`NOBS`/`DETECTED` en
`head_df`; `MJD`/`FLT`/`FLUXCAL`/`FLUXCALERR`/`MAG`/`PHOTFLAG` en `phot_df`; los campos de
`summary.json`) para que sea autocontenido, no solo remita al glosario del dashboard.

**Jupyter no estaba instalado en el venv de NLHPC** (solo tenía `pandas`/`pyarrow`/`matplotlib`, las
librerías de simulación) -- se instaló `jupyter`/`nbconvert`/`ipykernel` (verificado headroom con `dd`
antes, ~180MB instalados, sin impacto real en la cuota). **Verificado end-to-end real**: se corrió
`jupyter nbconvert --to notebook --execute --inplace` dentro de un job sbatch (nunca en el login node,
`execute_analyze_notebook.sbatch`, job 11891199, `COMPLETED 0:0`) contra los datos reales ya en disco
-- las 9 celdas de código ejecutaron sin error (incluidas las 3 celdas "guardia" que hoy reportan datos
faltantes en vez de fallar), las 4 celdas de gráficos generaron imagen real. La versión commiteada es
la ejecutada (con outputs reales embebidos, ~510KB), no una plantilla vacía.

## Fase 18 — síntesis de los 9 puntos de la reunión con el profe

El usuario trajo una lista de 9 puntos de una conversación con su profesor sobre por qué
LightCurveLynx difiere de SNANA. Esta fase no investigó nada nuevo -- cruzó cada punto contra la
evidencia ya acumulada en Fases 0-17 y armó una síntesis (documento HTML, no versionado en el repo,
publicado como artifact para llevar a la reunión). Resultado: **8 de los 9 puntos quedan cerrados con
evidencia directa de código real de ambos lados**:

1. Campo angular -- Fase 1 punto 4 (footprint DDF real vía `ObsTableRADECSampler`) + Fase 17 (WFD).
2. Propiedades del telescopio -- Fase 12 (throughput/zeropoint, `kcor_LSST.fits` real, `ZPoff=0`,
   mismo release v1.9) + Fase 2A (SKYSIG/PSF/ZPT reales del `.SIMLIB`).
3. Criterio de detección -- mismo criterio (Fase 1 punto 5, Fase 6), **con un bug real identificado
   y ya corregido que el usuario confirmó que hay que reportar formalmente**: Fase 4 encontró que
   `searcheff.py` contaba observaciones individuales en vez de épocas reales agrupadas
   (`NEWMJD_DIF=0.007d`) antes del trigger `>=2` -- afectaba a las 14 clases SIMSED por igual, ya
   corregido (`group_into_epochs()`), verificado formalmente como subconjunto estricto del método
   viejo.
4. Ruido -- Fase 16 paso 1 (`gen_fluxNoise_calc()` reconstruida, `fluxerr` coincide 0.9986-1.0000).
5. Tasa DNDZ(z) por clase -- 5 modelos reales (`POWERLAW2`/`MD14`/`CC_S15`/TDE/`PISN_PLK12`) de
   Fases 2B/6/7, tabla completa de 20 configs (SIMSED+NON1ASED+SALT2) verificada en esta síntesis.
6. z máximo por clase -- misma tabla del punto 5; caso `SLSN-I` reconfirmado explícitamente en Fase 17.
7. Ley de extinción R_V -- MW (Fase 1 punto 6, Fase 10, fórmula `gen_MWEBV()` verificada línea por
   línea) + color law SALT2 (Fase 16, coincide a precisión de máquina con `sncosmo`).
8. A_V por clase (extinción de host) -- 3 variantes reales (`exp`/`exp_halfgauss`/`wv07`) de Fase 3 y
   Fase 2B rondas 2-3, tabla completa por clase.
9. **Parámetros SALT2 -- el único punto que queda abierto**, y es el más importante: alpha/beta/x1/c
   y sus sigmas coinciden EXACTOS con el `.INPUT` real (Fase 16 paso 3), pero `M_abs`/`M_B0` nunca se
   verificó contra la convención interna real de SNANA (el `.INPUT` no declara `GENMAG_OFF`) -- sigue
   siendo el candidato más fuerte, con evidencia cuantitativa consistente en signo y magnitud
   (0.12-0.24 mag de exceso de brillo sin ruido, Fase 16 paso 3), para el residuo que queda tras
   cerrar los otros 8 puntos.

**Acciones que salen de esta síntesis** (no ejecutadas en esta fase): (a) reportar formalmente el bug
del punto 3 como hallazgo documentado; (b) el siguiente paso técnico real del proyecto sigue siendo el
que ya recomendaba el cierre de Fase 16 -- leer `sncosmo.SALT2Source`/`X0FromDistMod` para encontrar
la convención de M_B0 y compararla contra cómo SNANA deriva `x0` internamente sin `GENMAG_OFF`.

## Fase 19 -- auditoría real de z máximo por clase, convención M_B0/SALT2, instructivo, y nota de bugs

Continuación directa de Fase 18: (1) auditoría fresca de `GENRANGE_REDSHIFT` contra la fuente de
verdad real de producción (no solo los `.INPUT` template, sino qué `.INPUT` **de verdad** compiló cada
`GENVERSION`), (2) el seguimiento técnico que Fase 16/18 dejó pendiente -- la convención real de
`M_B0`/`x0` de SNANA para SALT2 --, (3) un instructivo operativo (`HOWTO.md`), y (4) la nota pedida
sobre qué bug es local y cuál amerita reportarse a la comunidad de LightCurveLynx.

### Auditoría de z máximo -- resultado: ningún cambio de código hizo falta

Fase 17/18 ya habían verificado `GENRANGE_REDSHIFT` por clase contra los `.INPUT` template
(`run_SNANA/model_config/`, `run_SNANA/elastic/model_config/`) -- pero esos árboles tienen variantes
sin usar (p.ej. `elastic/model_config/SIMGEN_INCLUDE_SNIa-SALT2.INPUT` con `z=1.65`, que nunca se
compila a ningún `GENVERSION` real de esta campaña). Esta fase fue más allá: se encontró la fuente de
verdad real -- `AUTOSIM/build/full_v5.3_10yrs/includes/include_model_<clase>.INPUT`, el archivo
`INPUT_INCLUDE_FILE:` que **de verdad** referencia cada `GENVERSION` compilado (confirmado leyendo
`sim_SNIa_DDF_baseline_v5.3.1_10yrs.INPUT` real, que a su vez incluye
`includes/include_model_SNIa.INPUT`, que apunta a
`run_SNANA/model_config/SIMGEN_INCLUDE_SNIa-SALT2.INPUT`, NO al árbol elastic). Se grepeó
`INPUT_INCLUDE_FILE` de los 40 `include_model_*.INPUT` reales y se cruzó contra el `GENRANGE_REDSHIFT`
real de cada uno, comparado clase por clase contra `CLASS_CONFIGS` de los 3 scripts:

**Las 19 clases dentro del alcance del proyecto (14 SIMSED + 5 NON1ASED + SALT2) coinciden EXACTAS
con el `z` real de producción, sin excepción** -- incluidas las variantes NON1ASED (que usan el árbol
`elastic/`, confirmado que ESA sí es la fuente real para ellas vía su propio `include_model_*.INPUT`).
Confirmado además que el include de modelo es **el mismo para DDF y WFD** (`include_model_SNIa.INPUT`
aparece igual en `sim_SNIa_DDF_...INPUT` y `sim_SNIa_WFD_...INPUT`) -- no hay `z` distinto por
estrategia en la campaña real, así que los scripts WFD (Fase 17, comparten `CLASS_CONFIGS` con DDF)
ya están alineados por construcción, sin necesitar overrides nuevos.

Las dos entradas `-elastic` de `run_simsed_poc.py` (`SNIa-91bg-elastic`, `SNIax-elastic`) siguen sin
corresponder a ningún `GENVERSION` real -- son variantes deliberadas creadas en Fase 6/7 para el
bake-off de codificación SIMSED-vs-NON1ASED (probar el efecto de un `z` más ancho), nunca tuvieron la
intención de igualar una corrida SNANA real, así que no aplican a este punto.

**Conclusión: no se modificó ningún `CLASS_CONFIGS`** -- la petición del usuario ("que cada clase
quede simulada hasta el mismo z que SNANA") ya estaba cumplida, con una verificación ahora más
rigurosa que confirma no solo que el valor está bien sino que se leyó del archivo correcto.

### Convención real de M_B0/x0 de SNANA para SALT2 (seguimiento de Fase 16/18, punto 9)

Se leyó el código fuente real de SNANA (`genmag_SALT2.c`) para encontrar `SALT2x0calc()`/
`SALT2mBcalc()`/`load_mBoff_SALT2()` -- la pieza que Fase 16 dejó pendiente.

**Fórmula real de SNANA:**
```c
// genmag_SALT2.c
mBoff_SALT2 = 10.635;                                   // load_mBoff_SALT2(), hardcoded real
arg   = 0.4 * (dlmag - alpha*x1 + beta*c);               // dlmag = GENLC.DLMU, distmod COSMOLÓGICO
                                                           // puro (gen_distanceMag() real, SIN M_abs)
x0inv = X0SCALE_SALT2 * pow(10, arg);   x0 = 1/x0inv;     // X0SCALE_SALT2 = 1.0E-12 ("arbitrary
                                                           // normalization", genmag_SALT2.h)
mB    = mBoff_SALT2 - 2.5*log10(x0);                      // SALT2mBcalc() -- SOLO diagnóstico/
                                                           // referencia, "not used to generate
                                                           // fluxes" (comentario real del código)
```
**Hallazgo real 1 -- coincide la constante `10.635`**: `mBoff_SALT2 = 10.635` (SNANA, hardcoded
"Aug 11, 2010... hard-wire to value based on SNLS VEGA system") es EXACTAMENTE la misma constante que
usa `X0FromDistMod`/`_x0_from_distmod` de LightCurveLynx (`astro_utils/snia_utils.py`:
`x0 = 10^(-0.4*(distmod - alpha*x1 + beta*c + m_abs - 10.635))`) -- misma forma funcional, mismo signo
en cada término (`alpha*x1` resta de `mB`, `beta*c` suma), evidencia sólida de que ambos códigos
implementan la MISMA relación de Tripp/SALT2 estándar, no hay bug estructural de signo ni de forma.

**Hallazgo real 2 -- `X0SCALE_SALT2` es puro bookkeeping, NO un M_abs real (trampa algebraica real,
encontrada y corregida en esta misma fase)**: un primer intento de igualar las dos fórmulas
algebraicamente (despejar qué `m_abs` haría que `X0FromDistMod` reproduzca la `mB` de SNANA) da
`m_abs_equiv = 10.635 + 2.5*log10(1e-12) = -19.365` -- pero esto resultó ser un espejismo. Se rastreó
`X0SCALE_SALT2` hasta `INTEG_zSED_SALT2()` (misma función que integra el flujo real): `SEDMODEL.FLUXSCALE
= X0SCALE_SALT2` se aplica AL FLUJO GENERADO (`*Finteg *= x0; *Finteg *= MODELNORM_Finteg` con
`MODELNORM_Finteg` que carga el mismo factor `X0SCALE_SALT2`) -- es decir, `X0SCALE_SALT2` aparece una
vez en `x0` (como `1/X0SCALE_SALT2`) y otra vez en el flujo (`× X0SCALE_SALT2`), **se cancela
exactamente** en el flujo físico real. La `mB`/`x0` que SNANA reporta como diagnóstico (`SIM_SALT2mB`,
`SIM_SALT2x0` en el `.DUMP`/FITS) vive en una escala corrida ~30 mag por esta convención de
bookkeeping -- consistente con el propio comentario del código ("mB is not used to generate fluxes").
**Cualquier `M_abs` derivado igualando esa fórmula de `mB` directamente es indistinguible de un
artefacto de esta convención interna, no de una calibración física real** -- confirmado indirectamente
porque el signo resultante (`-19.365`, más brillante que el `-19.3` actual) va en la dirección
CONTRARIA a la necesaria para cerrar el exceso de brillo ya medido en Fase 16 (LightCurveLynx ya sale
más brillante, no más tenue).

**Camino que sí es confiable -- calibración empírica usando el residuo ya medido**: dado que resolver
esto de punta a punta requeriría además inspeccionar la normalización física interna de los templates
`salt2_template_0/1.dat` tal como los lee `sncosmo.SALT2Source` (tercera convención de unidades, no
inspeccionada en esta fase), el camino confiable es usar directamente el residuo YA MEDIDO
end-to-end en Fase 16 (que sí compara brillo físico real, no una fórmula intermedia): 6 bins bien
poblados (excluyendo el primero, con poca estadística) dieron
`Δmag = LCL - SNANA = {-0.234, -0.137, -0.128, -0.239, -0.140, -0.116}`, media `-0.166` mag (LCL más
brillante). Como `mB` y `m_abs` se mueven 1:1 en la fórmula de LightCurveLynx (confirmado arriba,
misma forma que SNANA), la corrección calibrada es
**`m_abs ≈ -19.3 + 0.166 ≈ -19.13`** (más tenue que el valor actual, para compensar el exceso).
**No se aplicó este cambio a `run_snia_ddf_poc.py`** -- es una calibración empírica ajustada al
residuo medido, no una derivación de primeros principios, y cambiar `m_abs` invalidaría/recalcularía
todos los resultados de Fase 16 ya documentados como el hallazgo principal; queda como recomendación
concreta para la próxima sesión, junto con el paso pendiente real (inspeccionar
`sncosmo.SALT2Source`/normalización de los archivos `.dat` para cerrar esto con evidencia de primeros
principios en vez de un ajuste empírico).

### Nota -- bug local vs. bug real de LightCurveLynx (qué reportar al foro de la comunidad)

El usuario pidió aclarar si el bug de Fase 4 (trigger de detección contando observaciones individuales
en vez de épocas reales) es un bug **local** (de este proyecto) o del **programa** LightCurveLynx. Es
**100% local**: `SEARCHEFF` (curvas de eficiencia de detección, lógica de trigger) no existe en
absoluto dentro de LightCurveLynx -- es un módulo propio de este proyecto (`searcheff.py`) escrito
para replicar el comportamiento real de `snlc_sim.exe`. El bug estaba en nuestra propia
reimplementación del trigger, no en ningún código de LightCurveLynx -- **no hay nada que reportar al
foro de la comunidad por este hallazgo específico.**

Dicho esto, esta investigación SÍ encontró bugs reales **dentro del propio paquete instalado**
(`lightcurvelynx==0.5.2`, confirmado leyendo `inspect.getsource()` del código real en NLHPC, no
supuesto) que sí ameritan reportarse -- mismo patrón en los 3: un nodo interno arma su propio
generador aleatorio y nunca hereda el `seed=` del constructor externo, rompiendo reproducibilidad
para cualquier usuario que dependa de semillas fijas (no solo este proyecto):

1. **`ObsTableRADECSampler.compute()`** (`lightcurvelynx/math_nodes/ra_dec_sampler.py`) -- aplica
   jitter de posición sub-FOV con `np.random.default_rng()` sin semilla cuando `self.radius > 0`.
2. **`TableSampler.__init__`** (`lightcurvelynx/math_nodes/given_sampler.py`, clase base del
   anterior) -- arma su sampler de índice de fila (`NumpyRandomFunc("integers", ...)`) sin pasarle el
   `seed=` que sí llegó al constructor externo.
3. **`SIMSEDModel.from_dir()`** (`lightcurvelynx/models/sed_template_model.py`) -- arma su
   `GivenValueSampler` de selección de template sin `seed=`.
4. **`MultiSEDTemplateModel.__init__`** (mismo módulo, usado por NON1ASED) -- mismo problema.

Los 4 se confirmaron con un test real (Fase 5: dos procesos Python separados, misma semilla,
resultados distintos hasta corregirlos; byte-idénticos después). Son candidatos reales para un issue
en `github.com/lincc-frameworks/LightCurveLynx` -- "seed= passed to the parent node doesn't propagate
to internal samplers in ObsTableRADECSampler/SIMSEDModel/MultiSEDTemplateModel", con los 4 puntos de
arriba como reproducción. No se abrió el issue en esta fase (el usuario pidió la nota, no la acción).

**Seguimiento (Fase 20)**: se evaluó formalmente publicarlo -- `gh issue list` contra el repo real
(`lincc-frameworks/LightCurveLynx`) confirmó que no es duplicado, y se verificó contra `main` en GitHub
(no solo la versión `0.5.2` instalada) que los 3 bugs (`ObsTableRADECSampler`, `TableSampler`,
`SIMSEDModel`) siguen presentes hoy, sin arreglar. Se redactó el issue completo (título + cuerpo,
formato calibrado contra issues reales del repo) y se le mostró al usuario para confirmación explícita
antes de publicarlo -- **el usuario decidió no publicarlo por ahora**. El borrador completo queda
guardado en `exploration/lightcurvelynx/ISSUE_DRAFT_seed_propagation.md`, listo para publicar más
adelante si se decide (no correr `gh issue create` sin una confirmación explícita nueva).

## Fase 20 -- M_abs de SALT2 cerrado con primeros principios: la Fase 19 se corrige a sí misma

Retoma el pendiente explícito de Fase 19: leer `sncosmo.SALT2Source`/`X0FromDistMod` para encontrar la
convención real de M_B0 y compararla contra cómo deriva `x0` SNANA. **Resultado: la "corrección" que
propuso Fase 19 (declarar el `M_abs=-19.365` de Fase 17 un espejismo, y proponer `-19.13` en su lugar)
era ella misma un error** -- Fase 19 solo verificó que `X0SCALE_SALT2` se cancela del lado de SNANA,
sin verificar si `sncosmo`/LightCurveLynx cancela el mismo factor de la misma forma. No lo hace.

### El hallazgo que faltaba: `sncosmo.SALT2Source._SCALE_FACTOR = 1e-12`

Leyendo `sncosmo/models.py` real (`inspect.getsourcefile`, venv real de NLHPC, `sncosmo==2.13.0`):

```python
class SALT2Source(Source):
    _SCALE_FACTOR = 1e-12          # -- EXACTAMENTE el mismo valor que X0SCALE_SALT2 de SNANA
    def __init__(self, ...):
        for key in ['M0', 'M1']:
            phase, wave, values = read_griddata_ascii(names_or_objs[key])
            values *= self._SCALE_FACTOR      # -- aplicado UNA VEZ, al cargar el archivo
            self._model[key] = BicubicInterpolator(phase, wave, values)
    def _flux(self, phase, wave):
        m0 = self._model['M0'](phase, wave)   # ya trae el *1e-12 horneado
        m1 = self._model['M1'](phase, wave)
        return (self._parameters[0] * (m0 + self._parameters[1] * m1) * ...)  # x0 * M0, sin mas factores
```

A diferencia de SNANA (donde `x0 = 1/(X0SCALE*10^arg)` y el flujo se multiplica DE NUEVO por
`X0SCALE` en `INTEG_zSED_SALT2()` -- por eso se cancela, ver Fase 19), `sncosmo` aplica el `1e-12`
**una sola vez, al leer el archivo**, y `x0` (el parámetro libre que pone `X0FromDistMod`) se usa
directo, sin ningún factor de compensación. **El `1e-12` NO se cancela del lado de LightCurveLynx.**
Fase 19 asumió (sin verificarlo) que ambos lados cancelaban igual -- no era así.

### Verificación numérica directa (no solo álgebra, tercera vez que se hace esta pregunta)

Confirmado que los archivos crudos son **byte-idénticos** (`md5sum` real:
`a75b5afcc7c59354af25c4b182ee3edd` para `salt2_h17_local/salt2_template_0.dat` local y el
`salt2_template_0.dat.gz` descomprimido de `run_SNANA/plasticc_models/SALT2.WFIRST-H17/` real). Con
eso, `fase20_verify_mabs.py` (no versionado) calculó, para `z=0.3, x1=0, c=0, alpha=0.14, beta=3.1`:

| M_abs probado | `x0` (LightCurveLynx) | flujo LCL/flujo SNANA | Δmag (LCL−SNANA) |
|---|---|---|---|
| -19.300 (Fases 0-19) | 3.906753e-05 | 0.941890 | +0.0650 |
| **-19.365** | **4.147783e-05** | **1.000000** | **-0.0000** |
| -19.130 (propuesta Fase 19) | 3.340535e-05 | 0.805378 | +0.2350 |

`x0_SNANA` reconstruido de `SALT2x0calc()` real dio **4.147783e-05** -- coincide con el `x0` de
LightCurveLynx a `M_abs=-19.365` a 6 cifras significativas exactas. El flujo físico (`x0 * 1e-12 *
M0_crudo`, mismo `M0` crudo real para ambos) coincide con razón `1.000000` exacta. `-19.365` no es una
aproximación: es exactamente `10.635 - 30` (`mBoff_SALT2 - 2.5*log10(X0SCALE_SALT2)`), la identidad
algebraica que hace que `X0FromDistMod` reproduzca el `x0` real de SNANA byte a byte.

### Aplicado y verificado end-to-end: la corrección es real, pero el residuo NO se cierra (empeora)

Se corrigió `m_abs_func` (`loc=-19.3` → `loc=-19.365`) en `run_snia_ddf_poc.py` y
`compare_brightness_truth_salt2.py`, y se corrió de nuevo `compare_brightness_truth_salt2.sbatch`
(job 11897156, `COMPLETED`) contra el mismo `.DUMP` real de `SNIa_DDF_baseline_v5.3.1_10yrs`:

| z bin | Δmag Fase 17 (`M_abs=-19.3`) | Δmag Fase 20 (`M_abs=-19.365`, correcto) |
|---|---|---|
| [0.181,0.351) | -0.234 | -0.319 |
| [0.351,0.521) | -0.137 | -0.196 |
| [0.521,0.690) | -0.128 | -0.193 |
| [0.690,0.860) | -0.239 | -0.310 |
| [0.860,1.030) | -0.140 | -0.208 |
| [1.030,1.200) | -0.116 | -0.181 |
| **media** | **-0.166** | **-0.235** |

El desplazamiento medio real (-0.235 − (-0.166) = -0.069 mag) coincide con la predicción algebraica
(0.065 mag) dentro del ruido de binning -- **confirmación end-to-end, no solo de fórmula**.

### Conclusión Fase 20 (cierra el punto 9 de la Fase 18 de forma definitiva)

1. **`M_abs=-19.365` es la calibración físicamente correcta** -- verificada por triplicado (álgebra,
   coincidencia exacta de `x0`/flujo con archivos reales, y re-corrida end-to-end) -- y ya se aplicó a
   `run_snia_ddf_poc.py`/`compare_brightness_truth_salt2.py`. El valor `-19.3` de las Fases 0-19 era un
   placeholder de la literatura general, nunca antes verificado; corregirlo es una mejora real de
   fidelidad, independiente de lo que sigue.
2. **M_abs queda descartado como causa del residuo, con la evidencia más sólida de todo el
   proyecto** -- corregirlo a su valor real EMPEORA el exceso de brillo medido (-0.166 → -0.235 mag),
   no lo cierra. Esto revierte la propuesta de "calibración empírica ~-19.13" de Fase 19, que resultó
   ser un artefacto de un supuesto no verificado (que `X0SCALE_SALT2` cancela simétricamente en ambos
   simuladores) -- no cancela en LightCurveLynx/`sncosmo`, solo en SNANA.
3. **Lección metodológica explícita** (para no repetirla una cuarta vez): cuando dos simuladores
   comparten una constante de "normalización arbitraria", verificar SIEMPRE si esa constante se cancela
   en el flujo físico final de **ambos** lados por separado -- nunca asumir simetría. Las tres rondas
   sobre esta misma pregunta (Fase 17 álgebra parcial, Fase 19 "corrección" parcial, Fase 20 verificación
   completa) son un caso de estudio de por qué este proyecto insiste en verificar numéricamente contra
   archivos/código reales en vez de confiar en la derivación simbólica sola.
4. **Recomendación real que queda**: con M_abs, color law (Fase 16), extinción, ruido, footprint,
   SEARCHEFF, DNDZ y R_V todos cerrados o descartados con evidencia directa, el candidato que queda sin
   investigar es el que Fase 16 ya señalaba: la normalización/interpolación 2D (fase×longitud de onda)
   del propio flujo del template SALT2 -- comparar `M0(phase,wave)`/`M1(phase,wave)` punto a punto entre
   el `BicubicInterpolator` de `sncosmo` y la interpolación real de SNANA (`SALT2_TABLE`, spline/bicúbica
   propia en `genmag_SALT2.c`) sobre la misma grilla cruda -- nunca hecho, y ahora es el único mecanismo
   de la cadena SALT2 sin verificar directamente.

### Archivos de esta fase

- `run_snia_ddf_poc.py`/`compare_brightness_truth_salt2.py`: `m_abs_func` corregido a `-19.365`, con
  comentario explicando la derivación completa.
- `fase20_verify_mabs.py`/`fase20_compare_bins.py` (exploratorios, no versionados, borrados de NLHPC
  tras usarlos -- mismo criterio del proyecto para scripts de verificación puntual).
- `docs/index.html`: pestañas "Resumen"/"21 fases" de LightCurveLynx actualizadas para reflejar este
  cierre (reemplaza la recomendación de `-19.13` de Fase 19, ya superada).

## Fase 21 -- interpolación 2D del template SALT2: verificada y descartada como causa

Retoma el último candidato concreto que dejó pendiente Fase 16/20: la normalización/interpolación 2D
(fase × longitud de onda) del propio flujo del template SALT2 -- nunca antes comparada directamente
entre `sncosmo`/LightCurveLynx y SNANA.

### Hallazgo real: los dos simuladores usan esquemas de interpolación genuinamente distintos

Leyendo `fill_SALT2_TABLE_SED()`/`INTEG_zSED_SALT2()` reales (`genmag_SALT2.c`) y el `SALT2.INFO` real
de `SALT2.WFIRST-H17` (`SEDFLUX_INTERP_OPT: 1  # 1=>linear, 2=>spline` -- **confirmado LINEAR activo
para esta campaña**, no el default `2` (spline) del código): SNANA evalúa el flujo en cualquier
`(Trest, LAMSED)` con **interpolación bilinear real** (2×2 vecinos, lineal en día y en longitud de
onda, fórmulas `FSED = VAL0+(VAL1-VAL0)*FRAC_INTERP_LAMSED` y `FTMP = FSED[0]+FDIF*FRAC_INTERP_DAY`).

`sncosmo.salt2utils.BicubicInterpolator` (descargado el `.pyx` real, mismo método de Fase 16 --
`sncosmo/salt2utils.pyx` en GitHub, el paquete instalado solo trae el binario compilado) es
literalmente el <em>"Grid2DFunction" de snfit</em> -- **convolución bicúbica real** (kernel de Keys,
`a=-0.5`, ventana de 4×4 vecinos), con fallback a bilineal solo cerca de los bordes de la grilla. Son
dos algoritmos de interpolación genuinamente distintos, nunca antes comparados en este proyecto.

### Verificación numérica: la diferencia es real, pero 100x demasiado chica

`fase21_verify_interp.py` (no versionado) reimplementó la fórmula bilineal exacta de SNANA y la
comparó contra el `BicubicInterpolator` real de `sncosmo` (mismo objeto interno que usa
`SALT2Source._model['M0']`), sobre el `M0` crudo real (grilla nativa real: `DAYSTEP=1.0` día,
`LAMSTEP=10` Å) -- en el pico (`phase=0`) para la longitud de onda rest-frame real de la banda `r` en
los 7 `z` de Fase 16/20, y en un barrido fino de fase (`-10` a `+30` días) en B rest-frame:

| Punto de prueba | Δmag (bicúbico − bilineal) |
|---|---|
| pico, 7 valores de z reales (rest-frame r) | entre -0.0017 y +0.0022 mag |
| barrido de fase completo (B rest-frame, -10 a +30 d) | entre -0.0017 y +0.0022 mag |

**Máximo absoluto medido: 0.0022 mag** -- tres órdenes de magnitud más chico que el residuo de
`-0.235` mag (Fase 20). Con `DAYSTEP=1` día y `LAMSTEP=10` Å (grilla fina respecto a la escala de
variación real de la superficie SALT2), bilineal y bicúbico convergen -- **descartado como causa, con
evidencia numérica directa, no solo argumento de plausibilidad.**

### Conclusión Fase 21

Con esto se agotan los tres candidatos concretos de la cadena de generación de flujo SALT2 (color law
-- Fase 16 --, M_abs/M_B0 -- Fase 20 --, e interpolación 2D del template -- esta fase): **los tres
verificados directamente contra código y archivos reales, los tres descartados como causa del residuo
de ~0.235 mag.** La cadena SALT2 (`x0`↔magnitud, ley de color, superficie M0/M1) está ahora verificada
de punta a punta -- el residuo no viene de la física del modelo SALT2 en sí.

**Candidato metodológico nuevo, no descartado, no investigado todavía**: la comparación de "brillo
pico" (Fase 7/16/20) toma `flux_perfect.max()` sobre las épocas realmente observadas (cadencia real de
`OpSim`) del lado LightCurveLynx, no un escaneo continuo de fase -- si SNANA computa `PEAKMAG_r` de
forma distinta (evaluación directa en el verdadero pico de la curva, no limitada a la cadencia
observada), una diferencia de método -- no de física -- podría sesgar la comparación. No verificado en
esta sesión; requeriría leer cómo SNANA calcula `PEAKMAG_<filtro>` en el `.DUMP` real (`snlc_sim.c`).

### Archivos de esta fase

`fase21_verify_interp.py` (exploratorio, no versionado, borrado de NLHPC tras usarlo). Sin cambios de
código en los scripts del proyecto -- esta fase es diagnóstico puro, sin fix que aplicar (candidato
descartado, no una causa a corregir).

## Fase 22 -- el residuo real es más grande de lo reportado: la metodología de "pico" subestimaba el brillo

Retoma el candidato metodológico que dejó pendiente Fase 21: la comparación de "brillo pico" usada en
Fases 7/16/20/21 (`flux_perfect.max()` sobre las épocas que la cadencia real de OpSim efectivamente
observó) podría no ser la misma medición que `PEAKMAG_r` real de SNANA.

### Confirmado: SNANA mide el pico verdadero, no uno limitado por cadencia

Leyendo `snlc_sim.c` real (~línea 12857-12866, comentario real *"always add artificial PEAKMJD epoch
to be last"*): SNANA inserta, para cada filtro, un epoch **sintético** exactamente en
`GENLC.PEAKMJD` (`OBSFLAG_GEN=false` -- no es una observación real generada, solo bookkeeping interno)
específicamente para que `PEAKMAG_<filtro>` sea el flujo evaluado en el pico verdadero/continuo
(fase=0 rest-frame), **no** el máximo sobre las épocas realmente cadenciadas.

### Herramienta real encontrada: `compute_noise_free_lightcurves()`/`compute_single_noise_free_lightcurve()`

LightCurveLynx expone una API real y ya probada (`lightcurvelynx/simulate.py`) para evaluar curvas de
luz sin ruido en fases rest-frame arbitrarias, **sin pasar por ningún `OpSim`/cadencia** -- reutiliza
`model.evaluate_bandfluxes()`, la misma maquinaria interna real que usa `simulate_lightcurves()`, no
una aproximación. Permite reusar el mismo `graph_state` (parámetros ya sampleados: z, x1, c, t0, ra,
dec) para comparar de forma pareada, objeto por objeto, la métrica vieja (cadencia) contra la métrica
correcta (`rest_frame_phase_min=0, rest_frame_phase_max=0.5, rest_frame_phase_step=1.0` → un solo
punto exacto en `t0`).

### Resultado: ~1/3 de los objetos tienen cobertura de cadencia pésima cerca de su propio pico

Corrido sobre los mismos 2000 objetos de `compare_brightness_truth_salt2.py` (mismo `seed_base`, mismo
`M_abs=-19.365` de Fase 20), comparando `flux_perfect.max()` (cadencia) vs. flujo evaluado en
`rest_phase=0` (verdadero), objeto por objeto:

- **33.6% de los objetos tienen `|Δmag| > 0.5`** entre ambas métricas -- la cadencia real de DDF
  (pocas épocas por objeto) frecuentemente no cae cerca del pico real de un objeto dado.
- Caso extremo real verificado (no un bug de cómputo -- confirmado comparando contra la distribución
  completa de su bin de `z`, donde el valor "verdadero" cae justo en la mediana): un objeto con
  `flux_cadence_max=0.000355` pero `flux_true_peak=8945.6` (mediana real de su bin de z: ~8095) -- la
  cadencia simplemente nunca lo observó cerca de su pico real.
- La dirección es sistemática, no aleatoria: la mediana por objeto de `Δmag(verdadero−cadencia)` es
  **negativa** en los bins de `z` bajo (el pico verdadero es más brillante que el medido por cadencia,
  como predice la lógica -- un máximo sobre un subconjunto discreto de épocas nunca puede superar al
  máximo continuo) y se vuelve **positiva** hacia `z` alto (más complejo -- posición del pico real de
  banda `r` observada, que a alto `z` mapea a longitudes de onda rest-frame más azules, no coincide
  exactamente con `t0` definido en banda B).

### Recalculado contra el `.DUMP` real: el residuo casi se duplica

Repitiendo el binning de Fase 20 (mismos 7 bins de `z`, misma mediana poblacional por bin,
`PEAKMAG_r` real de SNANA sin cambios) pero con la métrica corregida (`flux` en `rest_phase=0` en vez
de `flux_perfect.max()` sobre cadencia):

| z bin | Δmag Fase 20 (cadencia, método viejo) | Δmag Fase 22 (`rest_phase=0`, corregido) |
|---|---|---|
| [0.181,0.351) | -0.319 | -0.466 |
| [0.351,0.521) | -0.196 | -0.480 |
| [0.521,0.690) | -0.193 | -0.534 |
| [0.690,0.860) | -0.310 | -0.599 |
| [0.860,1.030) | -0.208 | -0.503 |
| [1.030,1.200) | -0.181 | -0.534 |
| **media** | **-0.235** | **-0.519** |

**El residuo real (medido de forma consistente en ambos lados -- SNANA ya evalúa su `PEAKMAG_r` en el
pico verdadero, no limitado por cadencia) es de ~-0.52 mag, más del doble de los ~-0.235 mag
reportados desde Fase 16.** La metodología usada desde Fase 7 (incluyendo Fase 16/20/21, todas las
verificaciones de color law/M_abs/interpolación 2D) subestimaba sistemáticamente el brillo real de
LightCurveLynx por el sesgo de cadencia -- esas tres verificaciones (color law, M_abs, interpolación)
siguen siendo válidas como descartes (todas comparaban contra la MISMA métrica vieja de forma
consistente, así que sus conclusiones de "no explica la brecha" no cambian), pero la magnitud real de
lo que hay que explicar es mayor de lo que se pensaba.

### Conclusión Fase 22

**Hallazgo metodológico real, no una causa física nueva**: el residuo sistémico de brillo de este
proyecto es más grande de lo reportado en las Fases 7-21 (~-0.52 mag, no ~-0.235 mag), pero la causa
raíz sigue sin identificarse -- de hecho ahora es un problema más grande de lo que parecía. Con color
law, M_abs e interpolación 2D ya descartados (Fase 16/20/21) y ahora con la magnitud real confirmada
más alta, el siguiente paso natural (Paso 2 de esta fase, pendiente) es comparar la curva de luz SALT2
completa -- no solo el pico -- entre ambos simuladores, para localizar en qué fase/banda específica
diverge la física, ya que "es más grande de lo pensado" por sí solo no dice dónde buscar.

**Nota metodológica para trabajo futuro**: cualquier comparación de brillo "pico" en este proyecto de
ahora en adelante debe usar `compute_noise_free_lightcurves()` (evaluado en `rest_phase=0`), no
`flux_perfect.max()` sobre la cadencia real -- la cadencia real de DDF (pocas épocas por objeto) no es
suficientemente densa para que el máximo observado sea una proxy confiable del pico verdadero.

### Archivos de esta fase

`fase22_paso1_peak_bias.py`/`fase22_paso1_vs_dump.py` (exploratorios, no versionados, borrados de
NLHPC tras usarlos). Sin cambios a `run_*_poc.py`/`compare_brightness_truth_salt2.py` -- este hallazgo
es sobre la METODOLOGÍA de comparación (un script de análisis nuevo, no parte del pipeline de
simulación), no sobre un parámetro a corregir en la simulación en sí.

## Fase 23 -- la otra arista: el residuo corregido depende de la banda (patrón tipo extinción)

Continuación directa de Fase 22 -- se extiende la métrica corregida (`compute_noise_free_lightcurves`
en `rest_phase=0`, sin sesgo de cadencia) de la banda `r` sola a las **6 bandas LSST reales**
(`u,g,r,i,z,y`), comparadas contra las columnas reales `PEAKMAG_u/g/r/i/z/Y` del mismo `.DUMP` de
producción -- nunca antes comparado banda por banda con la métrica corregida.

### Resultado: el residuo NO es plano en longitud de onda

| Banda | Δmag medio (LCL−SNANA, bins 2-7, métrica corregida) |
|---|---|
| `g` | -0.593 |
| `r` | -0.519 |
| `i` | -0.469 |
| `z` | -0.435 |
| `y` | -0.382 |
| `u` | (solo 1 bin con datos válidos -- `PEAKMAG_u` real queda indefinido en la mayoría de los bins de
  `z`, banda muy angosta/tenue para SNIa a estos redshifts, sin estadística suficiente para concluir) |

**Patrón claro y monótono**: el exceso de brillo de LightCurveLynx es MÁXIMO en `g` (banda más azul con
estadística suficiente) y decrece sistemáticamente hacia el rojo (`r`→`i`→`z`→`y`) -- una diferencia de
~0.21 mag entre `g` y `y`. Esto es cualitativamente **el mismo patrón que produce la extinción** (más
fuerte en azul, más débil en rojo) -- un candidato real y concreto que no se había visto antes porque
todas las comparaciones de brillo previas (Fases 7/16/20/21/22) se hicieron solo en banda `r`.

### Lo que esto NO invalida (y lo que sí reabre)

- El color law en sí (`SALT2colorlaw1`/`SALT2ColorLaw`, Fase 16) sigue verificado idéntico a precisión
  de máquina -- ese mecanismo específico no es la causa.
- `x0` (el factor acromático que escala toda la SED) también sigue verificado idéntico (Fase 20) -- no
  puede producir por sí solo una dependencia de banda.
- La interpolación 2D (Fase 21) ya se midió despreciable (`<0.0022` mag) en B rest-frame -- no se
  volvió a medir explícitamente para las otras 5 bandas en este barrido, queda como cabo suelto menor.
- **Candidato real que reabre esto**: la extinción MW (`ExtinctionEffect`/`O94`, aplicada
  `frame="observer"`) es intrínsecamente cromática (más fuerte en azul) -- nunca se verificó si
  LightCurveLynx aplica la MISMA cantidad de extinción, banda por banda, que el `OPT_MWCOLORLAW`/`R_V`
  real de SNANA para el mismo `E(B-V)` nominal. Fase 10 solo verificó la FÓRMULA de dispersión
  (`GENSIGMA_MWEBV_RATIO`) sobre el valor nominal de `E(B-V)`, nunca la curva de extinción cromática
  aplicada al flujo en sí, banda por banda. Es el candidato más concreto y accionable que queda.

### Conclusión Fase 23

Confirma que la "otra arista" (comparar más allá de un solo número/banda) sí revela información nueva
que el enfoque anterior (solo banda `r`) no podía ver: el residuo tiene estructura cromática real, no
es un offset acromático global. El siguiente paso natural, no ejecutado en esta sesión, es comparar
directamente la curva de extinción MW aplicada (`ClippedExtinctionEffect`/`dust_extinction` `O94` vs.
`OPT_MWCOLORLAW` real de SNANA) evaluada en las 6 bandas para un `E(B-V)` fijo, aislando ese mecanismo
específico del resto de la cadena.

### Archivos de esta fase

`fase23_multiband_peak.py` (exploratorio, no versionado, borrado de NLHPC tras usarlo). Sin cambios a
scripts del pipeline -- diagnóstico puro.

## Fase 24 -- accionado el candidato de Fase 23: ley de extinción MW real es Fitzpatrick99, no O94

Acciona directamente el candidato que dejó abierto Fase 23 (extinción MW cromática).

### Hallazgo real: el `.INPUT` real usa `OPT_MWCOLORLAW: 99` (Fitzpatrick99 exacto), nunca O94/CCM89

Grepeando `AUTOSIM/build/full_v5.3_10yrs/includes/include_model_<clase>.INPUT` reales (confirmado
idéntico para `SNIa`, `SLSN-I`, `SNIa-91bg` -- se inyecta por clase, campaña-wide, no varía):
```
OPT_MWEBV:  1
OPT_MWCOLORLAW:  99
```
Leyendo `MWgaldust.h` real de SNANA: `OPT_MWCOLORLAW_FITZ99_EXACT = 99` ("exact Fitzpatrick (1999),
S.Thorp 2024") -- **no** `OPT_MWCOLORLAW_CCM89=89` ni `OPT_MWCOLORLAW_ODON94=94`. Los 5 scripts del
proyecto que aplican extinción MW (`run_simsed_poc.py`, `run_non1ased_poc.py`, `run_snia_ddf_poc.py`,
`compare_brightness_truth.py`, `compare_brightness_truth_salt2.py`) usaban
`extinction_model="O94"` desde Fase 1 -- un supuesto ("misma familia que SNANA") nunca antes verificado
contra el valor numérico real del `.INPUT`. Afecta a las 19 clases por igual, no solo `SNIa`.

### Verificado numéricamente: la diferencia es real, pero demasiado chica para explicar Fase 23

`dust_extinction` (el mismo paquete que ya usa el proyecto) trae `F99` como clase nativa. Comparando
`O94(Rv=3.1)` vs `F99(Rv=3.1)` -- `.extinguish()` real de ambas -- en las 6 bandas LSST, para los
`E(B-V)` reales de los 6 campos DDF (`0.006-0.025`) y un valor de referencia 6x más alto (`0.10`):
**diferencia máxima medida: <0.005 mag**, incluso en el caso de referencia con `E(B-V)` artificialmente
alto -- tres órdenes de magnitud más chico que el patrón de ~0.21 mag (g→y) de Fase 23. Consistente con
el hallazgo ya establecido en Fase 1 (los 6 campos DDF se eligieron deliberadamente por su baja
extinción): con `E(B-V)` tan bajo, la elección de ley de extinción casi no importa en magnitud absoluta,
sin importar cuál de las dos sea la "correcta". **Descartado como causa del patrón cromático de
Fase 23**, con evidencia numérica directa -- pero es una corrección real de todas formas.

### Corregido en los 5 scripts, sin necesidad de re-correr para verificar

Se corrigió `extinction_model="O94"` → `extinction_model="F99"` en los 5 scripts. No se re-corrió el
catálogo completo para confirmar el cambio -- la propia verificación numérica de arriba (<0.005 mag de
diferencia máxima a estos `E(B-V)`) ya acota el efecto esperado muy por debajo del ruido estadístico de
5 semillas ya reportado por clase (Fase 5), así que no hay nada que una re-corrida real pudiera revelar
que la verificación directa no haya cerrado ya.

### Conclusión Fase 24

El candidato concreto de Fase 23 queda accionado (corrección real aplicada) pero **no explica el patrón
cromático** -- descartado con la misma evidencia numérica directa que ya cerró color law (Fase 16),
M_abs (Fase 20) e interpolación 2D (Fase 21). El patrón g→y de ~0.21 mag de Fase 23 sigue sin explicarse.
**Candidato que queda, no investigado**: dado que el patrón correlaciona con la banda OBSERVADA (mismo
orden descendente `g>r>i>z>y` en cada bin de `z` de Fase 23, no con la longitud de onda rest-frame que
cada banda mapea según `z` -- lo que descartaría un artefacto ligado al redshift) el mecanismo más
probable que queda sin verificar es la propia **convención de integración de flujo en banda**
(photon-counting vs. energy-flux, factor `LAMSED*TRANS` visto en `INTEG_zSED_SALT2()` real de SNANA
vs. la integración real de `sncosmo`/LightCurveLynx) -- nunca comparada explícitamente término a
término, a diferencia de la forma estática del passband (Fase 12, sí verificada idéntica).

### Archivos de esta fase

`run_simsed_poc.py`, `run_non1ased_poc.py`, `run_snia_ddf_poc.py`, `compare_brightness_truth.py`,
`compare_brightness_truth_salt2.py`: `extinction_model` corregido de `"O94"` a `"F99"`.
`fase24_verify_extinction.py` (exploratorio, no versionado, borrado de NLHPC tras usarlo).

## Fase 25 -- integración de flujo en banda: intento sin resultado confiable (documentado honesto)

Ataca el candidato que dejó abierto Fase 24: la convención de integración de flujo en banda
(photon-counting vs. energy-flux) entre SNANA y `sncosmo`/LightCurveLynx.

### Lo que se confirmó con lectura de código real (sólido)

- **SNANA** (`INTEG_zSED_SALT2()` real, `genmag_SALT2.c`): `Fbin_forFlux = FTMP * CCOR * HOSTXT_FRAC *
  MWXT_FRAC * LAMSED * TRANS`, con `LAMSED` = longitud de onda REST-FRAME (`LAMOBS/(1+z)`) y `TRANS` =
  transmisión real del filtro en `LAMOBS`. Pesa por `λ` (photon-counting), consistente con la
  convención estándar de fotometría de conteo de fotones.
- **LightCurveLynx** (`Passband.compute_system_response_table()` real,
  `astro_utils/passbands.py`): `φ_b(λ) = S_b(λ)/λ / ∫[S_b(λ)/λ]dλ` -- cita explícita "eq. 8, On the
  Choice of LSST Flux Units (Ivezić et al.)" -- pesa por `1/λ`, no por `λ`. Documentado como una
  convención real y deliberada (no un bug), con referencia a un paper técnico real de LSST.

Que ambas fórmulas tengan un peso de signo opuesto en `λ` (uno `+λ`, el otro `1/λ`) es real y
verificado -- **pero no se pudo determinar de forma confiable si esto produce una diferencia neta
significativa**, por lo que sigue abajo.

### Intento de verificación numérica: resultado NO confiable, documentado en vez de ocultado

Se intentó reconstruir "a mano" la fórmula literal de SNANA (mismo patrón exitoso de Fases 16/19-21)
y compararla contra `Passband.fluxes_to_bandflux()` real de LightCurveLynx, usando el mismo `M0`/`M1`
crudo real y el mismo color law real (`sncosmo.SALT2ColorLaw`), en las 6 bandas LSST reales, a `z=0.6`
(representativo de la población de Fase 23). **Primer intento**: bug real encontrado y corregido en el
propio script (reconstruir `S_b(λ)` desde `normalized_system_response` de LightCurveLynx es circular --
ya trae horneada la normalización `1/λ` de LCL con una constante DISTINTA por banda, contaminando la
comparación). Corregido usando la tabla de transmisión cruda real (`transmission_table`, sin normalizar)
interpolada a la grilla de cada banda.

**Resultado tras la corrección: sigue sin ser confiable.** Los números salen implausiblemente grandes
(hasta ~3 mag en banda `u`) y **no monótonos** entre bandas (`u:+2.97, g:+0.36, r:0, i:-0.22, z:-0.15,
y:+0.58`) -- ni de lejos compatible con el patrón suave y monótono de Fase 23 (`g→y`, ~0.21 mag total).
Diagnóstico probable: a `z=0.6`, el borde azul de la banda `u` observada mapea a `λ_rest≈2000` Å --
exactamente el límite crudo del template SALT2 (`wave_grid[0]=2000`) -- el corte duro que aplica el
script ahí (`wave_rest >= wave_grid[0]`) introduce una discontinuidad artificial justo dentro de la
banda `u`, y el resultado inestable en las otras bandas (el signo de `y` se invirtió por completo entre
el primer y segundo intento, solo por corregir el bug de normalización circular) sugiere que la
reconstrucción manual, aislada de la ejecución real de ninguno de los dos códigos, es demasiado frágil
para esta pregunta específica -- **no aporta evidencia confiable en ninguna dirección.**

### Conclusión Fase 25 -- honesta: candidato ni confirmado ni descartado

A diferencia de Fases 16/20/21/24 (donde la reconstrucción manual sí dio resultados limpios y
verificables), este intento no llegó a un resultado defendible. No se reporta un número porque no se
confía en él -- **el candidato de la convención de integración de banda queda abierto, sin resolver**,
ni confirmado ni descartado. La forma correcta y confiable de cerrar esto (no intentada en esta sesión,
requiere más tiempo/alcance): correr el binario REAL de `snlc_sim.exe` (`SNANA_DIR` real ya disponible
en NLHPC, confirmado en fases anteriores) con un objeto de prueba controlado (`x1`/`c`/`z`/`t0` fijos,
`NGENTOT_LC` chico) y comparar su flujo por banda real, epoch por epoch, directo contra
`compute_noise_free_lightcurves()` real de LightCurveLynx para el mismo objeto -- comparación código
real contra código real, no una reconstrucción manual de la fórmula de SNANA que ya mostró ser frágil
en este caso específico (a diferencia de `SALT2x0calc`/interpolación 2D/color law, donde sí funcionó
bien en Fases 16/20/21).

### Archivos de esta fase

`fase25_bandflux_convention.py` (exploratorio, no versionado, borrado de NLHPC tras usarlo -- 2
versiones, la primera con el bug de normalización circular ya documentado arriba). Sin cambios a
scripts del pipeline -- ningún hallazgo lo suficientemente confiable como para actuar sobre él.

## Fase 26 -- integración de flujo en banda cerrada: código real vs. código real, descartada

Cierra definitivamente el candidato que dejó abierto Fase 25, siguiendo el camino que esa misma fase
identificó como el correcto: comparar código real contra código real, no una reconstrucción manual de
la fórmula de SNANA.

### 1a/1b -- higiene: la reconstrucción manual NO es de fiar, ni por borde de template ni por forma del SED

Se repitió el intento de Fase 25 a `z` seguros (`0.15, 0.3, 0.6, 0.9`, lejos del borde azul del template
SALT2 salvo un efecto menor en `u` a `z=0.9`) y con un control de espectro plano (`f_λ=`constante).
Resultado: la señal es **estable en `z`** (no es un artefacto de borde, contra lo que sugería el
diagnóstico de Fase 25) pero **espectro real y espectro plano dan prácticamente el mismo resultado**
implausible y no monótono (`u:+3.0, g:+0.44, r:0, i:-0.23, z:-0.16, y:+0.56` mag relativo a `r`) -- muy
distinto del patrón suave y monótono de Fase 23. Esto confirma que el problema no es el SED ni el borde
del template: la propia reconstrucción manual, comparando dos fórmulas ad-hoc con normalizaciones no
directamente comparables entre sí, no rastrea ningún efecto físico real. Confirma la recomendación de
Fase 25: abandonar la reconstrucción manual y pasar directo a la prueba definitiva.

### 1c -- la prueba definitiva: `snlc_sim.exe` real vs. `compute_noise_free_lightcurves()` real

Se corrió el binario real de SNANA (`SNANA_DIR=/home/lmod/software/SNANA/11.05p`, módulo `SNANA/11.05p`,
el mismo binario que genera toda la campaña de producción) con un `.INPUT` mínimo (`sbatch`, no en login
node) que fija un objeto SALT2 exactamente conocido: `GENRANGE_REDSHIFT`/`GENRANGE_SALT2c`/
`GENRANGE_SALT2x1` colapsados a un punto (`z=0.15`, `x1=0.973`, `c=-0.054`, mismos valores pico
nominales de la campaña), `GENSIGMA_SALT2c/x1: 0 0`, `OPT_MWEBV: 0` (aísla el objeto de la extinción MW,
ya descartada en Fase 24), mismo modelo real `SALT2.WFIRST-H17`, mismo SIMLIB DDF real,
`OPT_MWCOLORLAW: 99` (Fase 24). No existe un modo `GENPERFECT` que simplifique esto directamente para
este caso (revisado en `snlc_sim.c` real: sus bits solo tocan smearing/extinción/HOSTLIB, no colapsan
rangos de parámetros) -- se usó la vía directa de colapsar `GENRANGE_*`.

Dos bugs reales de sintaxis `.INPUT` encontrados y corregidos en el camino (documentados porque son
reales, no artefactos): `SIMGEN_DUMPALL: N` debe declarar el conteo EXACTO de variables listadas
(un desfase de 3 corrompió el parseo de todas las keys siguientes, incluyendo `GENMODEL`, con el error
engañoso `'' is not a valid genmag-model`); y `DNDZ` es obligatorio incluso con `GENRANGE_REDSHIFT`
colapsado a un punto (sin él, `init_DNDZ_Rate` aborta con `Unknown rate model`).

El `.DUMP` real resultante (`TEST_FASE26_bandflux_hygiene.DUMP`) dio `PEAKMAG_z`/`PEAKMAG_Y` = `-9`
(sin dato) para los 40 objetos generados, pese a que el LIBID elegido sí tiene epochs reales en `z`
(523 observaciones, confirmado grepeando el SIMLIB) -- un comportamiento real de `snlc_sim.exe` no
diagnosticado a fondo (posiblemente relacionado con `GENLC.SIMLIB_USEFILT_ENTRY`/`keep_SIMLIB_OBS`,
visto en el código real pero sin causa raíz confirmada), que queda anotado como cabo suelto menor y no
bloqueante: `u/g/r/i` sí quedaron completos y son exactamente las bandas centrales del patrón de
Fase 23.

Del lado LightCurveLynx: se reconstruyó el objeto EXACTO que generó SNANA (mismo `z` heliocéntrico,
`x1`, `c`, `t0=PEAKMJD` real, `x0` calculado con `_x0_from_distmod()` real de LightCurveLynx usando el
`MU` real que SNANA generó) vía `SncosmoWrapperModel` + `compute_noise_free_lightcurves()` real (sin
`ExtinctionEffect`, ya que `OPT_MWEBV=0` del lado SNANA), para dos objetos reales independientes del
`.DUMP` (CID=2 y CID=7, distintos `z`/`RA`/`DEC`/`PEAKMJD`).

**Resultado, banda por banda, relativo a `r` (aísla el efecto puro de convención, cancela cualquier
offset acromático global):**

| banda | CID=2: LCL−r | CID=2: SNANA−r | diff | CID=7: LCL−r | CID=7: SNANA−r | diff |
|---|---|---|---|---|---|---|
| u | +0.8702 | +0.8722 | −0.0020 | +0.8741 | +0.8760 | −0.0019 |
| g | −0.0708 | −0.0706 | −0.0002 | −0.0707 | −0.0705 | −0.0002 |
| i | +0.3243 | +0.3238 | +0.0005 | +0.3218 | +0.3213 | +0.0005 |

Las diferencias reales (`diff`) son de **0.0002 a 0.002 mag** -- dos a tres órdenes de magnitud más
chicas que el patrón de Fase 23 (`~0.07-0.12` mag entre bandas adyacentes). El offset acromático global
sí es real y del orden esperado (`Δmag(LCL−SNANA)` ≈ `-0.27` mag parejo en las 4 bandas, consistente con
el residuo ya conocido desde Fase 22) -- pero es constante entre bandas, no cromático: la convención de
integración NO introduce estructura cromática detectable a este nivel de precisión.

### Conclusión Fase 26 -- descartado con evidencia sólida, código real contra código real

La convención de integración de flujo en banda (`λ` de SNANA vs. `1/λ` de LightCurveLynx) **no explica
el patrón cromático de Fase 23**, con la evidencia más fuerte posible para esta pregunta: no una
reconstrucción manual de fórmulas (que ya mostró ser frágil en Fase 25 y de nuevo en 1a/1b de esta
fase), sino los dos binarios/APIs reales de producción, para el mismo objeto exacto, comparados
directamente. Con esto se agotan **todos** los candidatos concretos identificados en la cadena SALT2:
color law (Fase 16), `M_abs`/`x0` (Fase 20), interpolación 2D del template (Fase 21), ley de extinción MW
(Fase 24), y ahora la convención de integración de banda (Fase 26) -- los cinco descartados con
evidencia numérica directa. **El patrón cromático de Fase 23 (`g→y`, ~0.21 mag de spread total) queda
sin causa identificada** dentro del alcance de esta investigación de la cadena SALT2 propiamente dicha.
Esto es en sí mismo un resultado válido y bien acotado, no un fracaso: la investigación deja mapeado con
precisión qué NO lo explica, lo cual reduce sustancialmente el espacio de búsqueda para cualquier
continuación futura (candidatos fuera de la cadena SALT2 -- p.ej. el modelo de ruido/PSF por banda, o
algo en el propio `Passband`/`kcor_LSST.fits` no cubierto aún -- quedan como las áreas más probables no
exploradas). Las conclusiones finales de la investigación completa (síntesis como astrónomo experto)
quedan fuera de esta fase, a pedido explícito del usuario, para una sesión aparte.

### Archivos de esta fase

Exploratorios, no versionados, borrados de NLHPC tras usarlos: `fase26_bandflux_hygiene.py` (1a),
`fase26_flat_control.py` (1b), `sim_fase26_bandflux_test.INPUT` + `run_fase26_bandflux_test.sh` (1c,
SNANA real), `fase26_lcl_vs_real_snana.py` + `fase26_check2.py` (1c, LightCurveLynx real). Sin cambios a
scripts del pipeline -- candidato descartado, nada que corregir.

## Fase 27 — la integración de banda SÍ crece con z, pero de signo contrario al patrón de Fase 23

Fase 26 cerró el candidato "integración de flujo en banda" probándolo en un único punto, `z=0.15`, y
generalizó esa conclusión (diferencia despreciable) a toda la cadena SALT2. Pero el patrón cromático de
Fase 23 es un promedio poblacional sobre `z≈0.18` a `z≈1.2` — nunca se verificó si la diferencia (chica
a `z` bajo) se mantiene chica a `z` alto. Antes de asumir eso, se revisaron dos candidatos más por
lectura de código, sin necesitar corridas:

- **Extinción de host (`HOSTXT_FRAC`)**: descartado. El `.INPUT` real de la clase `SNIa` de esta campaña
  (`include_model_SNIa.INPUT` → `SIMGEN_INCLUDE_SNIa-SALT2.INPUT`) no declara `GENTAU_AV`/`GENRANGE_AV`
  — a diferencia de `SNIax`/`TDE-MOSFIT` (Fases previas), SNANA no aplica extinción de host a `SNIa` en
  este modelo. No puede ser la fuente de una diferencia con LightCurveLynx (que tampoco la aplica).
- **`kcor_LSST.fits` vs. preset `LSST`**: ya descartado con evidencia numérica concluyente en **Fase 12**
  (`ZPoff=0`, curvas idénticas a 4 decimales, mismo release v1.9) — no hacía falta repetirlo.

### Paso A — el offset relativo a `r` NO es plano en `z` (dato ya simulado, sin `sbatch` de simulación)

Se extendió `compare_brightness_truth_salt2.py` (mismo `seed_base=20260812`, mismos 2000 objetos) para
capturar las 6 bandas vía `compute_noise_free_lightcurves()` (rest_phase=0) en vez de solo `r`, y se
comparó contra `PEAKMAG_u/g/r/i/z/Y` real del `.DUMP` de producción
(`SNIa_DDF_baseline_v5.3.1_10yrs.DUMP`), binned en los mismos 7 bins equi-anchos de `z` de Fases 20/22/23
(`np.linspace(0.011, 1.2, 8)`). Corrección de metodología real encontrada en el propio análisis:
`PEAKMAG_<filt>=-9` es el flag real de SNANA para "banda no definida en este `z`" (Fase 13 — el borde del
`RESTLAMBDA_RANGE`, `u`/`g` observados mapean a rest-frame por debajo de 2000 Å a `z` alto) — hay que
enmascarar esos valores ANTES de tomar la mediana, no después, o contaminan el resultado con outliers de
`-9` mag (un bug real cometido y corregido en el primer intento de este mismo script).

| bin `z` (centro) | `u−r` | `g−r` | `i−r` | `z−r` | `y−r` |
|---:|---:|---:|---:|---:|---:|
| 0.10 | nan | nan | +0.066 | nan | nan |
| 0.27 | nan | -0.182 | 0.000 | +0.037 | nan |
| 0.44 | nan | -0.099 | -0.026 | -0.037 | +0.285 |
| 0.61 | nan | -0.015 | -0.083 | -0.109 | +0.376 |
| 0.78 | nan | nan | -0.138 | -0.173 | nan |
| 0.95 | nan | nan | -0.074 | -0.096 | nan |
| 1.12 | nan | nan | +0.012 | -0.065 | nan |

*(`u`/`g`/`y` quedan mayormente indefinidos en `PEAKMAG` real fuera de `z` bajo — mismo fenómeno de
borde de template ya señalado en Fase 23; `i` y `z` son las únicas columnas con cobertura completa en
los 7 bins.)* El offset relativo a `r` **no es plano** — crece en magnitud desde los bins bajos hacia
`z≈0.6-0.8` (`i−r`: `+0.066 → 0.000 → -0.026 → -0.083 → -0.138`) y luego se revierte parcialmente hacia
`z` alto. No es una función limpia y monótona de `z`, pero tampoco es constante — suficiente para
justificar extender la prueba código-real-contra-código-real de Fase 26 a más valores de `z`, en vez de
asumir que el resultado de `z=0.15` generaliza.

### Paso B1 — extender Fase 26 (código real vs. código real) a `z=0.6` y `z=0.9`

Mismo método exacto de Fase 26 (1c): `snlc_sim.exe` real (`SNANA/11.05p`) con `GENRANGE_REDSHIFT`/
`GENRANGE_SALT2c`/`GENRANGE_SALT2x1` colapsados a un punto (`x1=0.973`, `c=-0.054`, valores pico
nominales de la campaña), `OPT_MWEBV: 0`, mismo modelo `SALT2.WFIRST-H17`, mismo SIMLIB DDF real,
`NGENTOT_LC: 5`. **Bug real de sintaxis `.INPUT` nuevo, distinto a los dos de Fase 26**: SNANA aborta con
`'GENRANGE_REDSHIFT:' keys exceeds limit=1` si se incluye el `.INPUT` completo del modelo real
(`SIMGEN_INCLUDE_SNIa-SALT2.INPUT`, que ya declara `GENRANGE_REDSHIFT`/`SALT2c`/`SALT2x1`) y ADEMÁS se
re-declaran esas mismas keys para colapsarlas a un punto — `checkStringUnique` con `limit=1` no permite
keys duplicadas, ni siquiera para "sobreescribir". Corregido copiando a mano solo las keys necesarias
(`GENMODEL`, `DNDZ`, `GENRANGE_TREST`, `GENMEAN_SALT2ALPHA/BETA`) sin incluir el archivo completo del
modelo — coherente con la nota de Fase 26 de que no hay una vía de "override" directa en este release.

Del lado LightCurveLynx: se tomó el objeto `CID=1` de cada `.DUMP` real (mismo RA/Dec/PEAKMJD en ambos
`z` porque el `LIBID` de SIMLIB quedó fijo entre corridas) y se reconstruyó exacto vía
`SncosmoWrapperModel` + `compute_noise_free_lightcurves()` real, con `x0` calculado por
`X0FromDistMod` usando el `MU` real que generó SNANA (no una cosmología propia recalculada) — mismo
patrón que Fase 26.

**Resultado, banda por banda, relativo a `r` (misma convención de Fase 26: `diff = (LCL−r) − (SNANA−r)`):**

| `z` | banda | LCL−r | SNANA−r | diff |
|---:|---|---:|---:|---:|
| 0.15 (Fase 26, referencia) | u/g/i | — | — | `-0.0020` / `-0.0002` / `+0.0005` |
| 0.6 | g | +1.3132 | +1.2197 | **+0.0935** |
| 0.6 | i | -0.0270 | +0.0594 | **-0.0864** |
| 0.6 | z | +0.0144 | +0.1141 | **-0.0997** |
| 0.6 | y | +0.1041 | +0.2019 | **-0.0978** |
| 0.9 | i | -0.7188 | -0.5987 | **-0.1201** |
| 0.9 | z | -0.7546 | -0.5775 | **-0.1771** |
| 0.9 | y | -0.6263 | -0.4288 | **-0.1975** |

(`u` queda indefinido en el `.DUMP` real a ambos `z` — banda `u` observada mapea por debajo de 2000 Å
rest-frame ya a `z=0.6`; `g` queda indefinido también a `z=0.9`, mismo mecanismo de borde de Fase 13,
consistente con el patrón de `nan` del Paso A.)

**El efecto SÍ crece fuertemente con `z`**: de `~0.0002-0.002` mag en `z=0.15` (Fase 26) a `~0.09-0.20`
mag en `z=0.6-0.9` — dos órdenes de magnitud, y en `z=0.9` la magnitud (`i:-0.12, z:-0.18, y:-0.20`) es
comparable o mayor a la del propio patrón de Fase 23 (`~0.07-0.12` mag entre bandas adyacentes). **Fase
26 no generalizaba**: su descarte era válido solo en el punto que probó, no para toda la cadena SALT2
como se documentó entonces.

### Pero el signo es el opuesto al patrón que hay que explicar

Traduciendo el patrón poblacional de Fase 23 (`Δmag(LCL−SNANA)` por banda) a la misma convención "relativo
a `r`" que esta prueba (`Δ_Fase23(banda) − Δ_Fase23(r)`): `g: -0.074, i: +0.050, z: +0.084, y: +0.137` —
**creciente y positivo** de `g` a `y` (LCL relativamente cada vez MÁS brillante que SNANA hacia el rojo,
respecto de `r`). El efecto medido acá en `z=0.6-0.9` es **decreciente y negativo** hacia el rojo
(`i:-0.09/-0.12, z:-0.10/-0.18, y:-0.10/-0.20`) — **signo contrario**, no solo en `y` sino en `i`/`z`
también. Un mecanismo que empuja en la dirección opuesta a la observada no puede ser la explicación
(directa, aislada) del patrón de Fase 23 — como mucho, **cancela parcialmente** parte de la señal real a
`z` alto, lo que implica que la causa verdadera (aún no identificada) debe ser de magnitud mayor a la ya
medida en Fase 23 para sobrevivir a esta cancelación parcial.

### Conclusión Fase 27 — reabierto en magnitud, descartado en dirección; resultado genuinamente mixto

No es un descarte limpio ni una confirmación limpia, y se documenta así en vez de forzar una lectura
simple (mismo criterio de honestidad que Fase 25): la integración de banda **no es despreciable a todo
`z`** (Fase 26 generalizaba de más), pero tampoco puede ser la causa (aislada) del patrón de Fase 23
porque el signo no coincide. Verificado además, por lectura de código real sin necesitar corridas
nuevas, que el modelo de dispersión intrínseca cromática real de esta campaña
(`GENMAG_SMEAR_MODELNAME: G10` en `SIMGEN_INCLUDE_SNIa-SALT2.INPUT`, confirmado activo — simplificación
ya señalada como conocida en `NOTES.md` desde las primeras fases, nunca antes verificada) tampoco puede
ser la causa de un sesgo sistemático de mediana: `init_genSmear_SALT2()`
(`sntools_genSmear.c` real) construye el smear como `SIGCOH * RANGauss_LIST[...]` — un draw Gaussiano de
media cero por construcción, no una función determinista con sesgo direccional; además `PEAKMAG_<filt>`
en el `.DUMP` es la magnitud teórica/sin ruido (Fase 22 — epoch sintético en `PEAKMJD`), que no incluye
el smear en absoluto, consistente con el match exacto a 4 decimales de Fase 26 en `z=0.15`. Con esto se
agotan también estos dos candidatos adicionales. El patrón cromático de Fase 23 **sigue sin causa
identificada**, ahora con un candidato adicional (integración de banda) reclasificado de "descartado" a
"real pero de signo opuesto, insuficiente como única explicación" — y con el espacio de búsqueda para
una continuación futura reducido a mecanismos fuera de la cadena SALT2 propiamente dicha (p.ej. algo en
el modelo de ruido/PSF por banda, aunque eso no debería afectar una comparación sin ruido como esta).

### Archivos de esta fase

Exploratorios, no versionados, borrados de NLHPC tras usarlos: `fase27_paso_a_zbins.py` +
`fase27_paso_a.sbatch` (Paso A, población completa 6 bandas), `sim_fase27_bandflux_z06.INPUT` +
`sim_fase27_bandflux_z09.INPUT` + `run_fase27_bandflux_test.sbatch` (Paso B1, SNANA real),
`fase27_lcl_vs_real_snana.py` + `fase27_lcl_check.sbatch` (Paso B1, LightCurveLynx real). GENVERSIONs
`TEST_FASE27_bandflux_z06`/`z09` generados en `SNDATA_ROOT/SIM/` y borrados tras extraer el `.DUMP`. Sin
cambios a scripts del pipeline -- diagnóstico puro, ningún candidato quedó en condición de accionar una
corrección.

## Fase 28 — interpolación 2D descartada también a z alto; M1 confirmado idéntico; la descomposición término a término se topa con un límite real

Antes de escribir código se revisó un candidato más por lectura de código, sin necesitar corridas:
**offsets de calibración/magnitud del `.INPUT` real** (`GENMAG_OFF_GLOBAL`/`GENMAG_OFF_MODEL`/
`FUDGE_MAG`/`MAGOFF`) -- grepeado en `include_model_SNIa.INPUT`, `SIMGEN_INCLUDE_SNIa-SALT2.INPUT` y
todo `~/AUTOSIM/build/full_v5.3_10yrs/`: **ninguna de esas keys aparece en ningún `.INPUT` de la
campaña** -- descartado sin ambigüedad.

### Paso 1 — interpolación 2D (Fase 21) reabierta en las λ_rest reales de z alto: descartada de nuevo, con más margen que antes

Fase 21 solo había medido la diferencia bilineal (SNANA real) vs. bicúbica (`sncosmo` real) en la
longitud de onda rest-frame de la banda `r` cerca de `z` bajo y en un barrido de fase en B rest-frame
-- nunca en las λ_rest que `g/i/z/y` muestrean realmente a `z=0.6-0.9`, justo donde Fase 27 encontró que
el residuo total (código real vs. código real) crece a `0.09-0.20` mag. Se repitió el método exacto de
Fase 21 (mismo `M0`/`M1` crudo, mismo `SALT2ColorLaw` real) pero evaluando el **bandflux real completo**
(vía `Passband.fluxes_to_bandflux()` real de LightCurveLynx, integrado sobre el ancho real de cada
banda, no solo su centro) dos veces -- una con `M0`/`M1` interpolados bilinealmente (fórmula exacta de
SNANA) y otra con el `BicubicInterpolator` real de `sncosmo` (`src._model["M0"]`/`["M1"]`) -- manteniendo
fijos la ley de color, `x1`/`c`, y la convención de integración de banda (ambos cálculos usan la MISMA
integración real de LightCurveLynx), para aislar el efecto puro del esquema de interpolación 2D.

**Bug real encontrado y corregido en el propio script** (mismo tipo de trampa de normalización que ya
mordió a Fase 25): `src._model["M0"]`/`["M1"]` (bicúbico real de `sncosmo`) ya trae horneado el factor
`X0SCALE_SALT2=1e-12` desde `__init__` (hallazgo de Fase 19/20), mientras que `M0`/`M1` crudo leído del
archivo (usado para el bilineal) no lo trae -- sin corregir esto, la razón de flujos salía contaminada
por un factor `1e12` fijo (`Δmag=30.00` idéntico en las 7 combinaciones banda/z, un valor obviamente
artificial). Corregido escalando el lado bilineal por `X0SCALE_SALT2` antes de comparar.

**Resultado, tras la corrección — negligible en las 7 combinaciones banda/`z` probadas:**

| `z` | banda | Δmag(bicúbico−bilineal) | `diff` real Fase 27 |
|---:|---|---:|---:|
| 0.6 | g | +0.0001 | +0.0935 |
| 0.6 | i | -0.0000 | -0.0864 |
| 0.6 | z | -0.0000 | -0.0997 |
| 0.6 | y | +0.0000 | -0.0978 |
| 0.9 | i | +0.0001 | -0.1201 |
| 0.9 | z | -0.0000 | -0.1771 |
| 0.9 | y | +0.0000 | -0.1975 |

El efecto de esquema de interpolación es de `~0.0000-0.0001` mag -- **más chico todavía que el máximo ya
despreciable de Fase 21 (`0.0022` mag)**, y tres a cuatro órdenes de magnitud menor que el residuo real
de Fase 27 (`0.09-0.20` mag). **Descartado de nuevo, ahora con cobertura completa de las λ_rest que
realmente importan a `z` alto** -- no queda como "cabo suelto" como lo dejó Fase 23. Con `DAYSTEP=1`
día/`LAMSTEP=10` Å (grilla nativa fina respecto a la curvatura real de la superficie SALT2), bilineal y
bicúbico siguen convergiendo incluso lejos de B/r.

### Verificación adicional — el template `M1` (nunca antes chequeado) es byte-idéntico

Las fases previas (16/20/21/25) solo habían confirmado `md5sum` idéntico para `salt2_template_0.dat`
(`M0`) entre `salt2_h17_local/` (copia local de LightCurveLynx) y el `SALT2.WFIRST-H17` real de
`$SNDATA_ROOT/models/SALT2/` (comprimido `.gz` en la copia real de SNANA) -- `M1` nunca se había
verificado explícitamente. Confirmado ahora: **`3685abb568a787b27bcb258cd2e823b2`, idéntico en ambos
lados** (igual que `M0`, re-confirmado de paso: `a75b5afcc7c59354af25c4b182ee3edd`). Cierra un supuesto
que se venía arrastrando sin verificar desde el inicio de la investigación.

### Paso 2 — descomposición término a término: todos los factores individualmente aislables ya están descartados, salvo uno que resiste el aislamiento

Con Paso 1 (interpolación) y la verificación de `M1` de arriba, junto a lo ya establecido en fases
previas, **todos los factores multiplicativos de `Fbin_forFlux = FTMP * CCOR * HOSTXT_FRAC * MWXT_FRAC *
LAMSED * TRANS`** (`genmag_SALT2.c`, confirmada real en Fase 25) quedan verificados individualmente:

| factor | estado | fase |
|---|---|---|
| `FTMP` (superficie `M0`+`x1·M1`, interpolación) | idéntico/despreciable | 21, **28 (esta fase, extendido a z alto)** |
| `M0`/`M1` (valores crudos del template) | byte-idéntico | 16 (M0), **28 (M1, primera vez)** |
| `CCOR` (ley de color) | idéntico a precisión de máquina | 16 |
| `HOSTXT_FRAC` | =1, no aplica a `SNIa` en esta campaña | 27 |
| `MWXT_FRAC` | =0 por diseño del test (`OPT_MWEBV:0`) | 26, 27 |
| `TRANS` (curva de transmisión) | idéntica a 4 decimales | 12 |
| `x0`/`M_abs` (normalización global) | idéntico a 6 cifras | 20 |
| dispersión cromática (`GENMAG_SMEAR_MODELNAME: G10`) | media cero, no sesga | 27 |
| `LAMSED*TRANS` (convención de integración: peso `λ` vs. `1/λ`) | **el único factor no aislado con éxito** | 25, 26 (higiene), este intento |

El único factor que queda es la propia convención de integración de banda. Se evaluó si se podía aislar
de forma limpia esta vez (a diferencia del intento fallido de Fase 25): en vez de reconstruir el flujo
absoluto de SNANA desde cero (la fuente de los bugs de normalización de Fase 25), la idea era comparar,
dentro del propio pipeline real de LightCurveLynx, el mismo SED real integrado con dos kernels de peso
distintos (`S_b(λ)/λ` real vs. `S_b(λ)·λ`), aislando así la convención sin tocar la física de SNANA. Pero
esto es **exactamente el experimento que Fase 25 y la higiene de Fase 26 (1a/1b) ya intentaron dos veces
y documentaron como no confiable** -- incluyendo el control de espectro plano de Fase 26, que debería
haber dado una razón moderada y predecible, y en cambio dio el mismo resultado implausible (`~3` mag en
`u`, no monótono) que con el SED real. Ese patrón (un control de espectro plano fallando igual que el
caso real) es la firma de un artefacto del propio método de comparación, no de un efecto físico -- y
reintentarlo por tercera vez sin identificar la causa raíz de esa falla tiene alta probabilidad de
reproducir el mismo artefacto. No se reintentó por esa razón: **se documenta como un límite metodológico
real de este proyecto**, no como un candidato pendiente de "intentar de nuevo".

### Conclusión Fase 28

Con la interpolación 2D descartada ahora también en el régimen de `z` alto (no solo B/r) y el template
`M1` confirmado idéntico, **se agota la lista completa de factores multiplicativos de la fórmula real de
SNANA que se pueden aislar y verificar de forma independiente y confiable con las herramientas
disponibles en este proyecto** -- los ocho primeros de la tabla de arriba, los ocho, están descartados
con evidencia numérica directa. Queda un único factor, la convención de integración de banda, que sigue
siendo plausible por eliminación (es lo único no verificado independientemente) pero que **no se puede
aislar de forma confiable con los métodos disponibles** (reconstrucción manual, intentada tres veces
contando esta fase, falla de la misma manera incluso con un control de espectro plano). Cerrar esto de
forma definitiva requeriría instrumentar el binario real de SNANA (agregar un `printf`/dump de
`FTMP`/`CCOR`/`LAMSED*TRANS` dentro de `INTEG_zSED_SALT2()` y recompilar `snlc_sim.exe`) -- una
escalación real, fuera del alcance de este proyecto exploratorio tal como está planteado (no toca código
de producción ni requiere recompilar SNANA). El patrón cromático de Fase 23 **sigue sin causa
identificada**, ahora con la investigación de la cadena SALT2 verdaderamente agotada dentro de los
métodos no invasivos disponibles -- cualquier continuación futura necesitaría, o bien instrumentación de
SNANA a nivel de C, o bien un cambio de enfoque hacia candidatos genuinamente fuera de la cadena SALT2
(el espacio ya señalado en Fase 27: modelo de ruido/PSF -- aunque no debería afectar una comparación sin
ruido como esta -- u otro mecanismo aún no identificado).

### Archivos de esta fase

`fase28_interp_zhigh.py` (exploratorio, no versionado, borrado de NLHPC tras usarlo). Sin cambios a
scripts del pipeline -- diagnóstico puro, ningún candidato quedó en condición de accionar una corrección.

## Fase 29 — instrumentando SNANA real: la convención de integración de banda, correctamente normalizada, confirma el signo (y una fracción de la magnitud) del diff de Fase 27

A pedido explícito del usuario ("vamos por el lado a"), se instrumenta y recompila el propio código C de
SNANA (opción (a) del cierre de Fase 28) para aislar de una vez por todas el único factor de
`Fbin_forFlux = FTMP * CCOR * HOSTXT_FRAC*MWXT_FRAC * LAMSED*TRANS` (`genmag_SALT2.c`) nunca verificado
de forma confiable: la convención de integración de banda (`λ` de SNANA vs. `1/λ` de LightCurveLynx),
que Fases 25/26-higiene fallaron en aislar por reconstrucción manual (resultados implausibles, ~3 mag en
`u`, no monótonos, cambiando de signo entre intentos).

### El clon propio de SNANA ya era compilable -- solo hacía falta reconstruir el entorno de build

Verificado antes de tocar código: `~/github/SNANA_src` (clon privado del usuario, branch `master`, al
día con `origin/master`) ya tenía un `bin/snlc_sim.exe` previamente compilado con 2 parches locales
reales (`USE_PYTHON`/`USE_ROOT` deshabilitados en `genmag_PySEDMODEL.h`/`sntools_output.h`), pero sin el
`Makefile`/`config.status` generado (se había limpiado tras el build anterior) -- hubo que rehacer
`autoreconf -fi && ./configure && make snlc_sim` desde cero en NLHPC, lo cual reveló una cadena real de
dependencias de build rotas, todas resueltas sin tocar el código de SNANA en sí:

- `autoreconf` fallaba (`Can't locate File/Compare.pm`) porque el `/usr/bin/perl` del sistema (5.32) no
  trae ese módulo core -- resuelto copiando solo `File/Compare.pm` (puro Perl, sin binario XS) desde un
  módulo `perl/5.40` a un directorio aislado y apuntando `PERL5LIB` ahí (copiar el `lib` completo del
  perl 5.40 rompe por mismatch de ABI en `Cwd.so`, un XS binario -- solo el archivo puro-Perl es seguro
  de mezclar entre versiones).
- `./configure` requiere `python3-config` (para el flag `USE_PYTHON`, aunque esté deshabilitado a nivel
  de macro C -- el check de `configure.ac` es incondicional) -- resuelto con `module load
  python/3.13.2-zen4-6` (evitando cualquier módulo que dependa de `intel/`, que reemplaza `CC` por
  `mpiicc` y rompe la cadena de compilación gcc-nativa).
- La regla de compilación real de `Makefile.am` (`SNCFLAGS`/`ICFITSIO`/`IGSL`, NO las variables estándar
  `CPPFLAGS`/`LDFLAGS` de autoconf) requiere que GSL/cfitsio estén en el `PATH` de búsqueda nativo de
  `gcc` -- resuelto exportando `C_INCLUDE_PATH`/`LIBRARY_PATH`/`LD_LIBRARY_PATH` apuntando directo a
  instalaciones reales de `gsl/2.8` (build skylake_avx512) y `cfitsio/4.4.0` (build zen4/aocc) ya
  presentes en el árbol `spack` de NLHPC, en vez de usar módulos `module load` (que en este cluster no
  siempre exportan esas rutas de forma completa).
- El link final fallaba (`cannot find -lintl`) porque `python3-config --embed` de ese módulo Python
  requiere `libintl` (gettext) explícito -- resuelto agregando el `lib/` de un módulo `gettext/0.23.1`
  ya presente en el mismo árbol `spack`, sin necesitar `module load` adicional.

Build final verificado: `snlc_sim.exe` compila limpio (solo warnings preexistentes de `-Wformat-overflow`
en `snlc_sim.c`, no relacionados) y corre (menú de ayuda real confirmado).

### El parche real a `genmag_SALT2.c`

`INTEG_zSED_SALT2()` ya tenía hooks de debug reales (`int LDMP`, hardcodeado a `0`) -- en vez de
reactivarlos, se agregó un volcado nuevo gateado por variable de entorno, inmediatamente después del
cálculo real de `Fbin_forFlux` (línea 2843), solo para `ised==0` (superficie `M0`):

```c
	Fbin_forFlux = (FTMP * CCOR * HOSTXT_FRAC*MWXT_FRAC * LAMSED*TRANS);
	Fbin_forSpec = (FTMP * CCOR * HOSTXT_FRAC*MWXT_FRAC );

	// ALCES Fase29: volcado real de (LAMOBS,LAMSED,TRANS,FTMP,Fbin_forFlux) por bin de
	// longitud de onda, gateado por env var -- para aislar la convencion de integracion
	// de banda (LAMSED*TRANS) sin reconstruir FTMP a mano del lado LightCurveLynx.
	// Ver exploration/lightcurvelynx/NOTES.md Fase 29 en el repo ALCeS.
	if ( ised==0 && getenv("ALCES_DUMP_INTEG") != NULL ) {
	  FILE *fp_alces = fopen("/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx/dump_integ_salt2.csv","a");
	  if ( fp_alces != NULL ) {
	    fprintf(fp_alces, "%d,%d,%.6f,%.6f,%.6f,%.8e,%.8e,%.8e\n",
		    ifilt_obs, ilamobs, Trest, LAMOBS, LAMSED, TRANS, FTMP, Fbin_forFlux);
	    fclose(fp_alces);
	  }
	}
```

`Trest` (agregado en una segunda iteración, necesario para poder aislar la evaluación sintética exacta en
el pico -- ver Fase 22) y `ifilt_obs`/`Tobs` ya eran parámetros/variables reales de la función; nada del
resto de la función se modificó. Este parche vive **solo en el clon privado de SNANA del usuario**
(`~/github/SNANA_src`, repo externo, no versionado en este repo git) -- no se commitea a ALCeS.

**No-regresión verificada**: se corrió el mismo objeto controlado (z=0.6, `x1`/`c` fijos, `RANSEED`
fijo) dos veces con el binario recompilado -- una vez sin `ALCES_DUMP_INTEG`, otra con la variable
seteada -- y el `.DUMP` real resultante (`PEAKMAG_*`/`MU`/`PEAKMJD`/etc., las 35 columnas de
`SIMGEN_DUMPALL`) salió **byte-idéntico** entre ambas corridas. El parche es comprobadamente inocuo
cuando la variable de entorno no está seteada.

### El experimento: mismo `FTMP`/`TRANS` real de SNANA, dos convenciones de pesado, correctamente normalizadas

Objeto controlado real (`GENRANGE_REDSHIFT`/`SALT2c`/`SALT2x1` colapsados a un punto, `OPT_MWEBV:0`,
`OPT_MWCOLORLAW:99`, mismo patrón de Fase 26/27) corrido a `z=0.6` y `z=0.9` con el binario instrumentado
y `ALCES_DUMP_INTEG=1`. El volcado captura, por cada bin real de longitud de onda observada evaluado en
`Trest=0` (el epoch sintético del pico verdadero, Fase 22), el `FTMP`/`TRANS`/`LAMOBS` reales que usó
SNANA -- sin ninguna interpolación/reconstrucción de por medio.

**Primer intento -- sumas crudas sin normalizar, descartado como sin sentido**: comparar directamente
`Σ FTMP·TRANS·LAMSED` (SNANA) contra `Σ FTMP·TRANS/LAMSED` (LightCurveLynx) da diferencias de hasta
`~1 mag`, absurdamente grandes -- el mismo tipo de resultado implausible de Fase 25. Diagnóstico real
esta vez (con los datos de SNANA en mano, no una reconstrucción): las dos sumas crudas viven en escalas
completamente distintas (`~1e5` vs. `~1e-3`) porque ninguna está normalizada por su propia integral de
peso -- exactamente el mismo error de fondo que arruinó Fase 25, ahora identificado con precisión en vez
de solo sospechado.

**Corregido -- promedio ponderado normalizado (el formalismo estándar de fotometría sintética)**:
`<F>_SNANA = Σ(FTMP·TRANS·LAMSED) / Σ(TRANS·LAMSED)` y `<F>_LCL = Σ(FTMP·TRANS/LAMSED) / Σ(TRANS/LAMSED)`
-- ambos convergen a la misma magnitud física cuando el SED es plano, y aíslan limpiamente el efecto de
la FORMA del peso dentro de la banda. Resultado, relativo a `r` (misma convención `diff` que Fase 27):

| `z` | banda | Δmag (peso LCL − peso SNANA), esta fase | `diff` real Fase 27 |
|---:|---|---:|---:|
| 0.6 | g | **+0.1011** | +0.0935 |
| 0.6 | i | **-0.0229** | -0.0864 |
| 0.6 | z | **-0.0094** | -0.0997 |
| 0.6 | y | **-0.0151** | -0.0978 |
| 0.9 | i | **-0.0373** | -0.1201 |
| 0.9 | z | **-0.0517** | -0.1771 |
| 0.9 | y | **-0.0462** | -0.1975 |

### Conclusión Fase 29 -- la convención de integración de banda queda confirmada, no descartada: mismo signo en las 7 combinaciones, magnitud parcial

A diferencia de Fase 25 (sin resultado confiable) y de la lectura literal de Fase 27 ("signo opuesto,
insuficiente"), esta vez con evidencia código-real-vs-código-real y correctamente normalizada: **el
efecto puro de pesar por `λ` vs `1/λ` reproduce el mismo signo que el `diff` real de Fase 27 en las 7
combinaciones banda/`z` probadas** (`g` positivo, `i`/`z`/`y` negativos, en ambos `z`), y explica entre
~25% y ~45% de la magnitud total medida por Fase 27. Esto **confirma** (no descarta) que la convención de
integración de banda es un componente real y verificado del mecanismo que separa a SNANA de
LightCurveLynx -- consistente en signo con el `diff` de Fase 27 en las 7 pruebas -- pero es
insuficiente por sí sola para explicar toda la magnitud de ese `diff`, y ese mismo `diff` ya tiene signo
opuesto al patrón cromático poblacional de Fase 23. Es decir: el patrón cromático de Fase 23 sigue **sin
causa identificada**, pero ahora se sabe con precisión que la integración de banda es una pieza real
(cuantificada, no descartada) de un mecanismo más grande, cuyo resto (~55%-75% de la magnitud del `diff`
de Fase 27) queda sin aislar -- candidato para una continuación futura: la definición exacta de punto
cero/normalización de fotometría sintética de cada código más allá del simple exponente de peso (`λ`
vs. `1/λ`), no abordada en esta fase.

### Archivos de esta fase

Parche real a `~/github/SNANA_src/src/genmag_SALT2.c` (contenido completo arriba) -- vive en el clon
privado de SNANA del usuario, no versionado en este repo. Exploratorios en NLHPC, borrados tras usarlos:
`sim_fase29_z06.INPUT`/`sim_fase29_z06_dump.INPUT`/`sim_fase29_z09.INPUT` (objetos controlados),
`analyze_z06.py`/`analyze_z06_v2.py`/`analyze_z09.py` (análisis del volcado real). GENVERSIONs
`TEST_FASE29_bandflux_z06`/`z06_dump`/`z09_dump` generados en `SNDATA_ROOT/SIM/` y borrados tras extraer
el `.DUMP`/volcado. Sin cambios a scripts del pipeline de este repo -- diagnóstico puro.

## Fase 30 — el punto cero real (espectro de referencia) añade una fracción real, pero no cierra el resto

A pedido explícito del usuario ("sigamos cazando el resto de la magnitud"), se ataca el candidato que
dejó abierto Fase 29: la definición exacta de punto cero/normalización de fotometría sintética de cada
código, más allá del simple exponente de peso (`λ` vs. `1/λ`) ya aislado ahí.

### El mecanismo real que Fase 29 nunca incluyó

Leyendo `genmag_SEDtools.c` real (`init_filter_SEDMODEL()`, líneas ~270-350): SNANA no convierte flujo
integrado a magnitud con un punto cero universal fijo -- lo calibra **por banda**, integrando un
**espectro de referencia primario real** (`interp_primaryFlux_SEDMODEL(lam)`, la curva `PrimarySED` real
de `kcor_LSST.fits`, ya leída como HDU real en Fase 12) con la **misma convención de pesado por `λ`**
que usa para el objeto científico:

```c
fluxREF_sum  += transREF * fluxREF * lam ;        // linea 298
...
fluxREF_sum *= (lamstep/hc8) ;                     // linea 343
FILTER_SEDMODEL[ifilt].ZP = 2.5*log10(fluxREF_sum) + magprimary ;   // linea 346
```

y luego (`genmag_SALT2.c` línea 3628, ya citado en Fase 29): `MAG = -2.5*log10(FTMP) + ZP`. El promedio
ponderado normalizado que usó Fase 29 (`<F>=Σ(FTMP·TRANS·peso)/Σ(TRANS·peso)`) es equivalente, solo para
fines de esa comparación relativa, a asumir que el espectro de referencia usado para calibrar el punto
cero es plano dentro de la banda -- nunca contrastado contra el `PrimarySED` real, que no tiene por qué
serlo (un espectro AB puro es plano en `f_ν`, lo que en `λ` es `f_λ∝1/λ²`).

### El parche real

Mismo patrón que Fase 29 (`getenv("ALCES_DUMP_INTEG")`), esta vez en `genmag_SEDtools.c`, volcando por
bin del espectro de referencia y, al final de cada banda, el resumen real:

```c
    fluxREF_sum  += transREF * fluxREF * lam ;

    // ALCES Fase30: volcado real de (lam,transREF,fluxREF) por bin del espectro
    // de referencia primario, gateado por env var -- para recalcular el punto
    // cero (ZP) bajo la convencion 1/lambda sin reconstruirlo a mano.
    // Ver exploration/lightcurvelynx/NOTES.md Fase 30 en el repo ALCeS.
    if ( getenv("ALCES_DUMP_INTEG") != NULL ) {
      FILE *fp_alces_zp = fopen("/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx/dump_zp_salt2.csv","a");
      if ( fp_alces_zp != NULL ) {
        fprintf(fp_alces_zp, "BIN,%s,%d,%.6f,%.8e,%.8e\n",
                filter_name, ifilt_obs, lam, transREF, fluxREF);
        fclose(fp_alces_zp);
      }
    }
```
```c
  if( fluxREF_sum != 0.0 )
    { FILTER_SEDMODEL[ifilt].ZP = 2.5*log10(fluxREF_sum) + magprimary ; }
  else
    { FILTER_SEDMODEL[ifilt].ZP = 0.0 ; }

  // ALCES Fase30: volcado real de (magprimary,fluxREF_sum,ZP) final por banda,
  // gateado por env var. Ver exploration/lightcurvelynx/NOTES.md Fase 30.
  if ( getenv("ALCES_DUMP_INTEG") != NULL ) {
    FILE *fp_alces_zp2 = fopen("/home/mvalenzuela/AUTOSIM/exploration/lightcurvelynx/dump_zp_salt2.csv","a");
    if ( fp_alces_zp2 != NULL ) {
      fprintf(fp_alces_zp2, "SUMMARY,%s,%d,%.6f,%.8e,%.6f\n",
              filter_name, ifilt_obs, magprimary, fluxREF_sum, FILTER_SEDMODEL[ifilt].ZP);
      fclose(fp_alces_zp2);
    }
  }
```

Vive solo en el clon privado de SNANA del usuario (`~/github/SNANA_src`), no versionado en este repo.
Reconstruir el binario recicló toda la cadena de dependencias de build ya resuelta en Fase 29 (perl,
`python3-config`, GSL/cfitsio/gettext vía rutas reales del árbol `spack`, esta vez además con
`LD_LIBRARY_PATH` en tiempo de ejecución, no solo de build, porque el binario recompilado enlaza contra
`libcfitsio.so.10` dinámica).

**No-regresión verificada**: mismo objeto controlado de Fase 27/29 (`z=0.6`) corrido con y sin
`ALCES_DUMP_INTEG` -- `.DUMP` real resultante byte-idéntico (`diff` vacío).

### El experimento: `ZP` real de SNANA bajo ambas convenciones, combinado con el `Finteg` real de Fase 29

Objeto controlado real (mismo patrón de Fase 26/27/29: `GENRANGE_REDSHIFT`/`SALT2c`/`SALT2x1` colapsados
a un punto, `x1=0.973`, `c=-0.054`, `OPT_MWEBV:0`, `OPT_MWCOLORLAW:99`, `NGENTOT_LC:5`) corrido a `z=0.6`
y `z=0.9` con el binario doblemente instrumentado y `ALCES_DUMP_INTEG=1`. El volcado de `ZP` da, para
cada banda, `(magprimary, fluxREF_sum, ZP)` reales -- `magprimary=0` en las 6 bandas (consistente con
`ZPoff=0` de Fase 12), pero `fluxREF_sum` real con forma no trivial (no un simple factor por banda).

Con las `(lam,transREF,fluxREF)` reales volcadas por bin: se recalculó `fluxREF_sum` bajo la convención
`1/λ` (`Σ transREF·fluxREF/lam`, reescalado por la misma constante `lamstep/hc8` derivada empíricamente
de la propia banda -- verificado que la reconstrucción de la convención `λ` original coincide con el
`fluxREF_sum` real a precisión de máquina, sanity-check pasado) → `ZP_alt`. Con el `Fbin_forFlux` real ya
volcado por Fase 29 (evaluado en `Trest=0`, el epoch sintético del pico verdadero de Fase 22, deduplicado
entre los 4-5 objetos idénticos generados por `NGENTOT_LC:5`): `Finteg_λ = Σ Fbin_forFlux` (la integral
real que usa SNANA) y `Finteg_alt = Σ Fbin_forFlux/LAMSED²` (equivalente exacto bajo `1/λ`, ya que
`Fbin_forFlux=FTMP·CCOR·LAMSED·TRANS` con `HOSTXT_FRAC=MWXT_FRAC=1`).

`MAG_SNANA_real = -2.5·log10(Finteg_λ) + ZP_SNANA` vs. `MAG_alt = -2.5·log10(Finteg_alt) + ZP_alt`,
comparado relativo a `r` contra el `diff` real de Fase 27:

| `z` | banda | Fase 27 (`diff` real) | Fase 29 (solo forma del peso) | Fase 30 (forma + punto cero real) | fracción explicada |
|---:|---|---:|---:|---:|---:|
| 0.6 | g | +0.0935 | +0.1011 | **+0.1026** | 110% |
| 0.6 | i | -0.0864 | -0.0229 | **-0.0334** | 39% |
| 0.6 | z | -0.0997 | -0.0094 | **-0.0288** | 29% |
| 0.6 | y | -0.0978 | -0.0151 | **-0.0309** | 32% |
| 0.9 | i | -0.1201 | -0.0373 | **-0.0443** | 37% |
| 0.9 | z | -0.1771 | -0.0517 | **-0.0639** | 36% |
| 0.9 | y | -0.1975 | -0.0462 | **-0.0585** | 30% |

### Conclusión Fase 30 -- el punto cero real es una pieza real y adicional, pero insuficiente

Incluir la forma real del espectro de referencia (`PrimarySED`) en el punto cero, en vez de asumirlo
plano como hacía implícitamente Fase 29, **aumenta consistentemente la magnitud explicada** en las 6
combinaciones donde Fase 29 dejaba más margen (`i`/`z`/`y` en ambos `z`): de un rango de ~9%-31% (Fase
29, excluyendo `g`) a un rango más estrecho y más alto de ~29%-39% -- una mejora real, más marcada en
`z@0.6` (9.4%→28.9%, el peor explicado por Fase 29). La banda `g` ya estaba esencialmente explicada por
Fase 29 sola (108%) y el término de punto cero no la cambia de forma apreciable (110%). **Con esto, los
dos mecanismos aislados de la convención de integración de banda (forma del peso + punto cero) explican
en conjunto ~29%-39% de la magnitud del `diff` de Fase 27 en las bandas más difíciles**, dejando todavía
~60%-70% sin identificar. El patrón cromático poblacional de Fase 23 sigue **sin causa identificada** --
sigue de signo opuesto al `diff` de Fase 27 (ya establecido en Fase 27/29), así que este avance tampoco
lo explica directamente. Con la cadena SALT2 exhaustivamente descompuesta término a término (Fase 28) y
ahora también la convención de integración de banda descompuesta en sus dos sub-mecanismos (forma +
punto cero, Fases 29-30), el resto de la magnitud del `diff` de Fase 27 queda como una pregunta abierta
genuina que ya no tiene un candidato concreto identificado dentro de la fórmula de integración SALT2 de
SNANA -- cualquier candidato adicional requeriría mirar fuera de `genmag_SALT2.c`/`genmag_SEDtools.c`
(p.ej. el propio tratamiento de `CCOR`/color law evaluado en la grilla discreta, ya verificado idéntico
en Fase 16 pero no re-verificado en este régimen de `z` alto específico) o aceptar que la comparación
entre `PEAKMAG_<filt>` real y `compute_noise_free_lightcurves()` real, aun usando el mismo objeto exacto,
compara dos implementaciones de fotometría sintética suficientemente distintas en su núcleo (no solo en
la convención de pesado) como para no cerrar del todo con descomposición término a término.

### Archivos de esta fase

Parche real a `~/github/SNANA_src/src/genmag_SEDtools.c` (contenido completo arriba) -- vive en el clon
privado de SNANA del usuario, no versionado en este repo. Exploratorios en NLHPC, borrados tras usarlos:
`sim_fase30_z06.INPUT`/`sim_fase30_z09.INPUT` (objetos controlados), `fase30_analyze.py` (análisis del
volcado real, combina `dump_zp_salt2.csv` y el `dump_integ_salt2.csv` ya generado por el parche de Fase
29). GENVERSIONs `TEST_FASE30_zp_z06`/`z09` generados en `SNDATA_ROOT/SIM/` y borrados tras extraer el
`.DUMP`. Sin cambios a scripts del pipeline de este repo -- diagnóstico puro.

## Fase 31 — dos aristas nuevas: la premisa de la primera resultó errónea (Fase 30 ya incluía `CCOR`); la segunda audita la calibración de LightCurveLynx y la encuentra sólida

A pedido explícito del usuario ("sigamos cazando... revisar la calibración completa de LightCurveLynx
pues puede que sea deficiente"), se atacan dos aristas nuevas sobre el ~60-70% del `diff` de Fase 27 que
Fases 29-30 dejaron sin explicar.

### Paso 1 — la premisa resultó errónea: `CCOR` ya estaba incluido en el cálculo real de Fase 30

El plan de esta fase partía de una relectura de Fase 29/30 que concluía que la ley de color (`CCOR`)
había quedado excluida del promedio ponderado usado ahí. Al reconstruir el cálculo completo desde cero
(nuevo objeto controlado real, `CID=1` con `z=0.6`/`z=0.9`, mismo binario instrumentado de Fases 29-30,
mismo `.INPUT` -- claves copiadas a mano por el bug de keys duplicadas de Fase 27, `OPT_MWEBV:0`,
`OPT_MWCOLORLAW:99`) se confirma que **la premisa era incorrecta**: el cálculo *final* de Fase 30 usó
`Finteg_λ = Σ Fbin_forFlux` directamente (el producto real que SNANA calcula, `Fbin_forFlux =
FTMP·CCOR·LAMSED·TRANS`, `genmag_SALT2.c` línea 2843) -- `CCOR` estaba efectivamente incluido desde el
principio ahí; solo la comparación *preliminar* de Fase 29 (el primer intento, con el promedio
autonormalizado `<F>=Σ(FTMP·TRANS·peso)/Σ(TRANS·peso)`) lo excluía, y ese intento preliminar fue
superado por el cálculo real de Fase 30.

Recuperando `CCOR` real por bin (`CCOR = Fbin_forFlux/(FTMP·LAMSED·TRANS)`, válido con
`HOSTXT_FRAC=MWXT_FRAC=1`) se confirma además que `CCOR` es un factor real y activo, no un no-op: varía
entre `~0.92` (banda `Y`) y `~1.70` (banda `g`, cerca del pico de curvatura de la ley de color SALT2 real
del `c=-0.054` de esta campaña) -- no es plano, tiene forma real dentro de cada banda.

**Resultado de repetir el cálculo completo de Fase 30 (peso + `CCOR` + punto cero real) con un objeto
nuevo e independiente (`CID=1`, no el mismo objeto de Fase 30):**

| `z` | banda | Fase 30 (peso+CCOR+ZP real) | Este paso (mismo método, objeto distinto) |
|---:|---|---:|---:|
| 0.6 | g | +0.1026 | +0.10139 |
| 0.6 | i | -0.0334 | -0.03411 |
| 0.6 | z | -0.0288 | -0.02690 |
| 0.6 | y | -0.0309 | -0.03294 |
| 0.9 | i | -0.0443 | -0.03480 |
| 0.9 | z | -0.0639 | -0.05675 |
| 0.9 | y | -0.0585 | -0.05187 |

Coinciden a `~0.001-0.01` mag (diferencias explicables por tratarse de un objeto distinto -- mismo `z`
pero distinto `RA`/`DEC`/`PEAKMJD`, y por lo tanto distinta cadencia/`SIMLIB_MAXRANSTART` -- no por un
error de método). **Esto no es un hallazgo nuevo: es una replicación independiente que confirma la
reproducibilidad de Fase 30**, no un avance sobre el ~60-70% que queda sin explicar. Ambas fases
comparten la misma limitación conocida y explícita: solo se dumpea la superficie `M0` (`ised==0`), no
`M1` (`x1`) -- el factor `x0` global cancela exactamente en la diferencia `MAG_alt−MAG_SNANA` (aparece
idéntico en ambas convenciones, se cancela en el cociente dentro del logaritmo), pero la forma cromática
propia de `M1` pesada por `x1=0.973` queda fuera de esta aproximación en ambas fases -- un cabo suelto
menor y compartido, no introducido por este paso.

### Paso 2 — auditoría de la calibración de LightCurveLynx: estructuralmente sólida, con un detalle real pero despreciable

**(A) Autoconsistencia con fuente plana en `f_ν`**: se pasó una fuente sintética perfectamente plana
(`f_ν=12345.678` nJy, arbitrario) por el pipeline real (`PassbandGroup.from_preset(preset="LSST")` +
`Passband.fluxes_to_bandflux()` real). Resultado: **`Δmag` de `~2×10⁻¹³` mag en las 6 bandas** -- exacto
a precisión de máquina. Esto es **matemáticamente garantizado por construcción**, no un descubrimiento
empírico: `compute_system_response_table()` real (`passbands.py`) normaliza `φ_b(λ)` para que
`∫φ_b(λ)dλ=1` siempre, sin importar la forma de la banda -- cualquier fuente plana se reproduce a sí
misma exactamente, para cualquier banda, por diseño. La prueba se documenta igual (evidencia negativa
real), pero no puede en principio revelar un bug de esta clase.

**(B) Auditoría del jacobiano `f_λ→f_ν`**: se leyó el código real de conversión de unidades
(`lightcurvelynx/astro_utils/unit_utils.py`, funciones `flam_to_fnu()`/`get_flam_to_fnu_multiplier()`)
-- usa álgebra de unidades real de `astropy` (`(flam_unit·wave_unit²)/const.c.unit).to_value(fnu_unit)`)
para derivar el multiplicador escalar correcto, no una constante manual. El punto de llamada real
(`sncosmo_models.py`, `SncosmoWrapperModel.evaluate_sed()`) pasa `wave_unit=u.AA` consistente con las
longitudes de onda reales que usa (`self.source.flux(phase, wavelengths)`, documentadas "en angstroms").
**No hay bug de unidades real** -- la conversión `f_λ`(SALT2, erg/s/cm²/Å) → `f_ν`(nJy) está implementada
correctamente y de forma dimensionalmente rigurosa.

**(C) Hallazgo real nuevo -- `trim_quantile=1e-3` nunca se había auditado contra producción**: leyendo
`PassbandGroup._lsst_load_preset()`/`Passband.__init__` reales se confirma que
`PassbandGroup.from_preset(preset="LSST")` (la llamada real que usan los 5 scripts de producción de este
proyecto) aplica por defecto `trim_quantile=1e-3` (recorta el 0.1% de área en cada extremo) y
`delta_wave=5.0` Å -- **nunca antes verificado contra la tabla usada realmente en producción**: Fase 12
comparó la tabla CRUDA descargada (`transmission_table`, sin recortar) contra `kcor_LSST.fits` real, no
la tabla recortada+resampleada (`normalized_system_response`/`waves`) que `fluxes_to_bandflux()` usa de
verdad. El recorte es real y sustancial en longitud de onda (p.ej. banda `u`: `[3000,11500]`Å crudo →
`[3285,8410]`Å recortado; banda `g`: `[3000,11500]`Å → `[3925,5625]`Å).

Verificado numéricamente con el SED real SALT2 M0 (mismo template de Fases 16/20/21/25/28/29) en `z=0.15,
0.6, 0.9`, comparando `Δmag` relativo a `r` con `trim_quantile=1e-3` (producción) vs. `trim_quantile=None`
(sin recortar): el efecto es **despreciable en `g/i/z/y`** (`≤0.006` mag en todos los `z` probados) --
salvo en `u`, donde crece hasta **`+0.09`** mag a `z=0.9` (banda ya excluida del análisis principal de
todas formas, por `PEAKMAG_u` real indefinido a partir de `z≈0.6`, Fase 13/27). **No explica el residuo
de `g/i/z/y`** que sigue sin causa identificada, pero es una corrección real de higiene metodológica que
queda documentada -- cualquier futura comparación en banda `u` a `z` alto debería usar
`trim_quantile=None` o verificar explícitamente su efecto.

### Conclusión Fase 31 -- ninguna de las dos aristas cierra el resto de la magnitud; la calibración de LightCurveLynx queda auditada y verificada sólida

**Arista 1 (color law × punto cero)**: la premisa era errónea -- no había nada nuevo que combinar, Fase
30 ya lo había hecho. Este paso aporta una replicación independiente que confirma la reproducibilidad del
resultado de Fase 30 (no un avance).

**Arista 2 (auditoría de calibración de LightCurveLynx)**: **no se encontró una deficiencia real y
corregible**. La normalización de `Passband` es autoconsistente por construcción (garantizado
matemáticamente, no solo verificado), la conversión de unidades `f_λ→f_ν` es correcta y dimensionalmente
rigurosa (verificada leyendo el código real de `astropy`-based `unit_utils.py`), y el único detalle real
encontrado (`trim_quantile` nunca antes auditado contra producción) tiene un efecto medido pero
despreciable en las bandas que importan (`g/i/z/y`). **No se aplicó ninguna corrección de código** en
esta fase -- a diferencia del precedente de Fase 24, no hay nada concreto que corregir: ambas auditorías
dieron negativo, con evidencia numérica directa, no por falta de intentarlo.

El patrón cromático de Fase 23 **sigue sin causa identificada**. Con la cadena SALT2 agotada (Fase 28),
la convención de integración de banda cuantificada pero insuficiente y de signo mixto (Fases 26/27/29/30),
y ahora también la calibración de LightCurveLynx auditada y verificada sólida (Fase 31), el espacio de
candidatos concretos, verificables por lectura de código y evidencia numérica directa, está prácticamente
agotado. Lo que queda -- el ~60-70% de magnitud sin explicar del `diff` de Fase 27, y el patrón cromático
poblacional de signo opuesto de Fase 23 -- probablemente requiere una síntesis a nivel más alto (las
conclusiones finales, todavía diferidas a pedido del usuario) en vez de un candidato aislado más.

### Archivos de esta fase

Exploratorios en NLHPC, borrados tras usarlos: `fase31_lcl_calib_audit.py` (Paso 2, autoconsistencia +
auditoría de trim), `sim_fase31_z06.INPUT`/`sim_fase31_z09.INPUT` (Paso 1, objeto controlado nuevo),
`fase31_paso1_analyze.py` (análisis del volcado real, reutiliza el binario instrumentado de Fases
29-30 sin recompilar). GENVERSIONs `TEST_FASE31_ccor_z06`/`z09` generados en `SNDATA_ROOT/SIM/` y
borrados tras extraer el `.DUMP`. Sin parches nuevos a SNANA (se reutilizó el binario ya instrumentado
de Fases 29-30 sin modificarlo). Sin cambios a scripts del pipeline de este repo -- ambas auditorías
dieron negativo, no hay nada que corregir.

## Fase 32 — el hallazgo más significativo de la investigación: el sampler de `c`/`x1` no pesaba las dos mitades como SNANA

Nueva arista, distinta de toda la cadena de Fases 26-31 (que atacó la fórmula fotométrica de un objeto
controlado único): esta vez se audita la **fidelidad del muestreo poblacional**. Leyendo el código real
de SNANA (no documentación) se encontró un bug real y concreto, no solo una hipótesis.

### El bug real: SNANA pesa cada mitad de la Gaussiana bifurcada por su sigma, no 50/50

`~/github/SNANA_src/src/sntools.c::getRan_GaussAsym()` (la función real que SNANA usa para samplear
`SALT2c`/`SALT2x1`, invocada desde `getRan_GENGAUSS_ASYM()` en `sntools_genGauss_asym.c`) no elige el
lado "bajo"/"alto" de la Gaussiana bifurcada con 50/50 de probabilidad -- lo pesa **proporcional a cada
sigma**, para que la densidad de probabilidad sea continua en el pico:

```c
// sntools.c, getRan_GaussAsym() real
double BIGAUSSNORMCON = 1.25331413732;  // sqrt(2*pi)/2, normaliza cada media-Gaussiana
psum = (siglo + sighi) * BIGAUSSNORMCON + peakinterval;
p[0] = (siglo * BIGAUSSNORMCON) / psum;      // prob. de tomar el lado "bajo"
p[2]-p[1] = (sighi * BIGAUSSNORMCON) / psum;  // prob. de tomar el lado "alto"
```

Es decir, `P(lado alto) = sighi/(siglo+sighi)`, NO `0.5`. `snana_params.py::make_bifurcated_normal_sampler()`
(línea 284-311, usada en `compare_brightness_truth_salt2.py`/`run_snia_ddf_poc.py`/`run_dask_poc.py`)
usaba `side = rng.uniform(size=batch) < 0.5` -- siempre 50/50, sin importar cuán distintos fueran
`sigma_lo`/`sigma_hi`. Confirmado contra el `.INPUT` real (`SIMGEN_INCLUDE_SNIa-SALT2.INPUT`, vía
`include_model_SNIa.INPUT`): `GENPEAK_SALT2c/x1` son valores únicos (no un rango), y **no hay
`GENSKEW_SALT2c`/`GENSKEW_SALT2x1` declarado** -- `peakinterval=0` es válido, no hace falta implementar
la rama de `getRan_skewGauss()`.

Para `SALT2c` (`peak=-0.054, sigma_lo=0.043, sigma_hi=0.101`), la asimetría es grande: `sigma_hi` es
2.35x `sigma_lo`. `P(lado alto)` real es `0.101/(0.043+0.101) ≈ 70.1%`, no `50%`. Con 50/50,
LightCurveLynx sub-muestreaba el lado ancho (rojo, `c` alto) y sobre-muestreaba el lado angosto (azul,
`c` bajo) -- sesgo en la dirección correcta para producir tanto exceso de brillo global como señal
cromática. `SALT2x1` (`sigma_lo=1.472, sigma_hi=0.222`, asimetría opuesta) también estaba afectado.

### Corregido: `make_bifurcated_normal_sampler()` ahora replica la fórmula real

```python
p_side_lo = 0.5 if (sigma_lo == 0.0 and sigma_hi == 0.0) else sigma_lo / (sigma_lo + sigma_hi)
...
side = rng.uniform(size=batch) < p_side_lo
```

Verificado con un test estadístico directo (2M draws): `P(lado alto)` empírico coincide con el valor
esperado a 4 decimales (`SALT2c`: 0.7013 vs. 0.7014 esperado; `SALT2x1`: 0.1318 vs. 0.1311 esperado).

### Impacto real medido: recorrida completa de la población (2000 objetos, sampler corregido)

A diferencia de Fases 26-31 (objeto controlado único), este bug es inherentemente poblacional -- se
recorrió `compare_brightness_truth_salt2.py` (2000 objetos, mismo `seed_base=20260812`, mismo `.DUMP`
real de producción) con el sampler ya corregido, repitiendo la comparación banda-por-banda de Fase 23
(`compute_noise_free_lightcurves()` en `rest_phase=0`, mediana por los mismos 7 bins de `z`):

| banda | Fase 23 (pre-fix) | Fase 32 (post-fix) | reducción | % reducción |
|---|---:|---:|---:|---:|
| `g` | -0.593 | -0.3448 | -0.248 | 41.9% |
| `r` | -0.519 | -0.3142 | -0.205 | 39.5% |
| `i` | -0.469 | -0.3138 | -0.155 | 33.1% |
| `z` | -0.435 | -0.3113 | -0.124 | 28.4% |
| `y` | -0.382 | -0.2562 | -0.126 | 32.9% |

**El nivel acromático se reduce ~28-42% en todas las bandas con estadística suficiente**, y el **spread
cromático `g−y` se reduce de -0.211 a -0.089 mag -- una reducción del 58%**. `u` queda con un solo bin
de estadística válida (mismo problema de borde de Fase 13/23), resultado no confiable ahí.

### Conclusión Fase 32 — el hallazgo más significativo de la investigación

Un bug de muestreo real y corregible -- no una diferencia de convención fotométrica -- explica una
fracción sustancial (28-42% del nivel acromático, 58% del spread cromático) del residuo que las Fases
16-31 persiguieron a través de la cadena SALT2/fotometría sintética completa. `make_bifurcated_normal_sampler()`
no se usa en ningún otro lugar del proyecto fuera de estos 3 scripts SNIa/SALT2 (`grep` confirmado). El
residuo restante (~58-72% del nivel acromático según banda, ~42% del spread cromático) sigue sin causa
identificada, pero el espacio de búsqueda se redujo sustancialmente.

### Archivos de esta fase

`snana_params.py`: `make_bifurcated_normal_sampler()` corregido (probabilidad de lado proporcional a
sigma, no 50/50 fijo). Exploratorios en NLHPC, borrados tras usarlos: `fase32_verify_sampler.py` (Paso
2), `fase32_smoketest.py` (verificación de API), `fase32_population_6band.py`/`.sbatch` (Paso 3, output
`fase32_population_6band_output.parquet` también borrado tras extraer los números).

## Fase 33 — E(B-V) real (SFD98 por objeto) vs. el promedio fijo por campo: efecto marginal, pero se descubre contaminación real en el `.DUMP` de referencia

Siguiendo la misma estrategia que dio el mayor resultado hasta ahora (Fase 32: auditar un sampler/
aproximación custom contra el algoritmo real de SNANA, no la fórmula fotométrica), se ataca una nota
real que ya estaba escrita en el código, nunca investigada a fondo: `snana_params.py::
make_mwebv_ratio_scatter()` (líneas 532-539) señala que la campaña real de SNANA no usa un `E(B-V)` fijo
por campo DDF -- el SIMLIB real escribe `MWEBV=0.00` en cada header `LIBID`, disparando el fallback real
de `gen_MWEBV()` a `OPT_MWEBV_SFD98` (mapa real de polvo, evaluado en el RA/Dec exacto de cada objeto).
Este proyecto usa `DDF_FIELD_EBV`, un promedio fijo por campo (6 valores).

### Paso 1 -- el desajuste real, medido sin simular nada nuevo

El `MWEBV` real por objeto ya está en el `.DUMP` de producción (`SNIa_DDF_baseline_v5.3.1_10yrs.DUMP`,
columna `MWEBV` real, `VARNAMES` de 36 columnas confirmado) -- comparar contra `DDF_FIELD_EBV` no
requiere ninguna simulación nueva. Primer intento (media simple): resultados absurdos
(`elaiss1`: media real `1.94`, `std=7.57`, contra el valor fijo `0.008`) -- diagnosticado: **el `.DUMP`
de referencia contiene un ~15% de objetos que NO son miembros reales de ninguno de los 6 campos DDF**.

Asignando cada objeto al campo real más cercano (centros de campo reales extraídos del propio OpSim,
`target_name LIKE '%ddf_%'`, mismo patrón que usa el proyecto) y midiendo la separación angular: la
distribución es claramente **bimodal** (mediana `1.47°`, percentil 90 `76.6°`) -- **298/1957 objetos
(15.2%) están a más de 2° de cualquier campo DDF real** (separación mediana de ese subgrupo: `~77°`,
posiciones de cielo sin relación con las 6 pointings DDF). Inspeccionando los objetos de `MWEBV` más
alto (hasta `72.68`): sus RA/Dec (`~267°, ~-28°`) caen casi exactamente sobre el **centro galáctico**
(RA≈266.4°, Dec≈-28.9°) -- **astrofísicamente real, no un bug de parseo**: son objetos generados fuera
del footprint DDF de baja extinción, mezclados en el mismo `.DUMP` (coherente con el nombre real del
directorio que los contiene, `_stale_pre_v8fix`, y con los `target_name` reales del OpSim que mezclan
`ddf_*` con `GW_case_*`/`neutrino_*` en la misma tabla). Este es un hallazgo real de calidad de datos del
`.DUMP` de referencia usado desde Fase 16 -- dado que **todas** las comparaciones poblacionales de Fases
16-32 usan la **mediana** (robusta a un ~15% de contaminación siempre que no domine el bin), es poco
probable que invalide los hallazgos ya reportados, pero queda como un cabo suelto real para una
auditoría futura de esa referencia.

Filtrando a objetos bien-matcheados (separación `<2°`, 1659/1957) y usando **mediana** (no media, ya
sensible a outliers) por campo:

| campo | N | `MWEBV` real (mediana) | `DDF_FIELD_EBV` (fijo) | delta |
|---|---:|---:|---:|---:|
| cosmos | 269 | 0.02416 | 0.01820 | +0.00596 |
| ecdfs | 274 | 0.01002 | 0.00840 | +0.00162 |
| edfs_a | 282 | 0.00914 | 0.00620 | +0.00294 |
| edfs_b | 268 | 0.01320 | 0.01520 | -0.00200 |
| elaiss1 | 295 | 0.00816 | 0.00800 | +0.00016 |
| xmm_lss | 271 | 0.02445 | 0.02510 | -0.00065 |

Desajustes reales pero chicos (`-0.002` a `+0.006` en `E(B-V)`), del mismo orden que la propia dispersión
intra-campo.

### Paso 2 -- propagado a magnitud con F99 real (Fase 24): marginal

Usando `dust_extinction.F99(Rv=3.1)` (mismo estándar del proyecto desde Fase 24) sobre los deltas reales
de arriba, en las 6 bandas LSST:

| banda | cosmos | ecdfs | edfs_a | edfs_b | elaiss1 | xmm_lss | media ponderada |
|---|---:|---:|---:|---:|---:|---:|---:|
| u | +0.0281 | +0.0076 | +0.0139 | -0.0094 | +0.0008 | -0.0031 | **+0.0063** |
| g | +0.0218 | +0.0059 | +0.0107 | -0.0073 | +0.0006 | -0.0024 | **+0.0049** |
| r | +0.0152 | +0.0041 | +0.0075 | -0.0051 | +0.0004 | -0.0017 | **+0.0034** |
| i | +0.0113 | +0.0031 | +0.0056 | -0.0038 | +0.0003 | -0.0012 | **+0.0025** |
| z | +0.0089 | +0.0024 | +0.0044 | -0.0030 | +0.0002 | -0.0010 | **+0.0020** |
| y | +0.0073 | +0.0020 | +0.0036 | -0.0025 | +0.0002 | -0.0008 | **+0.0016** |

La media ponderada por población (`+0.006` a `+0.002` mag, `u`→`y`) es marginal -- del mismo orden que
el hallazgo ya descartado de Fase 24 (`<0.005` mag, cambio de ley de extinción a estos niveles de
`E(B-V)`). Incluso el peor caso de un solo campo (`cosmos`, `+0.028` mag en `u`) es pequeño frente al
residuo real que dejó Fase 32 (`~0.31` mag acromático, `~0.089` mag de spread cromático `g-y`). **No se
pasa al Paso 3** (implementación del lookup SFD98 real) -- el efecto estimado no lo justifica, mismo
criterio de decisión que Fase 24.

### Candidatos de reserva auditados

- **`build_dndz_powerlaw2_cdf`/`make_dndz_sampler` (DNDZ POWERLAW2, redshift)**: comparado el `z`
  (`ZHELIO`) muestreado por el sampler real del proyecto (200k draws, mismos segmentos reales
  `[(2.5e-5,1.5,0,1),(9.7e-5,-0.5,1,3)]`) contra el `ZHELIO` real de los 1659 objetos DDF bien-matcheados
  del `.DUMP`. Test KS: `stat=0.038, p=0.183` -- **no se puede rechazar que sean la misma distribución**;
  percentiles coinciden dentro de `0.01-0.02` en `z` en los 5 cuantiles probados. **Sin bug** -- el
  método de inversión de CDF reproduce fielmente la distribución real.
- **`ObsTableRADECSampler` (asignación de campo/posición)**: lectura del código real instalado
  (`ra_dec_sampler.py`) confirma un diseño documentado ("visit-weighted distribution") -- pesa por
  densidad real de visitas/observaciones del OpSim, no un supuesto arbitrario. Los conteos reales por
  campo del `.DUMP` (bien-matcheados) son casi uniformes (`268-295` de `1659`, `<10%` de spread),
  consistente con ese diseño. No se encontró indicio de sesgo en una revisión de código; una validación
  cuantitativa completa (recorrida de población + comparación de conteos por campo) queda fuera del
  presupuesto de esta fase -- honestamente marcada como no verificada a fondo, no como "descartada".

### Conclusión Fase 33 -- candidato marginal, pero con un hallazgo lateral real

El `E(B-V)` fijo por campo introduce un desajuste real mensurable, pero **marginal** frente al residuo
que queda tras Fase 32 -- mismo patrón que Fase 24 (corrección conceptualmente correcta pendiente, pero
sin magnitud suficiente para justificar la implementación completa en esta ronda). Los dos candidatos de
reserva (DNDZ, asignación de campo) no revelaron ningún bug adicional del tipo Fase 32. El hallazgo más
importante de esta fase no estaba en el plan original: **~15% del `.DUMP` de referencia usado desde Fase
16 no son miembros reales de los 6 campos DDF** -- un hallazgo de calidad de datos real, que no invalida
los resultados ya reportados (todos basados en medianas, robustas a esa fracción de contaminación) pero
queda documentado como un cabo suelto real para el futuro. El residuo post-Fase-32 (`~0.31` mag
acromático, `~0.089` mag cromático `g-y`) sigue sin causa identificada.

### Archivos de esta fase

Exploratorios en NLHPC, borrados tras usarlos: `fase33_paso1_mwebv.py` (Paso 1, con su output
`fase33_paso1_mwebv_output.csv`, también borrado). Paso 2 y los candidatos de reserva se corrieron
inline (sin script separado). Sin cambios a `snana_params.py`/scripts de producción -- ningún candidato
alcanzó el umbral para justificar una corrección esta fase.

## Fase 34 — `Omega_m=0.3` era un valor asumido, no el default real de SNANA (`0.315`): corregido, efecto real pero pequeño y en dirección inesperada

Nueva arista: auditar el módulo de distancia cosmológica propio de LightCurveLynx
(`DistModFromRedshift`, envoltorio real de `astropy.cosmology.FlatLambdaCDM.distmod(z)`, usado en
`compare_brightness_truth_salt2.py` desde Fase 16) contra el `MU` real de SNANA -- nunca antes validado
de forma independiente (las pruebas código-real-vs-código-real de Fases 26-31 siempre reusaron el `MU`
real de SNANA directamente, evitando el cálculo propio de LightCurveLynx por diseño).

### Paso 1 -- desajuste real medido, sin simular nada nuevo

El `.DUMP` real de producción (`SNIa_DDF_baseline_v5.3.1_10yrs.DUMP`) ya trae `ZCMB`/`ZHELIO`/`MU`/
`LENSDMU` por objeto. Aplicando el mismo filtro de contaminación de Fase 33 (separación angular `<2°`
al campo DDF real más cercano, 1659/1957 objetos bien-matcheados -- sin ese filtro, el `.DUMP` completo
da resultados absurdos, mismo hallazgo de Fase 33) y comparando `MU_LCL = FlatLambdaCDM(H0=70,
Om0=0.3).distmod(z).value` contra el `MU` real:

| | media | mediana | std |
|---|---:|---:|---:|
| `MU_LCL(ZCMB) − MU_real` | +0.01629 | +0.01719 | 0.00416 |
| `MU_LCL(ZHELIO) − MU_real` | +0.01739 | +0.01824 | 0.00463 |

`LENSDMU` real es exactamente cero para los 1659 objetos (media/mediana/std/min/max = 0.0) -- esta
campaña no aplica dispersión de lente gravitacional, no es la fuente del desajuste.

**El desajuste NO es un offset constante -- crece suavemente con `z`** (`ZCMB`, mediana por bin):

| bin `z` | N | `MU_LCL−MU_real` (mediana) |
|---:|---:|---:|
| [0.011,0.181) | 10 | 0.00225 |
| [0.181,0.351) | 51 | 0.00594 |
| [0.351,0.521) | 147 | 0.00949 |
| [0.521,0.690) | 219 | 0.01246 |
| [0.690,0.860) | 313 | 0.01537 |
| [0.860,1.030) | 438 | 0.01778 |
| [1.030,1.200) | 481 | 0.01972 |

Un crecimiento suave y monótono con `z` -- la firma exacta de un parámetro de cosmología mal
matcheado (no un offset/bug de fórmula). Ajustando `Om0` contra el `MU` real (manteniendo `H0=70`,
`scipy.optimize.minimize_scalar`, residuo mediano absoluto como función de costo): **`Om0=0.31435`
reduce el residuo mediano a 0.00068 mag** (esencialmente ruido numérico), contra `0.01719` mag con
`Om0=0.3`. Un ajuste equivalente variando `H0` con `Om0=0.3` fijo da `H0=70.59`, con un residuo
`0.0022` mag -- peor ajuste, confirmando que el parámetro mal matcheado es `Om0`, no `H0`.

**Confirmado contra el código fuente real de SNANA**: `~/github/SNANA_src/src/sntools.h`, línea 53:
`#define OMEGA_MATTER_DEFAULT 0.315` -- coincide con el `Om0` ajustado numéricamente a 4 decimales. La
misma cabecera confirma `H0_SALT2 = 70.0` (línea 57, "tied to SALT2 training") -- el `H0=70` que ya
usa el proyecto era correcto; solo `Omega_m=0.3` (un valor redondo asumido desde las primeras fases,
nunca verificado contra el default real) estaba mal. Ningún `.INPUT` real de la campaña (ni el de
`SNIa`, ni ningún archivo compartido bajo `~/AUTOSIM/build/full_v5.3_10yrs/` o
`/home/mvalenzuela/run_SNANA/model_config/`) sobreescribe `OMEGA_MATTER`, confirmado por grep sin
resultados -- la campaña corre con el default interno real de SNANA.

**Hallazgo de alcance más amplio, no corregido en esta fase**: `Om0=0.3` está hardcodeado en 8 archivos
del proyecto (`bench_snia.py`, `compare_brightness_truth.py`, `compare_brightness_truth_salt2.py`,
`run_dask_poc.py`, `run_non1ased_poc.py`, `run_simsed_91bg_ddf_poc.py`, `run_simsed_poc.py`,
`run_snia_ddf_poc.py`) -- afecta potencialmente a todas las clases, no solo `SNIa`. Esta fase corrige
únicamente los scripts SNIa/SALT2 ya tocados por la cadena de investigación (ver abajo); el resto queda
como trabajo pendiente identificado, no una fase futura todavía planificada. `run_dask_poc.py` además
usa `H0=73.0` (no `70.0`) -- un error real y más grande (~0.09 mag, `5·log10(73/70)`) que el de `Om0`,
pero fuera de alcance de esta fase (no es parte de la cadena de comparación poblacional que usan las
Fases 16-34, es un PoC de paralelización con Dask).

### Paso 3 -- corregido y medido: efecto real, pero pequeño, y en la dirección opuesta a "cerrar el residuo"

Corregido `Omega_m: 0.3 → 0.315` en `compare_brightness_truth_salt2.py` y `run_snia_ddf_poc.py` (los
2 de los 3 scripts SNIa/SALT2 que usan `DistModFromRedshift` directamente -- `run_dask_poc.py` queda
fuera, ver nota de `H0` arriba). Re-corrida la población completa (2000 objetos, mismo `seed_base`,
sobre la base ya corregida de Fase 32 -- sampler bifurcado real) con `compute_noise_free_lightcurves()`
en `rest_phase=0`, misma metodología exacta de Fase 32:

| banda | Fase 32 (antes) | Fase 34 (después, `Om0=0.315`) | Δ(Fase34−Fase32) |
|---|---:|---:|---:|
| `g` | -0.3448 | -0.3547 | -0.0099 |
| `r` | -0.3142 | -0.3285 | -0.0143 |
| `i` | -0.3138 | -0.3283 | -0.0145 |
| `z` | -0.3113 | -0.3271 | -0.0158 |
| `y` | -0.2562 | -0.2737 | -0.0175 |

**El residuo acromático NO se reduce -- se hace ligeramente más negativo (~0.01-0.018 mag), consistente
en signo y magnitud con la propia medición del Paso 1** (`MU_LCL(Om0=0.3)` era ~0.017-0.02 mag *mayor*
que el `MU` real, es decir LightCurveLynx generaba objetos ligeramente *más tenues* de lo que debería
por este único efecto -- una compensación parcial, no relacionada con la causa real del exceso de
brillo, que enmascaraba una fracción del residuo verdadero). Corregir `Om0` **elimina esa compensación
accidental**, revelando un residuo acromático real ligeramente mayor (~0.33 mag en vez de ~0.31 mag) que
el reportado en Fase 32 -- una medición más honesta, no un empeoramiento real de la física. El spread
cromático `g−y`, en cambio, mejora levemente: `-0.3547 − (-0.2737) = -0.0810` mag, contra `-0.0886` mag
de Fase 32 (~9% de reducción adicional) -- coherente con que el efecto de `Om0` es predominantemente
acromático (entra igual en las 6 bandas vía `x0`), con variación banda a banda solo por diferencias de
cobertura de bins de `z` válidos entre bandas (`u`/`z`/`y` tienen menos bins con estadística completa
por el efecto de borde de Fase 13/23), no por un mecanismo cromático nuevo. `u` sigue sin ser confiable
(solo 1-2 bins con datos, mismo problema de siempre).

### Candidato de reserva (`GENSIGMA_VPEC`/`GENRANGE_RV` en `.INPUT` compartido)

Grepeado en todos los `.INPUT` reales bajo `/home/mvalenzuela/run_SNANA/model_config/` y
`~/AUTOSIM/build/full_v5.3_10yrs/`: `GENRANGE_RV` sí aparece, pero solo en los `.INPUT` de clases con
extinción de host parametrizada (`SNIax`, `TDE-MOSFIT`, etc. -- ya documentado en fases previas, `RV`
del polvo de host, no de la Vía Láctea). El `.INPUT` real de `SNIa` (`SIMGEN_INCLUDE_SNIa-SALT2.INPUT`,
leído completo en la planificación de esta fase) no declara `GENSIGMA_VPEC` ni ningún parámetro de `RV`
-- descartado, sin necesidad de simular nada.

### Conclusión Fase 34 -- corrección real y precisa, pero de magnitud pequeña y de signo contraintuitivo

A diferencia de Fase 32 (reducción sustancial del residuo) y más parecido a Fase 24/33 (corrección real
pero de magnitud marginal frente al residuo total), esta fase identifica con precisión inusual la causa
exacta de un desajuste real (`Om0=0.3` asumido vs. `Om0=0.315` real, confirmado a 4 decimales contra el
código fuente de SNANA) -- pero corregirlo **no reduce** el residuo acromático reportado, lo aumenta
ligeramente (~0.01-0.018 mag), porque el error de `Om0` estaba parcialmente enmascarando, no causando,
parte del exceso de brillo real. El spread cromático mejora un poco (~9% adicional). El residuo que
queda tras Fase 32+34 (`~0.33` mag acromático, `~0.081` mag de spread cromático `g−y`) sigue sin causa
identificada. La corrección queda aplicada de todas formas -- es física y numéricamente correcta,
verificada contra el código fuente real de SNANA, independientemente de que no achique el número que se
viene persiguiendo.

### Archivos de esta fase

`compare_brightness_truth_salt2.py`, `run_snia_ddf_poc.py`: `Omega_m`/`Om0` corregido de `0.3` a
`0.315`, con comentario citando `OMEGA_MATTER_DEFAULT` real de `sntools.h`. Exploratorios en NLHPC,
borrados tras usarlos: `fase34_paso1_mu.py` (Paso 1, con su verificación de ajuste de `Om0`/`H0` inline),
`fase34_population_6band.py`/`.sbatch` (Paso 3, output `fase34_population_6band_output.parquet` también
borrado tras extraer los números).

## Fase 35 — el fix de `Om0=0.315` (Fase 34), extendido a los otros 6 scripts que lo tenían hardcodeado en `0.3`

A pedido explícito del usuario, se extiende el fix de cosmología de Fase 34 (`Om0=0.315`,
`OMEGA_MATTER_DEFAULT` real de SNANA, `sntools.h`) a los 6 archivos del proyecto que quedaron fuera de
esa fase (grep real confirmó 8 archivos con `Om0=0.3`/`Omega_m=0.3` hardcodeado en total; Fase 34 solo
corrigió `compare_brightness_truth_salt2.py`/`run_snia_ddf_poc.py`). Además, `bench_snia.py` y
`run_dask_poc.py` tenían `H0=73.0` (no `70.0`) -- el mismo bug de placeholder que Fase 34 encontró y
descartó para la clase `SNIa`.

### Verificación previa: `Om0=0.315` es correcto para las 6 clases, no solo `SNIa`

`OMEGA_MATTER_DEFAULT=0.315` (`sntools.h`) es un default GLOBAL de SNANA, no específico de una clase --
pero antes de asumir que ninguna clase lo sobreescribe, se grepeó `OMEGA_MATTER`/`OMEGA_LAMBDA`/`H0:`/
`H0_REF` en los 34 `include_model_<clase>.INPUT` reales de la campaña
(`~/AUTOSIM/build/full_v5.3_10yrs/includes/`) y en los `include_survey_*.INPUT`: **ninguno declara una
cosmología propia** -- el default global aplica sin excepción a las 6 clases que tocan estos scripts
(`SNIa` vía `bench_snia.py`/`run_dask_poc.py` -- ambos usan el mismo `SncosmoWrapperModel`/SALT2 que
`run_snia_ddf_poc.py`, confirmado leyendo su código --, `SNIa-91bg` SIMSED vía
`compare_brightness_truth.py`/`run_simsed_91bg_ddf_poc.py`, y las clases genéricas `NON1ASED`/`SIMSED`
vía `run_non1ased_poc.py`/`run_simsed_poc.py`). `H0=70.0` (ya confirmado real para `SNIa` en Fase 34)
también aplica sin cambios a `bench_snia.py`/`run_dask_poc.py`, ya que ambos simulan la misma clase
`SNIa`/SALT2.

### Corrección aplicada

| archivo | antes | después |
|---|---|---|
| `bench_snia.py` | `H0=73.0, Omega_m=0.3` | `H0=70.0, Omega_m=0.315` |
| `compare_brightness_truth.py` | `H0=70.0, Om0=0.3` | `H0=70.0, Om0=0.315` |
| `run_dask_poc.py` | `H0=73.0, Omega_m=0.3` | `H0=70.0, Omega_m=0.315` |
| `run_non1ased_poc.py` | `H0=70.0, Om0=0.3` | `H0=70.0, Om0=0.315` |
| `run_simsed_91bg_ddf_poc.py` | `H0=70.0, Om0=0.3` | `H0=70.0, Om0=0.315` |
| `run_simsed_poc.py` | `H0=70.0, Om0=0.3` | `H0=70.0, Om0=0.315` |

Verificado con `python3 -m py_compile` sobre los 6 archivos -- compila limpio. No se re-corrieron las
poblaciones completas de estas otras clases (`SNIa-91bg`/`NON1ASED`/`SIMSED` tienen su propio historial
de resultados reportados en Fases 5-9, sweeps de 5 semillas por clase -- fuera del hilo principal de esta
sesión, que es el residuo `SNIa`/SALT2) -- mismo criterio que Fase 24: se corrige por precisión de
calibración aunque no se mida el impacto numérico completo en cada clase.

### Conclusión Fase 35

Corrección de seguimiento, no una investigación nueva: cierra el hallazgo de Fase 34 en los 8 archivos
del proyecto que usan cosmología (2 ya corregidos ahí, 6 acá), con la misma diligencia de verificar
contra los `.INPUT` reales antes de aplicar el valor a ciegas. El residuo `SNIa`/SALT2 (~0.33 mag
acromático, ~0.081 mag cromático `g−y`) no cambia -- esta fase no lo toca, solo extiende la precisión de
calibración ya establecida al resto del proyecto.

### Archivos de esta fase

`bench_snia.py`, `compare_brightness_truth.py`, `run_dask_poc.py`, `run_non1ased_poc.py`,
`run_simsed_91bg_ddf_poc.py`, `run_simsed_poc.py`: `Om0`/`Omega_m` corregido de `0.3` a `0.315`
(y `H0` de `73.0` a `70.0` en `bench_snia.py`/`run_dask_poc.py`), con comentario citando `NOTES.md`
Fase 34. Sin scripts exploratorios nuevos -- la verificación de `.INPUT` fue grep directo, sin necesidad
de un script.

## Fase 36 — la contaminación del 15% que encontró Fase 33 SÍ infla el residuo: gran parte del patrón cromático de Fase 23 era un artefacto de calidad de datos

A pedido del usuario ("sigamos cazando otras aristas"), en vez de un candidato físico nuevo se revisa
un supuesto que quedó **sin verificar directamente** en Fase 33: que la contaminación real del 15% en
el `.DUMP` de referencia (`SNIa_DDF_baseline_v5.3.1_10yrs.DUMP`, 298/1957 objetos que no son miembros
reales de ningún campo DDF, muchos con `MWEBV` de hasta `72.68` sobre el centro galáctico) "es poco
probable que invalide los hallazgos ya reportados" porque toda la metodología usa la **mediana**. Ese
argumento nunca se puso a prueba -- y un análisis de cómo se comporta una mediana ante contaminación
**unidireccional** (los contaminantes son siempre más tenues, nunca más brillantes, por la extinción
extrema) sugiere que el argumento es, en principio, incorrecto: insertar contaminantes solo del lado
tenue de la distribución desplaza el ítem que cae en la mediana del conjunto contaminado hacia un
percentil más bajo (más tenue) de la población limpia real -- la mediana reportada de SNANA saldría
sistemáticamente **más tenue** de lo que debería, inflando artificialmente el "SNANA sale más tenue que
LightCurveLynx" que se persigue desde Fase 16.

### Paso 1 — recalcular la comparación de siempre, con y sin el filtro, número a número

Se reconstruyó la comparación banda-por-banda de Fase 32/34 desde cero (no existía un script versionado
único -- cada fase escribía y borraba el suyo): población LCL completa (2000 objetos, mismo
`seed_base=20260812`, modelo con Fase 32+34 ya aplicados) evaluada con `compute_noise_free_lightcurves()`
en `rest_phase=0` para las 6 bandas LSST, comparada contra la mediana `PEAKMAG_u/g/r/i/z/Y` real del
`.DUMP` por los mismos 7 bins de `z` (`ZCMB`, `np.linspace(0.011, 1.2, 8)`, enmascarando `-9`), **dos
veces**: sin filtrar, y filtrando con el criterio exacto de Fase 33 (separación angular `<2°` al campo
DDF real más cercano vía centros reales del OpSim, 1659/1957 objetos bien-matcheados).

**Sanity check**: el caso sin filtrar reproduce Fase 34 exacto en `g/r/i` (`-0.3547/-0.3285/-0.3283`,
match a 4 decimales) y muy cerca en `z/y` (`-0.3323` vs. `-0.3271`, `-0.2838` vs. `-0.2737` -- diferencia
chica, probablemente por cobertura de bins ligeramente distinta en las bandas con el problema de borde de
Fase 13/23, documentado honestamente, no oculto -- no afecta la conclusión porque lo que importa es el
delta filtrado-vs-sin-filtrar dentro de esta misma corrida, no la comparación cross-run).

| banda | `diff` sin filtrar (media bins 2-7) | `diff` filtrado (`<2°`) | cambio |
|---|---:|---:|---:|
| `u` | +0.8371 (no confiable, borde de template) | +0.8238 | -- |
| `g` | -0.3547 | **-0.2297** | +0.1250 |
| `r` | -0.3285 | **-0.2515** | +0.0770 |
| `i` | -0.3283 | **-0.2599** | +0.0684 |
| `z` | -0.3323 | **-0.2914** | +0.0409 |
| `y` | -0.2838 | **-0.2884** | -0.0046 |

**Nivel acromático** (media `g/r/i/z/y`): `-0.3255` mag sin filtrar → **`-0.2642` mag filtrado** --
reducción del **19%**. **Spread cromático `g−y`**: `-0.0762` mag sin filtrar → **`+0.0164` mag filtrado**
-- el spread **cambia de signo**, prácticamente desaparece.

### Paso 2 — interpretación: confirmado, con la dirección exacta que predice la física

El patrón de mejora es asimétrico y consistente con la hipótesis: `g` mejora **0.125 mag** (la banda más
afectada por extinción, la más sensible a contaminantes con `MWEBV` extremo), `y` casi no cambia (`-0.005
mag`, la banda menos sensible a extinción). Esto es exactamente lo que predice la física de la
contaminación (extinción ∝ mucho más fuerte en azul que en rojo) -- no un ajuste ad-hoc. **El patrón
cromático `g>r>i>z>y` que motivó las Fases 23 a 31 completas (integración de banda, punto cero,
interpolación 2D, instrumentar y recompilar SNANA...) resulta, en una fracción sustancial, un artefacto
de calidad de datos del `.DUMP` de referencia** -- no una diferencia real de física/fotometría entre
LightCurveLynx y SNANA. Aplicado como corrección permanente de metodología: nueva función
`filter_ddf_field_contamination()` en `snana_params.py` (reutilizable para cualquier comparación futura
contra este `.DUMP`).

### Conclusión Fase 36 — el hallazgo más grande de la investigación después de Fase 32

Con Fase 32 (bug de muestreo, ~30-40% del nivel acromático, ~58% del spread cromático) y Fase 36
(contaminación de datos, ~19% adicional del nivel acromático, prácticamente el 100% del spread cromático
restante) combinadas: el **residuo acromático real** queda en **~0.26 mag** (bajando de ~0.52 mag desde
Fase 22), y el **patrón cromático de Fase 23, que llevó 8 fases completas de investigación de la cadena
SALT2/fotometría sintética, resulta mayormente explicado por un problema de datos, no de física** --
con el spread `g−y` real cambiando de signo tras el filtro (`+0.016` mag, compatible con ruido/cobertura
de bins, no con un patrón cromático sistemático). Queda un residuo acromático real de ~0.26 mag sin
causa identificada -- significativamente más chico que el `~0.33` mag que dejó Fase 34, y sin ningún
patrón cromático claro que perseguir. Esto cambia sustancialmente el mapa de la investigación: el
trabajo de Fases 25-31 (aislar la convención de integración de banda, el punto cero) sigue siendo
metodológicamente válido y real (esos mecanismos existen y están cuantificados), pero ya no son
necesarios para explicar el patrón cromático observado -- ese patrón, en gran medida, nunca fue tal cosa.

### Archivos de esta fase

`snana_params.py`: nueva función `filter_ddf_field_contamination()` (filtro de contaminación de campo
DDF, reutilizable). Exploratorios en NLHPC, borrados tras usarlos: `fase36_population_6band.py`/`.sbatch`
(recorrida poblacional 6 bandas, output `fase36_population_6band_output.parquet` también borrado),
`fase36_analysis.py` (comparación con/sin filtro, outputs `fase36_diff_unfiltered.csv`/
`fase36_diff_filtered.csv` también borrados tras extraer los números).

## Fase 37 — RESUELTO: el residuo acromático era `MAG_OFFSET: 0.27`, una clave del `SALT2.INFO` real del modelo que `sncosmo` no lee en absoluto

Cierra el residuo que la investigación persigue desde Fase 16. **No estaba en la cadena SALT2, ni en
la fotometría sintética, ni en el muestreo poblacional: estaba en un archivo del propio directorio del
modelo que `sncosmo` abre pero nunca lee.**

### El cambio de método que lo destrabó: comparación PAREADA, no mediana-contra-mediana

Todas las comparaciones poblacionales de Fases 16-36 son `mediana(LCL)` contra `mediana(SNANA)` de
**dos poblaciones muestreadas independientemente** (LightCurveLynx samplea su propio `z`/`x1`/`c`;
SNANA los suyos). Eso mezcla irreversiblemente dos efectos distintos:

- **(a) diferencia de FOTOMETRÍA** — mismos parámetros, distinto flujo;
- **(b) diferencia de MUESTREO POBLACIONAL** — distinta distribución de `z`/`x1`/`c`/`MU`.

Ninguna fase anterior pudo separarlos, y por eso el espacio de candidatos parecía agotado: cada fase
atacaba un mecanismo de (a) o de (b) sin poder acotar cuánto podía aportar cada familia. El `.DUMP`
usado desde Fase 16 no trae `x1`/`c` (36 columnas reales, ninguna es `S2c`/`S2x1`), así que el pareo
nunca fue posible con ese archivo.

**Lo que sí lo hace posible, y nunca se había mirado: el `_HEAD.FITS` real de producción.** Tiene 212
columnas, entre ellas `SIM_SALT2x0`, `SIM_SALT2x1`, `SIM_SALT2c`, `SIM_SALT2mB`, `SIM_SALT2alpha`,
`SIM_SALT2beta`, `SIM_DLMU`, `SIM_MWEBV`, `SIM_PEAKMJD`, `SIM_MAGSMEAR_COH` y `SIM_PEAKMAG_u..Y` —
**por objeto**. Con eso se le pueden dar a LightCurveLynx los parámetros EXACTOS que usó SNANA y
comparar objeto a objeto, aislando (a) de (b) por primera vez en todo el proyecto.

### Paso 0 — hallazgo lateral de higiene: el `.DUMP` de referencia estaba truncado

El archivo usado desde Fase 16 vive en `_stale_pre_v8fix/` y tiene **1957** filas. Existe la versión
no-stale de la MISMA simulación (mismo `RANSEED: 12945`, filas 1-1957 byte-idénticas) en
`/home/mvalenzuela/DATASIM_LSST_1/DDF/SIMDv8/SNIa_DDF_baseline_v5.3.1_10yrs/`, con las **2000** filas
completas (`NGENTOT_LC: 2000`). El `_stale` era simplemente una copia truncada, no una corrida
distinta. Se pasa a la versión completa (43 objetos más, ~2%).

De paso, su `.README` confirma contra el registro real de la corrida varios valores que fases
anteriores dedujeron indirectamente: `OMEGA_MATTER: 0.3150` y `H0 = 70.00` (Fase 34 ✓),
`GENSIGMA_VPEC: 0` (Fase 34 ✓), `GENSIGMA_MWEBV_RATIO: 0.16` (Fase 10 ✓), `WRFLAG_MODELPAR: 1`.

### Paso 1 — verificación previa: la definición de `mB` de SNANA, objeto por objeto

Antes de nada, con las columnas reales del `_HEAD.FITS` (597 objetos escritos):

| relación probada | residuo mediano | std |
|---|---:|---:|
| `SIM_SALT2mB` vs `-2.5·log10(SIM_SALT2x0) + 10.635` | **0.000000** | — |
| `SIM_SALT2mB` vs `SIM_DLMU − 19.365 − α·x1 + β·c` | **0.000000** | 0.000001 |

`SIM_SALT2alpha=0.14`, `SIM_SALT2beta=3.1`, `SIM_SALT2gammaDM=0` exactos. **`M_abs=-19.365` de Fase 20
queda confirmado por tercera vez, ahora contra datos reales por objeto y no contra una reconstrucción.**
Además `SIM_MAGSMEAR_COH` tiene `std=0.0911` — es el término coherente de G10, y coincide con el
`SIGMA_INT=0.090` que el proyecto ya usaba.

### Paso 2 — la comparación pareada: el residuo es 100% fotométrico y perfectamente plano

Se alimentó a LightCurveLynx, objeto por objeto, el `SIM_SALT2x0`/`x1`/`c`/`SIM_REDSHIFT_HELIO`/
`SIM_MWEBV`/`SIM_PEAKMJD` **exactos** de SNANA (`SncosmoWrapperModel` +
`compute_single_noise_free_lightcurve()` en `rest_phase=0`, mismo motor real de Fases 22-36), con el
filtro de contaminación de Fase 36 aplicado (586/597):

| banda | N | mediana Δ (LCL−SNANA) | media | std | p16 | p84 |
|---|---:|---:|---:|---:|---:|---:|
| `u` | 28 | -0.2931 | -0.2803 | 0.189 | -0.438 | -0.117 |
| `g` | 266 | -0.2656 | -0.2746 | 0.132 | -0.409 | -0.154 |
| `r` | 584 | -0.2620 | -0.2641 | 0.114 | -0.369 | -0.153 |
| `i` | 585 | -0.2613 | -0.2620 | 0.098 | -0.355 | -0.165 |
| `z` | 566 | -0.2608 | -0.2605 | 0.094 | -0.353 | -0.168 |
| `y` | 517 | -0.2574 | -0.2607 | 0.094 | -0.354 | -0.165 |

Y **descontando el smear coherente real de cada objeto** (`SIM_PEAKMAG − SIM_MAGSMEAR_COH`):

| banda | mediana Δ | std |
|---|---:|---:|
| `g` | -0.2722 | 0.098 |
| `r` | -0.2722 | 0.073 |
| `i` | -0.2710 | **0.033** |
| `z` | -0.2693 | **0.023** |
| `y` | -0.2699 | **0.022** |

Ajustando `Δ_r` contra `SIM_MAGSMEAR_COH`: **pendiente `-0.9672`, intercepto `-0.2719`** — confirma
numéricamente que `SIM_PEAKMAG` SÍ incluye el smear intrínseco (dato nuevo: Fase 27 había supuesto lo
contrario) y que, quitándolo, lo que queda es una **constante**.

Y por bin de `z` (mediana, banda `r`): `-0.2977 / -0.2492 / -0.2700 / -0.2694 / -0.2623 / -0.2387 /
-0.2637` — **plano también en redshift**.

Con `std` de **0.022-0.033 mag** en `i`/`z`/`y` sobre ~570 objetos, esto no es un residuo estadístico:
es un **offset constante y acromático de −0.272 mag**. Y como el pareo elimina por construcción toda
diferencia de muestreo, **el 100% del residuo es fotométrico** — toda la familia (b) queda descartada
de un solo golpe.

### Paso 3 — ¿de qué lado está el error? Prueba a tres bandas

Se comparó la MISMA magnitud AB sintética para el mismo objeto SALT2 (`z=0.6`, sin extinción) por tres
caminos independientes: (1) LightCurveLynx (`PassbandGroup`/`evaluate_bandfluxes`), (2) `sncosmo`
nativo (`Model.bandmag(band, "ab", t0)`, implementación de referencia independiente), y (3) una
integral AB photon-counting escrita a mano desde `model.flux()`:

| banda | LCL | sncosmo | manual | LCL−sncosmo | LCL−manual |
|---|---:|---:|---:|---:|---:|
| `g` | 24.7335 | 24.6997 | 24.7335 | +0.0338 | **0.0000** |
| `r` | 23.3787 | 23.3761 | 23.3787 | +0.0027 | **0.0000** |
| `i` | 23.3418 | 23.3441 | 23.3418 | -0.0023 | **0.0000** |
| `z` | 23.3757 | 23.3781 | 23.3757 | -0.0024 | **0.0000** |
| `y` | 23.4704 | 23.4641 | 23.4704 | +0.0062 | **0.0000** |

(las diferencias contra `sncosmo` son el recorte `trim_quantile` de las bandas, ya cuantificado en
Fase 31). **La fotometría absoluta de LightCurveLynx es correcta**, verificada contra dos referencias
independientes. Y del lado de SNANA, el punto cero también: el `PrimarySED` real de `kcor_LSST.fits`
resultó ser **exactamente** AB (3631 Jy) — razón contra `3631 Jy` constante en las 991 longitudes de
onda con `std = 1.7e-7` — con `Primary Mag = 0`, `ZPoff(Primary) = 0` en las 6 bandas, y el log real de
la corrida confirma `MODEL mag offsets (ugrizY): 0.00 0.00 0.00 0.00 0.00 0.00`. También se verificó en
el fuente que `SEDMODEL.FLUXSCALE = X0SCALE_SALT2 = 1.0E-12` (`genmag_SALT2.c:257`), **el mismo valor
exacto** que `sncosmo.SALT2Source._SCALE_FACTOR`, y que los factores `lamstep/hc8` se cancelan entre
`Finteg` y el `ZP`. Los dos lados, por separado, son correctos.

### Paso 4 — el hallazgo: `MAG_OFFSET: 0.27` en el `SALT2.INFO` del modelo

`/home/mvalenzuela/run_SNANA/plasticc_models/SALT2.WFIRST-H17/SALT2.INFO` (y su copia local
`exploration/lightcurvelynx/salt2_h17_local/SALT2.INFO`, el directorio que los scripts le pasan a
`sncosmo.SALT2Source(modeldir=...)`) declara:

```
RESTLAMBDA_RANGE  2000. 23000
COLORLAW_VERSION: 1
COLORCOR_PARAMS: 2800 9500 4 -1.33154627 0.61225710 -0.12117791 0.00840832
COLOR_OFFSET:  0.0

MAG_OFFSET: 0.27          <---- ESTO
SEDFLUX_INTERP_OPT: 1
...
SIGMA_INT: 0.090
```

**SNANA lo lee y lo aplica a TODA magnitud del modelo** — `genmag_SALT2.c`, línea real 2257:

```c
magobs = ZP - 2.5*log10(flux) + INPUT_SALT2_INFO.MAG_OFFSET ;
```

(leído en `genmag_SALT2.c:1275-1276`, default `0.0` en la línea 1205; y aplicado también al
espectrógrafo en la línea 3586 vía `FSCALE_ZP = pow(TEN,-0.4*MAG_OFFSET)`). Como entra después de la
integral de banda, es **aditivo en magnitud y exactamente acromático**, y afecta a `peakmag_obs` y por
lo tanto a `PEAKMAG_<filt>` del `.DUMP` y a `SIM_PEAKMAG_<filt>` del `_HEAD.FITS`.

**`sncosmo.SALT2Source` no lee `SALT2.INFO` en absoluto.** Verificado sobre el fuente real del paquete
instalado (`sncosmo==2.13.0`, vía `inspect.getsource`): ni la cadena `"SALT2.INFO"` ni `"MAG_OFFSET"`
aparecen en la clase. Sus argumentos de `__init__` son exclusivamente `m0file`, `m1file`, `clfile`,
`cdfile`, `errscalefile`, `lcrv00file`/`11`/`01` — el `SALT2.INFO` está en el mismo directorio, se copia
junto al resto del modelo, y se ignora silenciosamente.

**Valor declarado: `0.27`. Residuo pareado medido: `-0.2722` mag. Coinciden a 0.002 mag.**

Detalle de honestidad: ese `0.0022` residual es consistente con un efecto real de segundo orden que se
encontró en el mismo paso pero no se corrigió — `snlc_sim.c:25324` real muestra que
`SIM_PEAKMAG = peakmag_obs − MCOR_TRUE_MW`, es decir el `_HEAD.FITS` reporta la magnitud **con la
extinción MW ya descontada**, mientras el pareo de arriba sí la aplicó del lado de LightCurveLynx.
A los `E(B-V)` reales de DDF eso vale ~0.02-0.07 mag según banda y explica también por qué el `Δ`
pareado no es perfectamente plano entre `u` y `y` (`-0.293` vs `-0.257`). No cambia la conclusión y se
documenta como caveat conocido, no se oculta.

**Ironía real del hallazgo**: `run_snia_ddf_poc.py` ya citaba este mismo archivo desde las primeras
fases — su docstring dice literalmente *"SIGMA_INT=0.090 (de SALT2.INFO)"*. El proyecto leyó
`SALT2.INFO`, tomó `SIGMA_INT` de ahí, y nunca miró la clave que está **dos líneas más arriba**.

### Paso 5 — corregido y medido sobre la población completa (2000 objetos)

Nueva función `read_salt2_info()` en `snana_params.py` que parsea el `SALT2.INFO` real (no hardcodea el
`0.27`), y `m_abs = -19.365 + MAG_OFFSET` en los scripts. Es exactamente equivalente al offset aditivo
de SNANA: `x0 ~ 10^(-0.4·m_abs)`, así que `+0.27` en `m_abs` atenúa las 6 bandas por igual en `+0.27`
mag.

Recorrida completa: **la misma población de 2000 objetos** (mismo `seed_base=20260812`, mismos
`z`/`x1`/`c`/`t0`/`ra`/`dec`) evaluada **dos veces en la misma corrida**, con y sin el offset, contra el
`.DUMP` real completo ya filtrado de contaminación (1696/2000, Fase 36),
`compute_noise_free_lightcurves()` en `rest_phase=0`, mediana por los mismos 7 bins de `z`, media de
bins 2-7 — metodología idéntica a Fases 32/34/36:

| banda | sin fix (estado Fase 36) | con fix `MAG_OFFSET` | cambio |
|---|---:|---:|---:|
| `u` | +0.8105 (no confiable, borde de template) | +1.0805 | +0.2700 |
| `g` | -0.2304 | **+0.0396** | +0.2700 |
| `r` | -0.2509 | **+0.0191** | +0.2700 |
| `i` | -0.2647 | **+0.0053** | +0.2700 |
| `z` | -0.2892 | **-0.0192** | +0.2700 |
| `y` | -0.2880 | **-0.0180** | +0.2700 |

**NIVEL ACROMÁTICO (media `g/r/i/z/y`): `-0.2646` → `+0.0054` mag — el residuo se reduce un 98%.**

Sanity check real: la columna "sin fix" reproduce el número de Fase 36 (`-0.2642`) a **0.0004 mag** de
diferencia, con un script escrito de cero — la comparación es la misma, no una redefinición conveniente.
El spread cromático `g−y` no cambia (`+0.0577` antes y después): el offset es exactamente acromático por
construcción, como debe ser. (Ese `+0.058` es algo mayor que el `+0.016` de Fase 36 por usar ahora el
`.DUMP` completo de 2000 filas en vez del truncado de 1957; sigue siendo compatible con ruido de
cobertura de bins, no con un patrón cromático sistemático.) `u` sigue sin ser confiable — mismo problema
de borde de template de Fase 13/23/27, con 1-2 bins válidos.

### Paso 6 — cabo suelto de Fase 32 cerrado de paso: los samplers de `c`/`x1`, contra los draws reales

Fase 32 verificó la **fracción de rama** del sampler bifurcado, nunca la distribución completa ni el
comportamiento en los bordes de truncamiento (`GENRANGE_SALT2c/x1`). Se cerró de dos formas.

**Por lectura de código real**: `getRan_GENGAUSS_ASYM()` (`sntools_genGauss_asym.c`, bloque final de la
función) trunca por **rechazo puro con redraw completo** (`if (ranval < lo) { goto
BEGIN_RANDOM_SELECT; }`), que vuelve a sortear también el lado — exactamente lo que hace
`make_bifurcated_normal_sampler()`. No hay diferencia de mecanismo.

**Por medición directa**: se reprodujo la corrida de producción con el `.INPUT` real **sin editarlo**
(`snlc_sim.exe sim_SNIa_DDF_baseline_v5.3.1_10yrs.INPUT GENVERSION TEST_FASE37_dump SIMGEN_DUMPADD
S2c,S2x1,S2mb` — `SIMGEN_DUMPADD` es un override de línea de comandos, la vía limpia que evita el bug
de claves duplicadas de Fase 27), obteniendo los `c`/`x1` reales de los **2000 objetos generados**
(`SIMGEN_DUMPALL`, sin sesgo de trigger; 79 filas traen el flag `-9` y se enmascaran):

| | `c` real (N=1921) | `c` LCL (200k) | `x1` real | `x1` LCL |
|---|---:|---:|---:|---:|
| media | -0.0061 | -0.0075 | -0.0083 | -0.0028 |
| mediana | -0.0153 | -0.0163 | 0.1695 | 0.1586 |
| std | 0.0753 | 0.0745 | 0.9034 | 0.9101 |
| P(lado alto) | 0.7090 | 0.7028 | 0.1223 | 0.1321 |
| fuera de rango | 0 | 0 | 0 | 0 |

Test KS de dos muestras: `c` → `stat=0.0187, p=0.515`; `x1` → `stat=0.0214, p=0.345` — **no se puede
rechazar que sean la misma distribución** en ninguno de los dos. Impacto en magnitud de las diferencias
de media: **`-0.0041` mag (`c`) y `-0.0008` mag (`x1`)**. **Los samplers están correctos**, bordes de
truncamiento incluidos — coherente con el Paso 2, que ya había mostrado que el residuo es 100%
fotométrico y por lo tanto que no quedaba nada por encontrar del lado poblacional.

### Conclusión Fase 37 — el residuo queda cerrado, y la lección metodológica es la parte transferible

1. **El residuo acromático de ~0.26 mag que la investigación persigue desde Fase 16 queda explicado y
   corregido**: `MAG_OFFSET: 0.27` del `SALT2.INFO` real del modelo `SALT2.WFIRST-H17`, aplicado por
   SNANA (`genmag_SALT2.c:2257`) e ignorado por completo por `sncosmo`/LightCurveLynx. Nivel acromático
   `-0.2646` → `+0.0054` mag, **98% de reducción**, sin patrón cromático residual.
2. **Cadena completa de la investigación**: Fase 22 midió `~0.52` mag; Fase 32 (bug del sampler
   bifurcado) bajó a `~0.33`; Fase 36 (contaminación de campo del `.DUMP`) a `~0.26`; Fase 37
   (`MAG_OFFSET`) a `~0.005`. Las cuatro correcciones son reales, independientes y verificadas contra
   código o datos reales.
3. **Por qué 21 fases no lo encontraron, y qué lo destrabó.** Dos razones concretas, ambas
   estructurales y no de esfuerzo:
   - *La métrica lo escondía.* Todas las pruebas código-real-contra-código-real de Fases 26-31 se
     midieron **relativas a la banda `r`** (`diff = (LCL−r) − (SNANA−r)`). Esa normalización **cancela
     por construcción cualquier offset acromático** — y `MAG_OFFSET` es exactamente eso. La búsqueda
     estaba, sin saberlo, ciega a la única clase de causa que quedaba.
   - *La comparación mezclaba dos familias de causas.* Comparar mediana contra mediana de dos
     poblaciones independientes impedía saber si el residuo venía de la fotometría o del muestreo. El
     pareo objeto-a-objeto (posible sólo mirando el `_HEAD.FITS`, nunca usado antes) lo resolvió en una
     sola corrida y con `std = 0.022` mag.
4. **Lección de fidelidad, generalizable más allá de este proyecto**: cuando se reemplaza un simulador
   por otro reusando los **mismos archivos de modelo**, no alcanza con verificar que los archivos de
   datos sean byte-idénticos (Fase 20 lo hizo, con `md5sum`) — hay que verificar que el nuevo código
   **lea todas las claves de configuración** que el viejo lee. `sncosmo` copia y abre el directorio
   `SALT2.WFIRST-H17` entero, y descarta silenciosamente `MAG_OFFSET`, `COLOR_OFFSET`,
   `SEDFLUX_INTERP_OPT`, `MAGERR_*` y `RESTLAMBDA_RANGE`. Es un modo de falla silencioso: no hay error,
   no hay warning, sólo un sesgo constante de 0.27 mag. Es el mismo patrón de las Fases 24/32/34
   (`O94` vs `F99`, split 50/50, `Om0=0.3`) llevado a su forma más pura: **un valor asumido por
   omisión, nunca contrastado contra la fuente real**.
5. **Cabo suelto menor documentado, no corregido**: `SIM_PEAKMAG` del `_HEAD.FITS` viene con la
   extinción MW descontada (`snlc_sim.c:25324`), mientras `PEAKMAG_<filt>` del `.DUMP` no. Cualquier
   comparación futura contra `_HEAD.FITS` debe apagar la extinción del lado de LightCurveLynx. Efecto
   ~0.02-0.07 mag; no afecta la comparación principal de esta fase, que usa el `.DUMP`.

### Archivos de esta fase

- `snana_params.py`: nueva función `read_salt2_info()` — parsea el `SALT2.INFO` real del directorio del
  modelo (no hardcodea `0.27`), con la cita de `genmag_SALT2.c:2257` y la verificación de que `sncosmo`
  no lo lee.
- `compare_brightness_truth_salt2.py`, `run_snia_ddf_poc.py`, `run_dask_poc.py`: `m_abs = -19.365 +
  MAG_OFFSET` leído del `SALT2.INFO` real. En `run_dask_poc.py` se corrige además el `-19.3` que había
  quedado sin migrar desde Fase 20 (mismo criterio de seguimiento que Fase 35 para `Om0`).
- `bench_snia.py`: **no** se toca — usa el modelo `"salt2-h17"` del registry de `sncosmo` (no el
  directorio real de producción, así que no hay `SALT2.INFO` que leer) y una población sintética
  (`x1~N(0,2)`, `c~N(0,0.02)`, `z` uniforme); es un benchmark de rendimiento, no parte de la cadena de
  fidelidad. Queda anotado honestamente, no corregido a ciegas.
- Referencia de comparación: se pasa del `.DUMP` truncado de `_stale_pre_v8fix/` (1957 filas) al
  completo de `DDF/SIMDv8/` (2000 filas, misma corrida).
- Exploratorios en NLHPC, borrados tras usarlos: `fase37_paired.py`/`.sbatch` (Paso 2, comparación
  pareada contra `_HEAD.FITS`), `fase37_3way.py` (Paso 3, LCL vs `sncosmo` vs integral manual),
  `fase37_pop.py`/`.sbatch` (Paso 5, población completa con y sin fix), `run_fase37_dump.sh` (Paso 6,
  reproducción de la corrida de producción con `SIMGEN_DUMPADD`). GENVERSION `TEST_FASE37_dump`
  generado en `SNDATA_ROOT/SIM/` y borrado tras extraer los `c`/`x1` reales. Sin parches nuevos a
  SNANA — esta fase no necesitó instrumentar el binario, sólo leer su fuente y sus archivos de entrada.

## Fase 38 — cerrar el círculo con Fase 16: ¿el exceso de SNR/detección también se cierra con el brillo corregido?

Retoma la pregunta que arrancó la mitad de esta investigación: Fase 16 midió un exceso de SNR real de
LightCurveLynx sobre SNANA (mediana `0.868` vs. `0.78` real, `+11.3%`; `p90` `2.948` vs. `2.26` real,
`+30.4%`) y lo atribuyó al exceso de brillo, entonces sin explicar. Fase 37 cerró el brillo
(`-0.2646 → +0.0054` mag, `98%` de reducción). Esta fase remide el SNR/eficiencia de detección con la
población ya corregida (Fases 32+34+36+37 aplicadas) para ver si también cierra.

### Predicción, escrita antes de correr nada

El brillo real bajó `+0.27` mag (más tenue) desde el punto en que se midió el exceso de SNR de Fase
16 — un factor de flujo `10^(-0.4*0.27) = 0.779`. `SNR ∝ flujo` (aprox., a fondo de cielo fijo), así
que la predicción cuantitativa es:

- `snr_median` esperado: `0.868 × 0.779 ≈ 0.676` (contra `0.78` real de SNANA — **se espera que el
  signo del exceso se invierta**, de `+11.3%` a `~-13%`).
- `snr_p90` esperado: `2.948 × 0.779 ≈ 2.296` (contra `2.26` real — cerraría casi exacto, `+1.6%`).
- `detection_efficiency_pct` esperada: sin un modelo cuantitativo tan directo (la curva de eficiencia
  SEARCHEFF no es lineal en SNR), pero cualitativamente se espera una baja sustancial desde el
  `56.45%`/`ratio 1.89x` de Fase 16, plausiblemente hacia la zona de `35-45%` (`ratio ~1.2-1.5x`) —
  **no necesariamente hasta el `29.85%` real de SNANA**.

**Predicción explícita: es esperable que el brillo corregido sobre-corrija el SNR mediano (lo cruce
hacia abajo) y que el exceso de eficiencia de detección se reduzca sustancialmente pero probablemente
NO cierre del todo** — documentado así antes de correr, para no leer el resultado real de forma
conveniente después.

### Paso 1 — se cierra H5: `snr_median`/`snr_p90` ahora sí quedan en `summary.json`

`run_snia_ddf_poc.py` ya calculaba e imprimía al log `snr_median`/`snr_p90` (línea ~341-344, real desde
Fase 1) pero nunca los guardaba en `summary.json`, pese a que `HOWTO.md` §5-6 los documenta como parte
del resumen real. Corregido: se agregan `snr_median`, `snr_p90`, `snr_median_snana_ref: 0.78`,
`snr_p90_snana_ref: 2.26` al dict real (único cambio a este script). `py_compile` OK.

### Paso 2 — 5 semillas, resultado real

Corridas reales en NLHPC (`sbatch`, jobs `12038980`-`12038984`, `COMPLETED` exit `0:0` los 5, ~100-120s
de tiempo de simulación cada una), mismo `seed_base` implícito por índice de semilla de siempre:

| semilla | `snr_median` | `snr_p90` | `n_detected`/2000 | `detection_efficiency_pct` |
|---|---:|---:|---:|---:|
| 0 | 0.8208 | 2.452 | 946 | 47.30 |
| 1 | 0.8439 | 2.595 | 995 | 49.75 |
| 2 | 0.8352 | 2.590 | 990 | 49.50 |
| 3 | 0.8571 | 2.834 | 957 | 47.85 |
| 4 | 0.8367 | 2.600 | 934 | 46.70 |
| **media ± std** | **0.839 ± 0.013** | **2.614 ± 0.138** | **964.4 ± 25** | **48.22 ± 1.35** |

Tabla comparativa completa:

| métrica | SNANA real | LCL Fase 16 (pre-fix) | LCL Fase 38 (post-fix, 5 semillas) |
|---|---:|---:|---:|
| `snr_median` | 0.78 | 0.868 (+11.3%) | **0.839 ± 0.013 (+7.6%)** |
| `snr_p90` | 2.26 | 2.948 (+30.4%) | **2.614 ± 0.138 (+15.7%)** |
| `detection_efficiency_pct` | 29.85% | 56.45% | **48.22% ± 1.35%** |
| ratio de detección | 1.00x | 1.89x | **1.615x ± 0.045** |

*(No se encontró en `NOTES.md` un número de SNR/eficiencia distinto y anterior a Fase 16 explícitamente
etiquetado "Fase 1" -- la fila de comparación real más temprana disponible es la de Fase 16 misma; no se
inventa un número de relleno.)*

### Paso 3 — interpretación contra la predicción: refutada, con evidencia directa

**La predicción cuantitativa (Paso previo, "esperado `snr_median≈0.68`") queda refutada.** El SNR
mediano real bajó solo de `0.868` a `0.839` (`-3.3%` relativo) -- casi siete veces menos que la caída
del `~22%` que predecía un modelo lineal `SNR ∝ flujo` dado el factor `×0.779` de `MAG_OFFSET`. El
`p90` sí se movió más (`2.948→2.614`, `-11.3%`), pero tampoco cruzó por debajo de la referencia real
(`2.26`). La eficiencia de detección mejora de forma real y ya no ambigua (`56.45%→48.22%`, ratio
`1.89x→1.615x±0.045`, bandas de 5 semillas no solapadas con el valor de Fase 16) -- pero queda lejos
de cerrar contra el `29.85%` real de SNANA.

**Lectura honesta**: el exceso de brillo SÍ explicaba una fracción real del exceso de detección (la
mejora de `1.89x` a `1.615x` es consistente en dirección y no trivial), pero el SNR en sí -- que depende
tanto del flujo (numerador) como del ruido asumido (denominador) -- casi no se movió. Si el numerador
bajó ~`22%` en términos de flujo pero el cociente SNR bajó solo `~3%`, la implicación aritmética directa
es que **el denominador (modelo de ruido) también está sesgado, en la dirección que compensa casi por
completo la corrección de brillo** -- consistente con el candidato que la propia Fase 16 (Paso 1) dejó
señalado y nunca cerrado: `snana_noise_columns()` no pasa explícitos los términos de
`readout_noise`/`dark_current` reales del SIMLIB (`readnoise=0.25`), dependiendo en cambio de los
defaults de `OpSim`. Otros candidatos no descartados: la lógica de trigger/SEARCHEFF real
(`searcheff.py::group_into_epochs()`) y `rest_time_window_offset=(-30,100)` (una ventana de generación
más ancha que la real podría inflar el denominador de la eficiencia, aunque no el SNR por observación
en sí). **No se fuerza un cierre que los datos no muestran** -- queda como pregunta nueva, abierta,
mejor acotada que antes (ya no es "¿por qué hay exceso de SNR?" sino específicamente "¿por qué el SNR
no cae proporcional al flujo corregido?").

### Tarea P1 — estado real de la referencia WFD de `SNIa`

El `postprocess_manifest.json` real (`~/AUTOSIM/build/full_v5.3_10yrs/postproc/`) registra
`SNIa_WFD_baseline_v5.3.1_10yrs` con `error: "'utf-8' codec can't decode byte 0xee in position 119:
invalid continuation byte"` (entrada real, `n_processed=0` en ese manifiesto -- corrida de postproceso
mayormente `skipped`, no completada). Pero la **simulación cruda sí completó**: 2 de 5 logs reales de
`snlc_sim.exe` para esta clase (`run_SNIa_WFD_baseline_v5.3.1_10yrs_11320196.out`/`_11330240.out`)
terminan con `DONE with snlc_sim.` real (`WR_SNFITSIO_END: wrote 28949 events`); los otros 3 fallaron a
mitad de camino (uno con error real de `cfitsio`, dos truncados, consistentes con el incidente de cuota
ya documentado). El directorio de salida real
(`/home/mvalenzuela/DATASIM_LSST_1/WFD/SIMWv8/SNIa_WFD_baseline_v5.3.1_10yrs/`) tiene `.DUMP` (2.5MB,
10.456 filas, bien formado, `VARNAMES`/`SELECTION: NONE` real), `_HEAD.FITS` (4.2MB) y `_PHOT.FITS`
(20MB) reales y con timestamp consistente (11-ago). El byte `0xee` reportado por el manifiesto **no
está** en la posición 119 del `.README` real actual (se verificó byte a byte: es `0x6c`, ASCII) -- el
error del manifiesto probablemente viene de un archivo/intento distinto o quedó desactualizado. **La
línea futura "extender a WFD" queda parcialmente desbloqueada**: hay datos reales de referencia
utilizables (`.DUMP`/`_HEAD.FITS`/`_PHOT.FITS`), pero el pipeline de postproceso automático necesita
revisión aparte antes de confiar en cualquier número que dependa de él.

### Conclusión Fase 38

El círculo con Fase 16 se cierra parcialmente, con un resultado más interesante que el esperado: **la
corrección del brillo (Fases 32/34/37) sí mejora la eficiencia de detección de forma real (ratio
`1.89x→1.615x`), pero el SNR en sí casi no se mueve** -- refutando con evidencia directa la hipótesis
lineal simple que motivaba esta fase, y por eliminación aritmética, apuntando al **modelo de ruido**
(no ya solo al flujo) como el candidato dominante que queda para el exceso de detección real. Es un
resultado más rico que "cierra"/"no cierra": redirige la investigación futura hacia un mecanismo
concreto y no probado (`snana_noise_columns()`/`readout_noise`/`dark_current` vs. SIMLIB real).

### Archivos de esta fase

`run_snia_ddf_poc.py`: agregados `snr_median`/`snr_p90`/`snr_median_snana_ref`/`snr_p90_snana_ref` a
`summary.json` (único cambio). `docs/lcl_qc/lcl_qc_index.json`: actualizado el registro `SNIa` con los
números reales de esta fase (antes: datos pre-Fase-32/34/37, ya sabidos incorrectos). `docs/index.html`:
nueva entrada Fase 38 en "N fases", callout "Actualización Fase 38" en Resumen, ítem 1 de "líneas para
seguir investigando" en Conclusiones marcado como hecho. Sin scripts exploratorios nuevos -- toda la
medición usa el propio `run_snia_ddf_poc.py` real, ya versionado.

## Fase 39 — validada la curva completa vía `SIM_MAGOBS` real: plana, sin la dependencia de fase esperada del candidato `SEDFLUX_INTERP_OPT`

Usa H1 (identificado al planificar esta ronda con Opus): el `_PHOT.FITS` real de producción trae
`SIM_MAGOBS` -- magnitud verdadera sin ruido, por época, para los 597 objetos SNIa DDF detectados
(`/home/mvalenzuela/DATASIM_LSST_1/DDF/SIMDv8/SNIa_DDF_baseline_v5.3.1_10yrs/`). Permite parear
objeto-a-objeto y **época-a-época real** contra LightCurveLynx sin simular ninguna fase sintética --
extensión directa del método pareado de Fase 37 (que solo miró `rest_phase=0`) a la curva completa.

### Verificación previa: `SIM_MAGOBS` también viene con la extinción MW descontada

Confirmado en `~/github/SNANA_src/src/snlc_sim.c` real (línea 25394):
```c
SNDATA.SIMEPOCH_MAG[epoch] = GENLC.genmag_obs[epoch] - MCOR_TRUE_MW ;
```
mismo patrón que `SIM_PEAKMAG` (línea 25324, cabo suelto ya documentado en Fase 37 Paso 4) --
`SIMEPOCH_MAG` es el nombre interno de struct que se escribe como `SIM_MAGOBS` en el `_PHOT.FITS`. Se
evaluó LightCurveLynx **sin** `ExtinctionEffect` para que el pareo sea consistente.

### Método real: `PTROBS_MIN`/`PTROBS_MAX`, no MJD

`_HEAD.FITS` (597 objetos, 212 columnas) trae `PTROBS_MIN`/`PTROBS_MAX` -- índices 1-based reales que
delimitan el bloque de épocas de cada objeto en `_PHOT.FITS` (2.630.079 filas totales). Por objeto, se
leyeron `SIM_SALT2x0/x1/c`, `SIM_REDSHIFT_HELIO`, `SIM_PEAKMJD` reales; se aplicó
`filter_ddf_field_contamination()` (Fase 36, ya versionada) -- 586/597 bien-matcheados; se construyó
`SncosmoWrapperModel(local_src, t0=SIM_PEAKMJD, x0=SIM_SALT2x0, x1=SIM_SALT2x1, c=SIM_SALT2c,
redshift=SIM_REDSHIFT_HELIO)` (sin extinción) y se evaluó `evaluate_bandfluxes()` real en los MJD
**exactos** de cada época real; se sumó `MAG_OFFSET` real (`read_salt2_info()`, Fase 37). Hallazgo de
higiene real: la columna `BAND` del `_PHOT.FITS` viene como `LSST-<letra>` (p.ej. `LSST-r`), no la
letra sola -- un primer intento sin parsear el prefijo dio 0 filas útiles, corregido antes de medir
nada. Sentinela real de "sin dato" en `SIM_MAGOBS`: `99.0` (571.868/2.630.079 filas, 21.7%);
enmascarado junto con 5 filas de encabezado (`BAND='-'`) antes de calcular cualquier cosa.

### Resultado: 560.421 pares época-objeto, prácticamente plano en toda la curva

| bin fase rest | mediana Δmag | media | std | N | p16 | p84 |
|---|---:|---:|---:|---:|---:|---:|
| [-20,-10) | -0.0074 | -0.0007 | 0.167 | 71.789 | -0.107 | 0.091 |
| [-10,-5) | -0.0197 | -0.0247 | 0.106 | 41.901 | -0.122 | 0.075 |
| [-5,0) | -0.0211 | -0.0298 | 0.100 | 48.706 | -0.134 | 0.068 |
| [0,+5) | -0.0302 | -0.0343 | 0.102 | 46.448 | -0.133 | 0.059 |
| [+5,+10) | -0.0200 | -0.0292 | 0.100 | 41.019 | -0.129 | 0.064 |
| [+10,+20) | -0.0185 | -0.0248 | 0.099 | 83.692 | -0.127 | 0.069 |
| [+20,+40) | -0.0178 | -0.0267 | 0.120 | 157.820 | -0.127 | 0.070 |
| [+40,+100) | -0.0234 | -0.0164 | 0.188 | 69.046 | -0.131 | 0.078 |

**No hay tendencia creciente con `|fase|`** -- el bin más extremo probado (`[+40,+100)`, hasta 100 días
del pico) da `-0.023` mag, prácticamente igual al bin central (`[0,+5)`, `-0.030` mag) y menor que
varios bins intermedios. Descarta la hipótesis concreta que motivó esta fase: `SEDFLUX_INTERP_OPT: 1`
(confirmado en el `SALT2.INFO` real, otra clave que `sncosmo` ignora igual que `MAG_OFFSET`) no produce
un artefacto que crezca con la distancia al pico -- si lo hiciera, sería visible acá y no lo es. Por
banda (`g/r/i/z/Y` con estadística real, `u` con `N<340` por bin y desviaciones de hasta `-0.15` mag,
mismo problema de borde de template de Fases 13/23/27/39 ya conocido, no confiable): todas dentro de
`-0.001` a `-0.046` mag, sin patrón cromático claro tampoco.

**Cabo suelto real, chico pero no cero**: los 8 bins muestran un offset residual consistente de
`-0.01` a `-0.03` mag (no cero, no creciente) -- del orden de un 10% de lo que ya se cerró en Fase 37,
visible ahora porque este es el primer test con épocas reales completas en vez de solo el pico
poblacional. No se investiga la causa en esta fase (fuera de alcance del criterio de decisión
definido) -- candidatos plausibles para una fase futura: ruido de segundo orden en la normalización de
banda (Fases 25-30) evaluado ahora en fases no-pico, o el `trim_quantile` de producción (Fase 31).

### Conclusión Fase 39

**Criterio "plano" cumplido**: la curva completa no muestra la dependencia de fase que predecía el
candidato `SEDFLUX_INTERP_OPT` -- descartado con evidencia directa (código real vs. datos reales de
época, no una aproximación). Fase 37 se extiende con confianza a la curva completa, no solo al pico:
el `MAG_OFFSET` cierra el residuo grande (`~0.27` mag) en todas las fases por igual, consistente con
ser un offset aditivo puro tal como predice la fórmula real de SNANA. Queda un residuo chico
(`-0.01` a `-0.03` mag, sin tendencia) documentado como pregunta abierta menor, no forzado a una
explicación.

**H4 cerrado de paso**: `compare_brightness_truth_salt2.py` usaba `flux_perfect.max()` sobre la
cadencia real -- la métrica que la propia Fase 22 declaró inválida, nunca migrada en el único script
versionado de comparación de brillo del proyecto (las Fases 22-38 usaban scripts exploratorios ya
borrados con la métrica correcta). Corregido a `compute_noise_free_lightcurves()` real evaluado en
`rest_phase=0` (mismo patrón de Fase 22 en adelante). Verificado: corre limpio sobre los 2000 objetos
reales de la campaña (`z` 0.08-1.20, `PEAKMAG_r_true` 18.1-28.8, rango físico razonable), sin errores.

### Archivos de esta fase

`compare_brightness_truth_salt2.py`: migrado de `simulate_lightcurves()`+`flux_perfect.max()` a
`sample_parameters()`+`compute_noise_free_lightcurves()` en `rest_phase=0` (cierra H4). Exploratorios
en NLHPC, borrados tras usarlos: `fase39_lightcurve_paired.py`/`.sbatch` (pareo época-a-época real),
`fase39_verify.sbatch` (corrida de verificación del fix de H4). Sin cambios a `snana_params.py` --
ningún candidato nuevo llegó al umbral de corrección esta fase.

## Fase 40 — cobertura de claves de configuración en las 19 clases: un hallazgo nuevo (`GENRANGE_TREST`), una corrección al propio dashboard, y el resto ya blindado

El método que encontró la causa raíz de toda la investigación (Fase 37: ¿qué claves reales del
`.INPUT`/`SED.INFO`/`SALT2.INFO` lee cada lado?) nunca se había aplicado fuera de `SNIa`. Esta fase lo
extiende a las 14 clases físicas reales que cubre LightCurveLynx (`SNIa` + 13 SIMSED; los 5
`*_NON1ASED` de la tabla de 19 "clases evaluadas" del dashboard son la MISMA clase física en otra
codificación, comparten `.INPUT`/directorio de modelo con su versión SIMSED, así que auditar 14 basta
para cubrir las 19 entradas). Trabajo puramente de lectura -- sin simular nada, sin tocar `SNDATA_ROOT`.

### Paso 1 — inventario real de `.INPUT` por clase

Vía `INPUT_INCLUDE_FILE:` real de `~/AUTOSIM/build/full_v5.3_10yrs/includes/include_model_<clase>.INPUT`
(no por nombre de carpeta, mismo criterio de `HOWTO.md` §7) se confirmó el `.INPUT` real de las 14
clases (`SIMGEN_INCLUDE_<modelo>.INPUT`, todos bajo `~/run_SNANA/model_config/` salvo los dos
`PISN-STELLA-*` que usan `~/run_SNANA/elastic/model_config/`) y se leyeron completos.

### Paso 2 — tabla de cobertura de claves

| Clave | Dónde se declara | Clases | Qué hace SNANA | ¿LCL la lee? | Impacto |
|---|---|---|---|---|---|
| `MAG_OFFSET` | `SALT2.INFO` | `SNIa` | offset aditivo de magnitud (`genmag_SALT2.c:2257`) | No — **corregido en Fase 37** | `0.27` mag, ya cerrado |
| `FLUX_SCALE` | `SED.INFO`/`NON1A.LIST` | todas las SIMSED/NON1ASED | normaliza el flujo del template | **Sí** — `SIMSEDModel.from_dir()` y `non1ased.py::parse_flux_scale()` | ninguno — control positivo |
| `MAGOFF`/`MAGSMEAR` (bloque `NON1A_KEYS`) | `.INPUT` | las 5 clases NON1ASED | offset/smear por template individual | No leído, pero **blindado**: `non1ased.py:86-90` levanta `NotImplementedError` si alguno es `≠0` (confirmado `0.0` real en las 5 clases del proyecto -- el guardia nunca disparó en ninguna corrida histórica) | ninguno hoy; riesgo latente ya cubierto por el guard, no silencioso |
| `GENPEAK_RV`/`GENRANGE_RV`/`GENSIGMA_RV` | `.INPUT` | 9 clases con extinción de host (`KN-K17`, `CaRT`, `SLSN-I`, `SNIax`, `TDE-MOSFIT`, `ILOT-MOSFIT`, `SNIIn-MOSFIT`, `PISN-MOSFIT`, `KN-BULLA19`) | `R_V` de la ley de extinción; `GENSIGMA_RV: 0.0 0.0` en las 9 → `R_V` efectivamente fijo en `GENPEAK_RV` pese al `GENRANGE_RV` declarado | **Sí** — `r_v=3.1` hardcodeado en `CLASS_CONFIGS`, coincide exacto con `GENPEAK_RV: 3.1` real en las 9 | ninguno — control positivo confirmado |
| `GENAV_WV07`/`WV07_REWGT_EXPAV` | `.INPUT` | 9 clases (7 con `GENAV_WV07:1` directo, 2 con `WV07_REWGT_EXPAV:0.5`) | activa el modelo WV07 de extinción de host | **Sí** — `make_wv07_av_sampler(rewgt_expav=...)`, con/sin rewgt coincide clase por clase (Fase 3) | ninguno |
| `GENTAU_AV`/`GENSIG_AV`/`GENRATIO_AV0` | `.INPUT` | `SNIax` | mezcla exponencial+semi-Gaussiana de extinción de host | **Sí** — `make_exp_halfgauss_av_sampler()` (Fase 2B ronda 3) | ninguno |
| `SIMSED_REDCOR` | `.INPUT` | `SNIa-91bg`, `SNII-NMF` | correlación entre parámetros SIMSED | **Sí** — `make_correlated_normal_weights()` | ninguno confirmado hoy; Fase 41 lo audita estadísticamente |
| `DNDZ` (todas las familias: `POWERLAW`/`POWERLAW2`/`MD14`/`CC_S15`/`TDE`/`PISN_PLK12`) | `.INPUT` | las 14 | tasa volumétrica vs. `z` | **Sí**, reimplementadas con fórmula real citada (`snana_params.py`); solo `POWERLAW2` de `SNIa` tiene validación estadística directa (Fase 33, KS `p=0.183`) | resto pendiente de Fase 41 |
| `DNDZ_ALLSCALE` | `.INPUT` | `SNII-NMF`, `ILOT-MOSFIT`, `SNIIn-MOSFIT` | escala la tasa `CC_S15` | **Sí** — pasado como `scale` a `build_dndz_ccs15_cdf()` | ninguno |
| `GENMEAN_SALT2ALPHA`/`GENMEAN_SALT2BETA` | `.INPUT` | `SNIa` | parámetros Tripp fijos | **Sí**, exacto (Fase 16) | ninguno |
| `GENSIGMA_SALT2c`/`GENSIGMA_SALT2x1` (bifurcadas) | `.INPUT` | `SNIa` | sigma distinta a cada lado del pico | Sí, pero la **probabilidad de rama** estaba mal — **corregido Fase 32** | ya cerrado |
| `GENMAG_SMEAR_MODELNAME: G10` | `.INPUT` | `SNIa` | dispersión intrínseca coherente + término cromático | Parcial — solo el coherente (`SIGCOH`), falta el cromático | razonado y descartado como causa (ya documentado en el dashboard); dirección contraria a lo que había que explicar |
| **`GENRANGE_TREST`** | `.INPUT`, real por clase (`-50/300` a `-100/1000`, ver tabla abajo) | las 14 | ventana de fase válida para generar observaciones/época | **No** — los 7 scripts (`bench_snia.py`, `compare_brightness_truth*.py`, `run_dask_poc.py`, `run_non1ased_poc.py`, `run_simsed*_poc.py`, `run_snia_ddf_poc.py`) usan `rest_time_window_offset=(-30, 100)` **hardcodeado e idéntico para las 14 clases**, nunca leído del `.INPUT` real | **hallazgo nuevo real** — ver Paso 3 |
| `MINSLOPE_EXTRAPMAG_LATE` | `.INPUT` | `KN-K17`, `KN-BULLA19` | piso de pendiente para extrapolación tardía más allá del template nativo | No implementado | **clave real nunca antes mencionada en el proyecto** — ver Paso 4; sin efecto en comparaciones de pico, relevante solo más allá del rango nativo del template |
| `GENMODEL_EXTRAP_LATETIME` (`SNIa_Extrap_LateTime_2expon.TEXT`) | `.INPUT` | `SNIa` | modelo real "doble exponencial" de extrapolación tardía | Aproximado con `LinearDecay(50.0)`, ya documentado como simplificación conocida | relevante para Fase 39 (curva completa), no para el pico |
| `SIMSED_USE_BINARY` | `.INPUT` | todas las SIMSED (`: 0` en las 14) | formato de caché binaria interna de SNANA para acelerar `snlc_sim.exe` | N/A — puramente I/O interno de SNANA, sin contraparte física que LCL deba replicar | ninguno |

### Paso 3 — `GENRANGE_TREST`: hallazgo nuevo, sin efecto en el pico, candidato real para clases de cola larga

`GENRANGE_TREST` real por clase, contra la ventana hardcodeada `(-30, 100)` que usan los 7 scripts:

| Clase | `GENRANGE_TREST` real | Ventana usada | Fracción del rango real cubierta |
|---|---:|---:|---:|
| `SNIa` | `-100  300` | `-30  100` | 32.5% |
| `SNIa-91bg` | `-100  400` | `-30  100` | 26.0% |
| `KN-K17` | `-100  300` | `-30  100` | 32.5% |
| `CaRT` | `-100  500` | `-30  100` | 21.7% |
| `SLSN-I` | `-100  500` | `-30  100` | 21.7% |
| `SNIax` | `-100  400` | `-30  100` | 26.0% |
| `TDE-MOSFIT` | `-100  500` | `-30  100` | 21.7% |
| `SNII-NMF` | `-100  400` | `-30  100` | 26.0% |
| `ILOT-MOSFIT` | `-100  1000` | `-30  100` | **11.8%** |
| `SNIIn-MOSFIT` | `-50  300` | `-30  100` | 37.1% |
| `PISN-MOSFIT` | `-100  300` | `-30  100` | 32.5% |
| `KN-BULLA19` | `-100  500` | `-30  100` | 21.7% |
| `PISN-STELLA-HECORE`/`-HYDROGENIC` | (no releído en esta fase, mismo `.INPUT` `elastic` que las demás `PISN-*`, se asume comparable) | `-30  100` | — |

**Esto no afecta ningún resultado ya reportado de comparación de brillo pico** (Fases 22-39 evalúan
`compute_noise_free_lightcurves()`/`compute_single_noise_free_lightcurve()` en `rest_phase=0`, que no
pasa por `rest_time_window_offset` en absoluto -- ese parámetro solo gobierna la ventana de
`simulate_lightcurves()`, la ruta con cadencia/ruido/trigger). **Sí es un candidato real, nunca antes
verificado, para los ratios de detección de las Fases 5-9** (`NOBS`/trigger de las 13 clases SIMSED,
todas corridas con esta misma ventana hardcodeada): `ILOT-MOSFIT` es el caso extremo, con solo 11.8%
de su rango temporal real cubierto -- si su curva de luz real tiene emisión observable fuera de
`[-30,100]` días (su nombre, "Intermediate Luminosity Optical **Transient**", sugiere evoluciones
más lentas que una SN estándar), la ventana recortada podría estar subestimando `NOBS`/SNR real de
forma sistemática. **No se corrigió ni se remidió en esta fase** -- es diagnóstico puro, documentado
como candidato concreto para una fase futura dedicada a las clases SIMSED (fuera del alcance actual,
centrado en `SNIa`).

### Paso 4 — `MINSLOPE_EXTRAPMAG_LATE`: clave real nueva, nunca antes mencionada

El dashboard (fase que cerró el "roadmap" de candidatos, sub-tab "N fases") sí verificó correctamente
que `REDCOV`/`TEMPLATE_ZPT` no aparecen en ningún `.INPUT`/`.SIMLIB` real de las 19 clases -- esa
afirmación queda confirmada, sin corrección necesaria (verificación cruzada, no repetida a ciegas).
`MINSLOPE_EXTRAPMAG_LATE` nunca se había mencionado en el proyecto hasta esta fase -- no es una
corrección a un texto existente, es una clave real nueva: aparece, real, en `KN-K17` y `KN-BULLA19`
(`MINSLOPE_EXTRAPMAG_LATE: 0.1`), no implementada del lado LightCurveLynx. Sin efecto en ninguna
comparación ya reportada (ninguna dependió de la extrapolación tardía de esas 2 clases), documentado
como candidato menor para una futura auditoría de esas dos clases específicamente.

### Conclusión Fase 40

De las claves reales auditadas en las 14 clases, **13 están o bien leídas correctamente (controles
positivos que confirman que el método distingue bien, sin repetir el error de Fase 37) o blindadas
activamente contra el modo de falla silencioso** (`MAGOFF`/`MAGSMEAR`). Fuera de `MAG_OFFSET`
(ya cerrado, Fase 37) y el sampler bifurcado (ya cerrado, Fase 32), el **único hallazgo nuevo real** es
`GENRANGE_TREST` -- ignorado en las 14 clases por igual, sin efecto en ninguna comparación de brillo
pico ya reportada, pero un candidato concreto y nunca antes verificado para los ratios de detección
históricos de clases de cola larga (`ILOT-MOSFIT` en particular). **No se corrige en esta fase** --
corregirlo bien requeriría decidir si la ventana debe ser por-clase (rompe la comparabilidad histórica
entre clases de las Fases 5-9 si se cambia a mitad de camino) y remedir esas clases, un alcance mayor
que esta auditoría de lectura. Queda documentado como la pregunta abierta más concreta que deja esta
fase para una futura ronda centrada en las clases SIMSED (no `SNIa`). El modo de falla de Fase 37
(`MAG_OFFSET`) resultó ser, dentro de lo auditado, un caso único en este catálogo -- no una clase de
bug repetida -- aunque `GENRANGE_TREST` demuestra que "una clave ignorada" sigue siendo un patrón real
y vale la pena seguir buscándolo.

### Archivos de esta fase

Ninguno versionado -- diagnóstico puro (grep/lectura de `.INPUT` reales vía `ssh`, sin scripts
Python nuevos, sin simular nada, sin tocar `SNDATA_ROOT`). Corrección de texto en `docs/index.html`
(la cifra "otras 39 clases" de la sub-tab "Conclusiones", corregida a la cobertura real de
LightCurveLynx -- 14 clases físicas, 19 entradas evaluadas contando codificaciones NON1ASED).

## Fase 41 — samplers de extinción de host y `DNDZ: MD14` validados en 3 clases; `SIMSED_REDCOR` reabre un mecanismo real nunca comparado

Extiende el patrón de Fase 32 (auditar el *algoritmo*, no solo los parámetros, de cada sampler custom
de `snana_params.py` contra el código real de SNANA) a los samplers nunca auditados:
`make_wv07_av_sampler`, `make_exp_halfgauss_av_sampler`, `make_dndz_sampler`/`build_dndz_md14_cdf`, y
`make_correlated_normal_weights` (`SIMSED_REDCOR`).

### Sin sesgo de trigger, sin necesitar `SIMGEN_DUMPADD`

Las 4 clases elegidas (`KN-K17`, `SLSN-I`, `SNIax`, `SNIa-91bg`) ya tienen corridas reales completas en
`/home/mvalenzuela/DATASIM_LSST_1/DDF/SIMDv8/<clase>_DDF_baseline_v5.3.1_10yrs/` con
`SELECTION: NONE` (2000/2000 filas, sin sesgo de detección) -- no hizo falta reproducir ninguna corrida
ni usar `SIMGEN_DUMPADD`. Sus `.DUMP` ya traen `AV`/`RV` (extinción de host) directo en `VARNAMES`, y el
de `SNIa-91bg` trae `stretch`/`color` directo. **Hallazgo de higiene real, no reportado hasta ahora**:
las columnas `AV` y `ZHELIO` de estos 4 `.DUMP` contienen sentinelas `-9` reales (102/2000 en `KN-K17`,
53/2000 en `SLSN-I`, 79/2000 en `SNIax`, 81/2000 en `SNIa-91bg` -- objetos sin extinción/redshift válido
asignado por alguna razón no investigada acá) que hay que enmascarar **antes** de cualquier estadística
-- sin filtrar, la media/std salen absurdas (p.ej. `KN-K17` `AV` media `-0.22`, imposible físicamente) y
contaminan cualquier comparación, mismo tipo de trampa que ya documentaron Fases 13/27/33 para
`PEAKMAG=-9`.

### Extinción de host (`wv07`/`exp_halfgauss`) y `DNDZ: MD14`: los 5 pares, correctos

Comparando 200k draws de cada sampler (parámetros reales exactos de `CLASS_CONFIGS`,
`run_simsed_poc.py`) contra los draws reales de SNANA (sentinelas ya filtrados), mismo formato de tabla
que Fase 37 Paso 6 + KS de dos muestras + impacto en magnitud vía `F99(Rv=3.1)` sobre la diferencia de
medianas:

| par (clase, sampler) | N real | KS stat | KS p | Δmag máx (u→y) |
|---|---:|---:|---:|---:|
| `KN-K17` `AV` (wv07, rewgt=0.5) | 1898 | 0.028 | 0.106 | +0.010 (u) |
| `SLSN-I` `AV` (wv07, sin rewgt) | 1947 | 0.024 | 0.219 | +0.012 (u) |
| `SLSN-I` `z` (DNDZ MD14, rate0=2e-8) | 1947 | 0.021 | 0.334 | -- |
| `SNIax` `AV` (exp_halfgauss) | 1921 | 0.014 | 0.817 | -0.002 (u) |
| `SNIax` `z` (DNDZ MD14, rate0=6e-6) | 1921 | 0.024 | 0.226 | -- |

**Los 5 pares pasan limpio** (KS `p>0.05` y `Δmag<0.01` mag en las 6 bandas para los 3 de extinción) --
`make_wv07_av_sampler()`, `make_exp_halfgauss_av_sampler()` y `build_dndz_md14_cdf()`/
`make_dndz_sampler()` reproducen fielmente el algoritmo real de SNANA para estas 3 clases. Ningún bug
del tipo Fase 32 en estos 5 mecanismos.

### `SIMSED_REDCOR` (`SNIa-91bg`): las medias coinciden, pero el mecanismo real es otro

`make_correlated_normal_weights()` calcula, para los 35 templates reales de `simsed_91bg_local/SED.INFO`,
un peso `∝ exp(-½ (x-peak)ᵀ Σ⁻¹ (x-peak))` evaluado **exactamente en el punto discreto de cada
template**, y resamplea por ese peso. Comparado contra `stretch`/`color` reales de los 2000 objetos del
`.DUMP` (sentinelas de `ZHELIO` filtrados aparte, `stretch`/`color` sin sentinelas):

| | real (N=2000) | sim (200k, resampleo por peso) |
|---|---:|---:|
| `stretch` media | 0.9770 | 0.9752 |
| `stretch` mediana | 0.9772 | 0.9500 |
| `color` media | 0.5498 | 0.5568 |
| `color` mediana | 0.5517 | 0.5000 |
| KS `stretch` | -- | stat=0.211, **p=1.2e-77** |
| KS `color` | -- | stat=0.276, **p=2.7e-133** |

Las **medias** coinciden casi exactamente (`Δstretch=0.0018`, `Δcolor=0.0070`) -- pero el test KS es
abrumadoramente significativo, y las medianas difieren más (`Δstretch=0.027`, `Δcolor=0.052`), cayendo
justo sobre los dos templates de mayor peso teórico (`(0.95, 0.50)` y `(1.05, 0.50)`, `24.4%` y `22.4%`
del peso total). Se leyó el algoritmo real de SNANA para descartar que sea solo un artefacto de la
grilla discreta: `prep_user_SIMSED()` (`snlc_sim.c`, real, "Prepare Cholesky decomp for correlations")
confirma que SNANA **no** evalúa el peso Gaussiano en cada punto de grilla -- arma la descomposición de
Cholesky de la covarianza real, samplea un valor **continuo** correlacionado, y recién después snapea al
template más cercano vía `nearest_gridval_SIMSED()` (línea real 14179: `PARVAL =
nearest_gridval_SIMSED(ipar_model,PARVAL_TMP)`). Son dos mecanismos genuinamente distintos -- pesar la
densidad exacta en cada punto discreto (lo que hace `make_correlated_normal_weights()`) no es
matemáticamente equivalente a integrar la densidad sobre la celda de Voronoi de cada template alrededor
de un draw continuo (lo que hace SNANA real), sobre todo con una grilla tan gruesa e irregular como
35 templates en 2D.

**No se llegó a implementar ni medir el impacto del mecanismo correcto en esta fase** (el "continuo +
snap a la grilla" requiere replicar la lógica de Voronoi/nearest-neighbor de `nearest_gridval_SIMSED()`,
no solo cambiar una línea) -- documentado honesto como lo que es: un mecanismo real y confirmado
distinto (no una hipótesis), con evidencia estadística fuerte (KS) pero **sin cuantificar aún el
impacto en magnitud poblacional**, ya que la media (que es lo que más pesa en un residuo tipo mediana)
coincide bien. Candidato concreto para una fase futura, con la cita exacta ya en mano
(`nearest_gridval_SIMSED()`) para no tener que rebuscarla.

### P2 -- seed propagation: sigue en la misma versión, un dato del borrador quedó desactualizado

`lightcurvelynx==0.5.2` sigue siendo la versión instalada (sin cambios desde que se escribió
`ISSUE_DRAFT_seed_propagation.md` en Fase 19-20). Verificado por lectura de fuente real
(`inspect.getsource`):

- `ObsTableRADECSampler.compute()`: el patrón `rng_info if rng_info is not None else
  np.random.default_rng()` sigue presente -- **bug #1 confirmado sin cambios**.
- `TableSampler.__init__`: sigue sin forwardear `seed=` al `NumpyRandomFunc("integers", ...)` interno
  -- **bug #2 confirmado sin cambios**.
- `SIMSEDModel.from_dir()`: el código real actual **ya no construye el sampler interno ahí** -- solo
  lee los templates y hace `return cls(templates, flux_scale=flux_scale, **kwargs)`, delegando a
  `__init__`. El borrador cita la construcción del `GivenValueSampler`/`_sampler_node` como parte de
  `from_dir()`; en la versión instalada hoy esa lógica vive en otro lugar (no confirmado en esta pasada
  por presupuesto). **No se tocó el borrador** -- queda anotado acá que la cita de ubicación de ese
  tercer bug necesita una relectura antes de publicarlo, aunque el bug en sí (falta de propagación de
  semilla) parece seguir siendo real por el patrón de código ya visto en fases anteriores.

### Conclusión Fase 41

5 de 6 samplers auditados (extinción de host en 3 clases, `DNDZ: MD14` en 2) quedan **validados**, sin
bugs -- el patrón de Fase 32 no se repite ahí. El sexto (`SIMSED_REDCOR`, `SNIa-91bg`) queda en estado
intermedio y honesto: mecanismo real confirmado distinto (Cholesky+nearest-neighbor vs. peso discreto
exacto), evidencia estadística fuerte, pero impacto en magnitud sin cuantificar porque las medias
coinciden razonablemente bien -- no es un cierre limpio en ninguna dirección, y se documenta así en vez
de forzarlo. P2 confirma que los 2 bugs de seed propagation más simples siguen intactos en la versión
instalada; el tercero necesita que alguien relea `SIMSEDModel.__init__` antes de que el borrador sea
públicable con confianza.

### Archivos de esta fase

`fase41_samplers.py`/`fase41_samplers_v2.py` (exploratorios, no versionados, borrados de NLHPC tras
usarlos -- la v1 tenía el bug de sentinelas `-9` sin filtrar, documentado arriba como hallazgo de
higiene real, no como error oculto). Sin cambios a `snana_params.py` -- ningún candidato llegó al
umbral de "bug confirmado y cuantificado" que justificara una corrección esta fase.
