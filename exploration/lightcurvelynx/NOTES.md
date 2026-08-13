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
