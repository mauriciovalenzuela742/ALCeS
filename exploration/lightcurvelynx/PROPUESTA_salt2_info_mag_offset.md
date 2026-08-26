# Borrador de issue — lincc-frameworks/LightCurveLynx (via `sncosmo`)

Redactado en Fase 37 (`NOTES.md`), a raíz del hallazgo que cerró la investigación de fidelidad
fotométrica SNIa/SALT2 entre LightCurveLynx y SNANA. **No publicado** — a pedido explícito del
usuario, queda guardado acá para revisar con el profesor antes de decidir si se publica como issue
de GitHub y/o post en el foro de Vera Rubin. No correr `gh issue create` ni postear en ningún foro
sin confirmación explícita nueva.

## Contexto para quien revise esto (no forma parte del reporte en sí)

Esta investigación (37 fases, `exploration/lightcurvelynx/NOTES.md`) comparó LightCurveLynx contra
SNANA para SNIa/SALT2 en los campos DDF reales de la campaña de este proyecto. Un residuo
acromático de ~0.26 mag (LightCurveLynx sistemáticamente más brillante) resistió 8 fases completas
de investigación de la cadena física SALT2 (Fases 23-31: color law, punto cero, interpolación 2D,
incluso instrumentar y recompilar el binario C real de SNANA) antes de encontrarse que la causa no
era física en absoluto: un archivo de configuración del modelo que un simulador lee y el otro no.
El hallazgo es genérico — afecta a cualquier usuario de LightCurveLynx que instancie
`sncosmo.SALT2Source` con un directorio de modelo real que declare `MAG_OFFSET` en su
`SALT2.INFO`, no solo a este proyecto.

## Título propuesto

`SALT2Source(modeldir=...)` silently ignores `MAG_OFFSET` (and other keys) declared in the model's
`SALT2.INFO` file — real production SALT2 models (e.g. `SALT2.WFIRST-H17`, used by SNANA/PLAsTiCC)
declare a non-zero offset that never gets applied

## Cuerpo

**Bug report**

`sncosmo.SALT2Source(modeldir=...)` reads exactly four files from the model directory it's pointed
at: the two flux templates (`salt2_template_0/1.dat`), the color-law file
(`salt2_color_correction.dat`), and the error/covariance files. It never opens or reads
`SALT2.INFO`, even though that file lives in the same directory and is treated as part of the model
by every SNANA-compatible tool. Confirmed by reading the installed source
(`sncosmo==2.13.0`, via `inspect.getsource`) — neither the string `"SALT2.INFO"` nor `"MAG_OFFSET"`
appears anywhere in `SALT2Source.__init__` or the rest of the class.

`SALT2.INFO` for a real production model can declare `MAG_OFFSET: <value>` — an additive magnitude
offset that SNANA applies to *every* magnitude generated from that model
(`genmag_SALT2.c`, function that assembles the observed magnitude:
`magobs = ZP - 2.5*log10(flux) + INPUT_SALT2_INFO.MAG_OFFSET;`, real line 2257 of the file as
distributed in the public SNANA source, default value `0.0` when the key is absent). For the model
this project uses in production, `SALT2.WFIRST-H17` (used broadly in LSST/Rubin-adjacent
SALT2 work, including PLAsTiCC), `SALT2.INFO` declares:

```
MAG_OFFSET: 0.27
```

Since LightCurveLynx's `SncosmoWrapperModel` wraps `SALT2Source` directly, any simulation built on
this model directory is missing that entire term — silently. There is no error, no warning, no
degraded-mode message. The resulting magnitudes are simply wrong by a constant, real, and (for this
model) fairly large amount (0.27 mag ≈ 25% in flux) in every band.

**Environment**

- `lightcurvelynx` (installed via `pip install "lightcurvelynx[all]"`, current as of this
  investigation)
- `sncosmo==2.13.0`
- Python 3.12.3, Linux (NLHPC cluster)
- Model directory: `SALT2.WFIRST-H17` (real SNANA/PLAsTiCC production model, publicly distributed)

**Reproduction / evidence**

1. Paired object-by-object comparison: fed LightCurveLynx the *exact* `SIM_SALT2x0/x1/c`/redshift/
   `t0`/MW `E(B-V)` that a real SNANA run (`snlc_sim.exe`) generated for the same objects (available
   per-object in the real `_HEAD.FITS` output of the run), and evaluated
   `compute_noise_free_lightcurves()` at `rest_phase=0`. Residual against SNANA's own
   `SIM_PEAKMAG_<filt>`: **−0.2722 mag**, flat across all 6 LSST bands and across the full redshift
   range (std 0.022–0.033 mag on ~570-600 objects per band) — i.e. a clean constant offset, not
   scatter.
