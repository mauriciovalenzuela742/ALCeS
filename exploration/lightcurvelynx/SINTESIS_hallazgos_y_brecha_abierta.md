# Síntesis — 4 bugs reales de LightCurveLynx/sncosmo corregidos, pero una brecha de sobre-detección sin explicar

**Estado: datos completos (13/13 clases, 5/5 semillas c/u), brecha todavía sin explicación.** No
publicar ni citar los 4 borradores de issue como conclusión cerrada sin confirmación explícita nueva
del usuario — mismo criterio que rige en el resto del proyecto (ningún `.md` de este catálogo se
publica como issue de GitHub, post de foro, etc. sin esa confirmación).

La 5ª semilla de `PISN-STELLA-HYDROGENIC` (job NLHPC `12152052`) ya terminó: `46.475%`, consistente
con las otras 4 (`46.29%`, `46.03%`, `46.46%`, `45.50%`). El valor usado abajo para esa clase
(`1.888x`) es la cifra final con `n=5`, no provisional — el cambio respecto al valor con `n=4`
(`1.884x`) fue de +0.2%, no movió el promedio del catálogo.

Este documento es el que conviene leer primero, antes de los 4 borradores de issue individuales
(`ISSUE_DRAFT_seed_propagation.md`, `PROPUESTA_salt2_info_mag_offset.md`,
`ISSUE_DRAFT_sed_wavelength_range.md`, `ISSUE_DRAFT_add_effect_param_collision.md`) — les da el marco
que explica por qué los 4 son reales y a la vez no cierran la investigación.

## 1. Resumen ejecutivo

En 59 fases de comparación entre LightCurveLynx (LCL) y SNANA, se confirmaron y corrigieron **4 bugs
reales de la librería** (o de `sncosmo`, de la cual LCL depende para su modelo SALT2) — cada uno con
evidencia de código de ambos lados e impacto numérico medido. Pero la sobre-detección total del
catálogo de clases del proyecto sigue sin explicarse del todo: el hallazgo más reciente (Fase 59)
muestra que la brecha real entre LCL y SNANA es bastante más grande de lo que se creía hace apenas
una semana, y que ninguno de los 4 bugs conocidos —solos o combinados— la explica.

## 2. Qué se creía hasta Fase 58

- El residuo fotométrico de SNIa/SALT2 (brillo pico, sin ruido, campos DDF) se había cerrado en
  Fase 37: de -0.52 mag a +0.005 mag, con `MAG_OFFSET` como causa identificada y corregida.
- El re-barrido formal de Fase 58 (13 clases SIMSED × 5 semillas, bajo el fix del pico bolométrico de
  Fase 56-57) había concluido que "el promedio del catálogo se mueve solo -4.8%" — es decir, que el
  fix no invalidaba de forma generalizada las tablas de referencia de detección ya publicadas.

## 3. Qué cambió en Fase 59

Fase 58 usaba, sin saberlo, un `rest_time_window_offset` (el análogo en LCL de `GENRANGE_TREST` de
SNANA — la ventana de fase-resto dentro de la cual puede caer la parte observada de una curva de luz)
**hardcodeado a `(-30, 100)` e idéntico para 12 de las 14 clases del catálogo**, en vez del
`GENRANGE_TREST` real de cada una (que en el `.INPUT` real de SNANA va de `-50/300` a `-100/1000`
según la clase). Esto se sabía como un hueco de auditoría desde Fase 40, pero solo se había corregido
para 2 clases (`SLSN-I`/`ILOT-MOSFIT`, Fase 43) — las otras 12 quedaron con el hardcode angosto,
inadvertido, durante 19 fases.

Al completar la corrección para las 11 clases restantes (Fase 59), el resultado es el opuesto al
esperado: el ratio de sobre-detección LCL/SNANA **no mejora, empeora**, y de forma sustancial, en
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

Ninguna clase mejora. El hardcode angosto no era una aproximación neutral — estaba, sin que nadie lo
supiera, conteniendo artificialmente la sobre-detección real de LightCurveLynx frente a SNANA para la
mayoría del catálogo.

## 4. Por qué esto reformula la narrativa, sin contradecir el trabajo previo

Los 4 bugs reales que este proyecto encontró y corrigió en LightCurveLynx/sncosmo (sección 5) son
verdaderos independientemente de Fase 59 — cada uno tiene evidencia de código de ambos lados y un
impacto medido real. La aparente tensión ("¿cómo puede haber 4 bugs cerrados si la brecha creció?")
se resuelve mirando qué midió cada uno exactamente:

| Bug | Qué métrica cerró | Qué NO tocó |
|---|---|---|
| A · Fase 13 (rango λ) | Ratio de detección `SLSN-I`: 1.604x→1.577x (mejora chica, 1 sola clase) | Nunca extendido a las otras 13 clases; nunca re-medido junto con el `GENRANGE_TREST` real de Fase 59 |
| B · Fases 19-20 (seeds) | Reproducibilidad exacta entre corridas | Cero impacto en precisión o en ningún ratio — el propio borrador ya lo declara |
| C · Fase 37 (`MAG_OFFSET`) | Brillo pico SNIa/SALT2 sin ruido: -0.2646→+0.0054 mag | Nunca se tradujo a un cambio en el ratio de detección de las 13 clases SIMSED (esas usan NON1ASED/SIMSED, no SALT2 — es una cadena de código distinta) |
| D · Fase 51 (`add_effect()`) | Brillo banda u/g de `SNIax`/`CaRT`: mejora de 2 a 5x | Nunca se re-corrió el ratio de detección de esas clases combinando este fix CON el `GENRANGE_TREST` real de Fase 59 — son dos correcciones que nunca se apilaron en una sola medición |

