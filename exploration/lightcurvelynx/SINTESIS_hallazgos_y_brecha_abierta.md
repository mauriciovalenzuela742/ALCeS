# Síntesis — 4 bugs reales de LightCurveLynx/sncosmo corregidos, y la causa raíz de la brecha de
sobre-detección encontrada, corregida y confirmada catálogo-completo

**Estado (actualizado 2026-09-03): brecha cerrada.** Lo que este documento originalmente describía
como "brecha sin explicación" (sección 3, `2.895x → 5.113x`, Fase 59) fue investigado a fondo en las
Fases 60-64 y **resuelto**: el trigger de detección propio de este proyecto usaba el flujo *observado*
(con ruido) en vez del flujo *verdadero* (sin ruido) que usa SNANA real — un bug de una sola línea,
confirmado leyendo `snlc_sim.c` de SNANA línea por línea. Corregido y re-medido en las 19 clases del
catálogo completo (Fases 64/65/67/70): el ratio promedio pasa de `5.113x` a `1.070x`. Ver sección 3-bis
para el detalle real, con números de las 19 clases.

Publicación: **3 de los 4 borradores de bug ya se publicaron** el 2026-09-01 como un solo issue
combinado en `lincc-frameworks/lightcurvelynx`:
[issue #955](https://github.com/lincc-frameworks/lightcurvelynx/issues/955) (bugs A, B, D — ver sección
5). Solo **`PROPUESTA_salt2_info_mag_offset.md` (bug C) sigue sin publicar**, a la espera de revisión
con el profesor antes de decidir si va como issue de LightCurveLynx y/o post en el foro de Vera Rubin —
mismo criterio de siempre: no publicar sin confirmación explícita nueva.

La 5ª semilla de `PISN-STELLA-HYDROGENIC` (job NLHPC `12152052`) ya terminó: `46.475%`, consistente
con las otras 4 (`46.29%`, `46.03%`, `46.46%`, `45.50%`). El valor usado abajo para esa clase (`1.888x`
en la tabla histórica de Fase 59) es la cifra final con `n=5`, no provisional.

Este documento es el que conviene leer primero, antes de los 4 borradores de issue individuales
(`ISSUE_DRAFT_seed_propagation.md`, `PROPUESTA_salt2_info_mag_offset.md`,
`ISSUE_DRAFT_sed_wavelength_range.md`, `ISSUE_DRAFT_add_effect_param_collision.md`) — les da el marco
que explica por qué los 4 son reales y por qué ninguno, solo ni combinado, era la causa dominante de la
brecha de detección (esa causa era otra, y ya se encontró — sección 3-bis).

## 1. Resumen ejecutivo

En más de 70 fases de comparación entre LightCurveLynx (LCL) y SNANA, se confirmaron y corrigieron
**4 bugs reales de la librería** (o de `sncosmo`, de la cual LCL depende para su modelo SALT2) — cada
uno con evidencia de código de ambos lados e impacto numérico medido. Un análisis más amplio de
configuración (Fase 59) reveló que la sobre-detección agregada del catálogo era considerablemente más
grande de lo reportado hasta entonces, y que ninguno de los 4 bugs conocidos la explicaba. Una
investigación dedicada a encontrar la causa real (Fases 60-64) la encontró: el trigger de detección
reimplementado por este proyecto usaba el criterio equivocado de SNR. **Corregido y confirmado con 19
clases del catálogo completo, la brecha queda cerrada — ratio promedio `1.070x`, sin sesgo sistemático
relevante.**

## 2. Qué se creía hasta Fase 58

- El residuo fotométrico de SNIa/SALT2 (brillo pico, sin ruido, campos DDF) se había cerrado en
  Fase 37: de -0.52 mag a +0.005 mag, con `MAG_OFFSET` como causa identificada y corregida.
- El re-barrido formal de Fase 58 (13 clases SIMSED × 5 semillas, bajo el fix del pico bolométrico de
  Fase 56-57) había concluido que "el promedio del catálogo se mueve solo -4.8%" — es decir, que el
  fix no invalidaba de forma generalizada las tablas de referencia de detección ya publicadas.

## 3. Qué cambió en Fase 59 (histórico — la causa de este salto se explica en la sección 3-bis)