2. `SALT2.INFO` of the exact model directory used declares `MAG_OFFSET: 0.27`. Measured value and
   declared value agree to 0.002 mag.
3. Verified LightCurveLynx's own photometry is otherwise correct: for the same synthetic SALT2
   object, LightCurveLynx's bandflux matches `sncosmo.Model.bandmag(band, "ab", t0)` (a second,
   independent code path inside the same package) to ≤0.006 mag, and matches a hand-written AB
   photon-counting integral over `model.flux()` to 0.0000 mag. The bug isn't in LightCurveLynx's
   flux/magnitude machinery — it's that `SALT2Source` never picks up `MAG_OFFSET` from the model
   directory in the first place.
4. Applying `MAG_OFFSET` as a post-hoc correction (added to the absolute-magnitude/`x0` normalization
   before generating light curves) reduces the measured population-level residual for this project's
   full DDF campaign (2000 objects) from −0.2646 mag to +0.0054 mag — a 98% reduction, with the
   small remainder consistent with unrelated, already-quantified effects (Galactic-extinction
   bookkeeping between the two comparison files used).

**Suggested fix**

`SALT2Source.__init__` (or a wrapper one level up, e.g. LightCurveLynx's own SALT2 loading path)
should parse `SALT2.INFO` from `modeldir` if present, and apply at least `MAG_OFFSET` (and ideally
`COLOR_OFFSET`, which the file format also supports and SNANA also applies) when computing
magnitudes/flux normalization. At minimum, if parsing the full file is out of scope, a loud warning
when `SALT2.INFO` is present in `modeldir` but ignored would prevent this exact silent-bias failure
mode for the next person who points `SALT2Source` at a real production model directory instead of
the packaged registry entries (`sncosmo.get_source("salt2", version="2.4")`, etc., which presumably
were calibrated without depending on this key — this project's registry-based benchmark script,
which does *not* use a real `modeldir=`, was intentionally left uncorrected for this same reason).

Happy to share the reproduction scripts (deleted from the exploratory environment per this
project's convention of not versioning throwaway analysis scripts, but easily reconstructed) or open
a PR against `sncosmo` and/or LightCurveLynx's SALT2 loading path.

## Nota aparte: candidato para el foro de Vera Rubin / comunidad SNANA-LightCurveLynx

Más allá del bug report técnico de arriba (que apunta a `sncosmo`), puede valer la pena un post
separado, más narrativo, dirigido a quienes estén evaluando LightCurveLynx como reemplazo de SNANA
para simulación LSST: la lección de que **verificar que los archivos de datos del modelo sean
idénticos (checksums) no alcanza** — hace falta verificar que el código nuevo lea *todas* las
claves de configuración que el código viejo lee, no solo los archivos de datos gruesos. Es el mismo
tipo de hallazgo que motivó las Fases 24/32/34 de esta investigación (ley de extinción MW asumida en
vez de leída del `.INPUT` real, sampler bifurcado con la probabilidad de rama incorrecta, `Om0`
asumido en vez del default real de SNANA) llevado a su forma más pura. Esto queda como sugerencia,
no como texto redactado — a definir con el profesor si tiene sentido como post aparte o como parte
del mismo hilo del issue.

## Nota aparte 2 — SALT2.INFO tiene más claves ignoradas que MAG_OFFSET

`sncosmo.SALT2Source` no lee `SALT2.INFO` en absoluto (ver cuerpo del issue arriba) — además de
`MAG_OFFSET`, también se ignoran en silencio `COLOR_OFFSET`, `SEDFLUX_INTERP_OPT`, `MAGERR_*` y
`RESTLAMBDA_RANGE` si el modelo real las declara. De estas, solo `SEDFLUX_INTERP_OPT` se puso a
prueba (Fase 39 de `NOTES.md`): se descartó como causa de un artefacto que crece con la distancia al
pico, pero no se probó como posible offset constante pequeño (queda un residuo real de -0.01 a -0.03
mag sin explicar, documentado como cabo suelto en esa misma fase). `COLOR_OFFSET` y `MAGERR_*` nunca
se testearon. Se documenta como extensión del mismo hallazgo, no como un bug nuevo — el fix sugerido
arriba (parsear `SALT2.INFO` completo, no solo `MAG_OFFSET`) ya lo cubre.