**Los 4 bugs son reales, verificados con evidencia de código de ambos lados, e independientes entre
sí — pero ninguno fue medido nunca contra la métrica agregada de detección de 13 clases que usan
Fase 58/59, y esa es justamente la métrica que se disparó de 2.9x a 5.1x.** No hay contradicción
lógica: simplemente nunca se hizo la medición que uniría ambas cosas. Ese es el hueco de investigación
real que queda abierto — no una falla en el trabajo ya hecho.

## 5. Los 4 hallazgos — catálogo completo

| # | Hallazgo | Fase | Archivo/mecanismo real de LCL | Impacto medido | Estado |
|---|---|---|---|---|---|
| A | Flujo fuera de rango de λ no se suprime, se clampea | 13 | `SEDTemplate.evaluate_sed()` (`sed_template_model.py`) | 46% de la población de `SLSN-I` en z≥2.2; ratio 1.604x→1.577x | Borrador listo — `ISSUE_DRAFT_sed_wavelength_range.md` |
| B | Propagación de semilla incompleta en 4 nodos internos | 19-20 | `ObsTableRADECSampler`/`TableSampler`/`SIMSEDModel.from_dir()`/`MultiSEDTemplateModel` | Rompe reproducibilidad exacta, no precisión | Borrador listo (sin publicar) — `ISSUE_DRAFT_seed_propagation.md` |
| C | `MAG_OFFSET` de `SALT2.INFO` nunca se lee | 37 | `sncosmo.SALT2Source.__init__` | Residuo poblacional -0.2646→+0.0054 mag (98% de reducción) | Borrador listo (sin publicar) — `PROPUESTA_salt2_info_mag_offset.md` |
| D | Colisión de nombre de parámetro en `add_effect()` | 51 | `PhysicalModel.add_effect()` (`physical_model.py`) | Extinción de host al 2-8% de lo nominal en 12 clases; `SNIax` u: -2.018→-0.760 mag | Borrador listo — `ISSUE_DRAFT_add_effect_param_collision.md` |

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
> uno con evidencia de código de ambos lados y con impacto medido y reproducible. Sin embargo, una
> auditoría más amplia de configuración (Fase 59) muestra que la sobre-detección agregada del
> catálogo es considerablemente mayor de lo que habíamos reportado, y que ninguno de los 4 bugs
> conocidos —solo o en combinación— la explica cuantitativamente. No recomendamos todavía tratar
> LightCurveLynx como validado para pronóstico de eficiencia de detección a escala de catálogo
> completo; sí lo consideramos válido y bien caracterizado para brillo fotométrico de SNIa/SALT2 en
> DDF, el alcance real que se puso a prueba con ese nivel de rigor.

## 8. Próximos pasos concretos (no bloqueantes para publicar los issues A-D)

- Correr el catálogo completo de 14 clases con **todos** los fixes reales apilados a la vez (Fases
  32, 34, 36, 37, 42, 48, 49, 51, 53, 55, 56/57, 59) — hasta ahora cada fase midió su propio delta de
  forma aislada; nunca se hizo una corrida que combine todo el conocimiento acumulado en una sola
  medición. **Pendiente** — decisión explícita del usuario de no lanzar cómputo nuevo en NLHPC en esta
  sesión, solo actualizar dashboard/docs con lo ya medido.
- Decidir si vale la pena testear el impacto de `COLOR_OFFSET`/`MAGERR_*` (sección 6). **Pendiente.**
- **Hecho (2026-08-26)** — `docs/lcl_qc/lcl_qc_index.json` actualizado con los ratios reales de Fase
  48/59 para las 13 clases SIMSED, leyendo los `summary.json` reales de las 65 corridas en NLHPC (no
  derivado de las tablas de esta síntesis) — conteos absolutos, medias/std/min/max de 5 semillas,
  filas reordenadas por `ratio_mean_5seeds` (el dashboard asume la primera fila = mejor caso, la
  última = peor caso).
- **Hecho (2026-08-26)** — el callout final de la sub-tab "Causas investigadas" del dashboard
  (`docs/index.html`) ya no presenta la brecha de Fase 16 (1.42x-10.83x) como vigente; se agregó un
  callout nuevo (`Estado vigente — Fase 48/58/59`) con el promedio real del catálogo (5.113x) y el
  peor caso real (`CaRT`, 27.45x), con link a este documento.
- Decidir con el profesor si publicar los issues A-D ya (son válidos independientemente del resultado
  de esta brecha) o esperar a tener una explicación más completa. **Pendiente.**

## 9. Referencias

- `NOTES.md` — Fase 13 (líneas 2678-2777), Fases 19-20 (líneas 3332-3468), Fase 37 (líneas
  5060-5341), Fase 39 (líneas 5465-5528), Fase 40 (líneas 5551-5656), Fase 43 (líneas 5831-5889),
  Fase 51 (líneas 6547-6687), Fase 58 (líneas 7275-7368), Fase 59 (líneas 7370-7513).
- `exploration/lightcurvelynx/ISSUE_DRAFT_seed_propagation.md`
- `exploration/lightcurvelynx/PROPUESTA_salt2_info_mag_offset.md`
- `exploration/lightcurvelynx/ISSUE_DRAFT_sed_wavelength_range.md`
- `exploration/lightcurvelynx/ISSUE_DRAFT_add_effect_param_collision.md`