Fase 58 usaba, sin saberlo, un `rest_time_window_offset` (el análogo en LCL de `GENRANGE_TREST` de
SNANA — la ventana de fase-resto dentro de la cual puede caer la parte observada de una curva de luz)
**hardcodeado a `(-30, 100)` e idéntico para 12 de las 14 clases del catálogo**, en vez del
`GENRANGE_TREST` real de cada una (que en el `.INPUT` real de SNANA va de `-50/300` a `-100/1000`
según la clase). Esto se sabía como un hueco de auditoría desde Fase 40, pero solo se había corregido
para 2 clases (`SLSN-I`/`ILOT-MOSFIT`, Fase 43) — las otras 12 quedaron con el hardcode angosto,
inadvertido, durante 19 fases.

Al completar la corrección para las 11 clases restantes (Fase 59), el resultado fue el opuesto al
esperado: el ratio de sobre-detección LCL/SNANA **no mejoró, empeoró**, y de forma sustancial, en
las 13 clases del catálogo:

| clase | ratio Fase 58 (rango `-30/100`) | ratio Fase 59 (rango real) | Δ |
|---|---:|---:|---:|
| `SNIa-91bg` | 1.245 | 1.398 | +12.3% |
| `KN-K17` | 2.014 | 3.748 | +86.1% |
| `CaRT` | 8.819 | **27.45** | **+211%** |
| `SNIax` | 1.755 | 2.832 | +61.4% |
| `TDE-MOSFIT` | 1.192 | 1.397 | +17.2% |
| `SNII-NMF` | 1.285 | 1.835 | +42.8% |
| `SNIIn-MOSFIT` | 4.613 | 9.231 | +100% |
| `PISN-MOSFIT` | 1.597 | 2.203 | +37.9% |
| `KN-BULLA19` | 1.957 | 4.000 | +104% |
| `PISN-STELLA-HECORE` | 1.503 | 1.907 | +26.9% |
| `SLSN-I` (sin cambio, ya corregida en Fase 43) | 1.487 | 1.487 | 0% |
| `ILOT-MOSFIT` (sin cambio, ya corregida en Fase 43) | 7.091 | 7.091 | 0% |
| `PISN-STELLA-HYDROGENIC` (5/5 semillas) | 1.513 | 1.888 | +24.8% |
| **promedio catálogo (13 clases)** | **2.895** | **5.113** | — |

Ninguna clase mejoró. El hardcode angosto no era una aproximación neutral — estaba, sin que nadie lo
supiera, conteniendo artificialmente la sobre-detección real de LightCurveLynx frente a SNANA para la
mayoría del catálogo.

## 3-bis. La causa real, encontrada y confirmada (Fases 60-64, 67, 70) — cierra la brecha de la sección 3

Después de publicar la sección 3 como una pregunta abierta, tres fases de investigación dedicada
encontraron la causa real:

- **Fase 60**: extendió la comparación de brillo verdadero a las 10 clases SIMSED que nunca la
  tuvieron. Hallazgo clave: `ILOT-MOSFIT` es sistemáticamente **más tenue** en pico que SNANA (no más
  brillante) pero **sobre-detecta 7.09x** — descarta que un exceso de brillo explique la brecha; el
  mecanismo tenía que estar en la forma/duración de la curva o en el trigger mismo.
- **Fase 63**: extendió la metodología de comparación objeto-a-objeto (Fase 39) a una clase SIMSED por
  primera vez, reimplementando el trigger real (`searcheff.py`) sobre la fotometría real de SNANA.
  Hallazgo no buscado, el más importante: **el propio trigger reimplementado del proyecto** (usado en
  TODAS las mediciones de ratio desde Fase 4) daba una ventana de detección **~2.6x más ancha** que la
  real de SNANA — incluso alimentado con el flujo **real, observado, de SNANA** (no con el de LCL).
  Hipótesis formulada: el trigger modela cada época como un sorteo estocástico independiente sobre el
  flujo observado (con ruido), sin ningún límite adicional — mientras que SNANA real evalúa el SNR
  sobre el flujo *verdadero*.
- **Fase 64**: confirmó la hipótesis leyendo `snlc_sim.c` línea por línea — el trigger real de SNANA
  para LSST calcula el SNR sobre el flujo verdadero sin ruido (`SNR_CALC`), y llama explícitamente
  "SNR incorrecto" (comentario real en el código fuente) a la versión sobre flujo observado
  (`SNR_OBS`), que es la que este proyecto venía usando desde la Fase 4. Validado época a época contra
  el `PHOTFLAG&4096` real de SNANA: la fórmula anterior sobre-estimaba la detección real en `+17.1%`;
  la corregida la reproduce casi exacta (`+0.04%`).
