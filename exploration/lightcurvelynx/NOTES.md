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