- **Fase 65**: el fix se implementó en el código de producción (`run_simsed_poc.py`), pero el
  re-barrido completo quedó bloqueado temporalmente por un cupo de disco real agotado en NLHPC
  (incidente distinto, no relacionado con el fix en sí).
- **Fase 66**: mientras se esperaba resolver el cupo, se construyó un sistema de automatización de
  barridos (hash de identificación, deploy de un click, monitoreo, agregación) — pedido explícito del
  profesor para seguir la investigación de forma reproducible.
- **Fase 67**: primera carga de trabajo real del sistema nuevo — re-barrido de las 13 clases SIMSED
  (65 corridas, 5 semillas c/u, sin fallos). **El ratio promedio del catálogo baja de `5.113x` a
  `0.992x`.** El caso más extremo, `CaRT` (el peor de toda la investigación, `27.45x`), pasa a
  `1.011x`. Residuo honesto: 3 clases (`SNII-NMF`, `ILOT-MOSFIT`, `SNIIn-MOSFIT`) invierten el signo y
  quedan sub-detectando 10-17%.
- **Fase 70**: se confirmó que el fix de Fase 64 nunca se había portado a los otros 2 scripts de
  producción (`run_snia_ddf_poc.py` para `SNIa`/SALT2, `run_non1ased_poc.py` para las 5 clases
  `NON1ASED`) — seguían usando el trigger viejo. Portado y re-medidas las 6 clases restantes con 5
  semillas c/u: todas bajan sustancialmente (rango `1.17x-1.33x`, desde `1.6x-7.06x`).
- **Fase 71**: investigó el residuo de las 3 clases que quedaron sub-detectando (Fase 67). Descartó
  dos hipótesis con datos reales (muestreo poblacional de redshift y de extinción de host, ambos
  prácticamente idénticos entre LCL y SNANA) y confirmó fidelidad objeto-a-objeto casi perfecta
  (`99.93%` de recall). Concluyó que la mayor parte del residuo reportado es un efecto de normalización
  ya conocido (denominador post-filtro de contaminación de campo RGES, Fase 48, que solo aplica al lado
  SNANA) — los conteos crudos de detección son casi idénticos entre ambos simuladores (diferencias de
  `0-5%`, no el `10-17%` reportado).

**Resultado final, las 19 clases del catálogo completo (13 SIMSED + `SNIa`/SALT2 + 5 `NON1ASED`):
ratio promedio `1.070x`.** Ninguna clase queda por encima de `1.33x` (antes: hasta `27.45x` para
`CaRT`, hasta `7.06x` para `SNIax (NON1ASED)`).

## 4. Por qué esto no contradice el trabajo de los 4 bugs (sección 5) — solo lo pone en su lugar real

Los 4 bugs reales que este proyecto encontró y corrigió en LightCurveLynx/sncosmo (sección 5) son
verdaderos independientemente de la brecha de detección — cada uno tiene evidencia de código de ambos
lados y un impacto medido real. Pero ninguno era la causa dominante de la sobre-detección de la sección
3: ese mecanismo (el trigger usando `SNR_OBS` en vez de `SNR_CALC`) es un bug real más, encontrado
después (Fase 64) e independiente de los 4 anteriores — de hecho es el más importante de toda la
investigación en términos de impacto medido (explica un factor `~5x`, contra el impacto de 1 clase o
unas décimas de magnitud de los otros 4).

| Bug | Qué métrica cerró | Qué NO tocó |
|---|---|---|
| A · Fase 13 (rango λ) | Ratio de detección `SLSN-I`: 1.604x→1.577x (mejora chica, 1 sola clase) | No era el mecanismo detrás del salto catálogo-completo de Fase 59 |
| B · Fases 19-20 (seeds) | Reproducibilidad exacta entre corridas | Cero impacto en precisión o en ningún ratio — el propio borrador ya lo declara |
| C · Fase 37 (`MAG_OFFSET`) | Brillo pico SNIa/SALT2 sin ruido: -0.2646→+0.0054 mag | No aplica a las 13 clases SIMSED (usan NON1ASED/SIMSED, no SALT2) |
| D · Fase 51 (`add_effect()`) | Brillo banda u/g de `SNIax`/`CaRT`: mejora de 2 a 5x | No era el mecanismo dominante del salto de detección — el trigger (bug del proyecto, no de LCL) sí lo era |
| **E · Fase 64 (`SNR_CALC` vs `SNR_OBS`)** | **Ratio de detección catálogo completo: 5.113x→0.992x (13 SIMSED), 1.070x (19 clases)** | Es un bug del *código de este proyecto* (`searcheff.py`/`run_*_poc.py`), no de LightCurveLynx en sí — no aplica a los 4 borradores de issue |

**Los 4 bugs A-D son reales y siguen siendo válidos candidatos a reportar a LightCurveLynx — 3 de 4 ya
se publicaron (sección 5). El bug E (el más importante en impacto) es un bug de este proyecto, no de
LightCurveLynx, y ya está corregido en el código de producción.**

## 5. Los 4 hallazgos de LightCurveLynx/sncosmo — catálogo completo, estado real de publicación

| # | Hallazgo | Fase | Archivo/mecanismo real de LCL | Impacto medido | Estado |
|---|---|---|---|---|---|
| A | Flujo fuera de rango de λ no se suprime, se clampea | 13 | `SEDTemplate.evaluate_sed()` (`sed_template_model.py`) | 46% de la población de `SLSN-I` en z≥2.2; ratio 1.604x→1.577x | **Publicado** — [issue #955](https://github.com/lincc-frameworks/lightcurvelynx/issues/955) |
| B | Propagación de semilla incompleta en 4 nodos internos | 19-20 | `ObsTableRADECSampler`/`TableSampler`/`SIMSEDModel.from_dir()`/`MultiSEDTemplateModel` | Rompe reproducibilidad exacta, no precisión | **Publicado** — [issue #955](https://github.com/lincc-frameworks/lightcurvelynx/issues/955) |
| C | `MAG_OFFSET` de `SALT2.INFO` nunca se lee | 37 | `sncosmo.SALT2Source.__init__` | Residuo poblacional -0.2646→+0.0054 mag (98% de reducción) | **Sin publicar** — `PROPUESTA_salt2_info_mag_offset.md`, pendiente de revisión con el profesor |
| D | Colisión de nombre de parámetro en `add_effect()` | 51 | `PhysicalModel.add_effect()` (`physical_model.py`) | Extinción de host al 2-8% de lo nominal en 12 clases; `SNIax` u: -2.018→-0.760 mag | **Publicado** — [issue #955](https://github.com/lincc-frameworks/lightcurvelynx/issues/955) |

Los bugs A, B y D se combinaron en un solo issue (siguiendo la guía de contribución real de
LightCurveLynx, que no exige un template separado por bug) el 2026-09-01, con confirmación explícita
del usuario. El bug C queda deliberadamente fuera de esa publicación — es una propuesta de cambio de
comportamiento de `sncosmo` (no un bug puntual como los otros 3), y el usuario pidió guardarlo para
revisar con el profesor antes de decidir el canal (issue de LightCurveLynx vs. foro de Vera Rubin).

## 6. Las 5 claves de `SALT2.INFO` ignoradas — estado real de cada una

`sncosmo.SALT2Source` no lee `SALT2.INFO` en absoluto (bug C). Eso significa que, además de
`MAG_OFFSET`, se ignoran en silencio otras 4 claves:

- **`MAG_OFFSET`**: confirmada, medida, corregida (Fase 37) — 0.27 mag declarado, -0.2722 mag medido.
- **`SEDFLUX_INTERP_OPT`**: confirmada ignorada; Fase 39 descartó **una firma específica** (un
  artefacto que crece con la distancia al pico) — no un descarte general. Queda un residuo chico y
  sin tendencia (-0.01 a -0.03 mag) documentado en esa misma fase como cabo suelto, nunca investigado
  como posible offset constante.
- **`COLOR_OFFSET`**, **`MAGERR_*`**, **`RESTLAMBDA_RANGE`**: mencionadas como ignoradas en Fase 37,
  nunca testeadas con impacto medido propio (`RESTLAMBDA_RANGE` es el mecanismo del bug A, pero
  probado ahí como supresión de observación, un ángulo distinto del mismo problema de fondo).

## 7. Marco honesto para cualquier comunicación externa (propuesto, no redactado como texto final)

> Identificamos y corregimos 4 bugs reales de LightCurveLynx (o de su dependencia `sncosmo`), cada
> uno con evidencia de código de ambos lados y con impacto medido y reproducible — 3 de los 4 ya
> reportados al equipo de LightCurveLynx (issue #955). Una auditoría más amplia de configuración
> (Fase 59) mostró inicialmente que la sobre-detección agregada del catálogo era considerablemente
> mayor de lo reportado, y que ninguno de esos 4 bugs la explicaba. Una investigación dedicada
> (Fases 60-64) encontró la causa real: no era un bug de LightCurveLynx, sino del código propio de
> este proyecto — el trigger de detección reimplementado usaba el flujo observado (con ruido) en vez
> del flujo verdadero que usa el trigger real de SNANA. Corregido y confirmado con las 19 clases del
> catálogo completo (65+ corridas reales, sin fallos), el ratio promedio de sobre-detección baja de
> `5.1x` a `1.07x`, sin sesgo sistemático relevante. Consideramos LightCurveLynx, con este fix
> aplicado, razonablemente bien caracterizado tanto para brillo fotométrico como para eficiencia de
> detección en los campos DDF de esta campaña — con un residuo real pequeño (~15-30% en algunas
> clases minoritarias) cuya causa exacta sigue sin identificarse del todo (Fase 71), pero que ya no
> representa una brecha sistemática de catálogo completo.

## 8. Próximos pasos concretos

- ~~Correr el catálogo completo con todos los fixes reales apilados a la vez.~~ **Hecho** (Fases
  64-67, 70) — el fix del trigger (`SNR_CALC`) es el que se apiló sobre todos los fixes previos
  (32, 34, 36, 37, 42, 48, 49, 51, 53, 55, 56/57, 59) y cerró la brecha.
- Decidir si vale la pena testear el impacto de `COLOR_OFFSET`/`MAGERR_*` (sección 6). **Pendiente,
  baja prioridad** — no relacionado con la brecha de detección ya cerrada, es un residuo fotométrico
  chico y sin tendencia clara.
- ~~Decidir con el profesor si publicar los issues A-D.~~ **Hecho parcialmente** — A, B, D publicados
  (issue #955, 2026-09-01). C (`MAG_OFFSET`) sigue **pendiente**, a la espera de esa conversación.
- El residuo real y pequeño de 3 clases (`SNII-NMF`, `ILOT-MOSFIT`, `SNIIn-MOSFIT`, Fase 71) queda como
  pregunta abierta de baja prioridad — no es una brecha sistemática, es del orden de la varianza de
  muestra dado el tamaño de las poblaciones detectadas.
- El sistema de automatización de barridos (Fase 66) y el punto de enganche para entrenamiento de
  ALeRCE (`sweep_publish_dataset.py`, `ingestion_format: null` a propósito) quedan listos para cuando
  el formato de ingesta real se defina — no es una tarea de este proyecto resolver ese formato.

## 9. Referencias

- `NOTES.md` — Fase 13 (líneas 2678-2777), Fases 19-20 (líneas 3332-3468), Fase 37 (líneas
  5060-5341), Fase 39 (líneas 5465-5528), Fase 40 (líneas 5551-5656), Fase 43 (líneas 5831-5889),
  Fase 51 (líneas 6547-6687), Fase 58 (líneas 7275-7368), Fase 59 (líneas 7370-7513), Fase 60 (líneas
  7515-7656), Fase 61 (líneas 7657-7732), Fase 62 (líneas 7733-7848), Fase 63 (líneas 7849-7997),
  Fase 64 (líneas 7998-8132), Fase 65 (líneas 8133-8200), Fase 66 (líneas 8201-8336), Fase 67 (líneas
  8337-8439), Fase 68 (líneas 8440-8508), Fase 69 (líneas 8509-8563), Fase 70 (líneas 8564-8639),
  Fase 71 (líneas 8640-8735).
- `exploration/lightcurvelynx/ISSUE_DRAFT_seed_propagation.md` (publicado, issue #955)
- `exploration/lightcurvelynx/PROPUESTA_salt2_info_mag_offset.md` (sin publicar)
- `exploration/lightcurvelynx/ISSUE_DRAFT_sed_wavelength_range.md` (publicado, issue #955)
- `exploration/lightcurvelynx/ISSUE_DRAFT_add_effect_param_collision.md` (publicado, issue #955)
