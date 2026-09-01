# Borrador de issue — lincc-frameworks/LightCurveLynx

Redactado a partir de Fase 13 (`NOTES.md`), en el marco de una investigación de 59+ fases comparando
LightCurveLynx contra SNANA. **PUBLICADO** el 2026-09-01, con confirmación explícita del usuario,
combinado en un solo issue junto con `ISSUE_DRAFT_add_effect_param_collision.md` e
`ISSUE_DRAFT_seed_propagation.md`: https://github.com/lincc-frameworks/lightcurvelynx/issues/955

## Contexto para quien revise esto (no forma parte del reporte en sí)

LightCurveLynx documenta que sus `LightcurveTemplateModel` no periódicos ("caen a 0.0") fuera de su
rango de fase por defecto. Esa documentación es correcta solo en el eje de fase — en el eje de
longitud de onda no hay ningún chequeo de rango en absoluto, y el comportamiento real (confirmado
leyendo y ejecutando el código, no solo la documentación) es peor que "cae a cero": devuelve un
valor de flujo constante, clampeado al borde del rango nativo del SED. El fix propio del proyecto
(`restlambda_gate()`/`restlambda_gate_vec()` en `run_simsed_poc.py`) solo se aplicó a la clase más
expuesta (`SLSN-I`) como workaround — no toca el código de la librería, y nunca se extendió a las
otras 13 clases SIMSED del catálogo del proyecto.

## Título propuesto

`SEDTemplate.evaluate_sed()` clamps flux to the edge value outside the SED's native wavelength range
instead of returning zero or suppressing the observation — silently generates non-trivial flux
arbitrarily far outside the template's valid range

## Cuerpo

**Bug report**

`SEDTemplate.evaluate_sed()` (`sed_template_model.py`) initializes its output array to zero and only
fills in the PHASE axis within `self.times[0]-self.times[-1]` — the documented zero-padding is real,
but only along phase. Along the wavelength axis there is no range check at all:
`RectBivariateSpline(...)(wavelengths, grid=True)` gets called with any wavelength, inside or outside
the SED's native range. Tested interactively against a real production model
(`SIMSED.SLSN-I-MOSFIT`, template 0): at wavelengths below 1000 Å or above 11000 Å, the returned flux
is **not zero — it's a constant value, clamped exactly to the edge** (querying 100, 300, 500, 999,
and 1000 Å all returned the identical flux). The model keeps generating a real, non-trivial
observation no matter how far outside its declared range you ask.

For comparison, SNANA (the reference simulator this package is meant to be compatible with) suppresses
the observation entirely when this happens — it never generates it. From `genmag_SEDtools.c` (real
comment in the source, "Mar 22 2017 -- bail if any part of filter trans it outside of model range"):

```c
if ( LAMOBS_MIN/z1 < SEDMODEL.LAMMIN[ised] ) { continue ; }
if ( LAMOBS_MAX/z1 > SEDMODEL.LAMMAX[ised] ) { continue ; }
```

If the full observed-frame bandpass doesn't map completely inside the SED's declared rest-frame
wavelength range, SNANA never builds that flux-table cell at all — the observation simply doesn't
exist. SNANA even tracks this explicitly with its own variable (`NOBS_UNDEFINED`, distinct from
`NOBS`, available in `SIMGEN_DUMP` output), confirming this is treated as a real, expected code path
on that side, not an edge case.

**Environment**

- `lightcurvelynx` (installed via `pip install "lightcurvelynx[all]"`)
- Python 3.12.3, Linux (NLHPC cluster)
- Model directory: `SIMSED.SLSN-I-MOSFIT` (real production SIMSED model, publicly distributed with
  SNANA/PLAsTiCC-style catalogs)

**Reproduction / evidence**

1. Direct interactive query of `SEDTemplate.evaluate_sed()` (or the underlying `RectBivariateSpline`)
   at wavelengths progressively farther outside the native range (100/300/500/999/1000 Å against a
   template whose native range starts at 1000 Å): flux is identical across all five points — a flat
   clamp, not a decaying or zero value.
2. Population-level exposure: for `SLSN-I` with its real rate model (`MD14`, SFR-weighted) and its
   real redshift range (up to z=9.7), **46% of the entire simulated population already sits at
   z≥2.2** — the point where the `u` band's rest-frame wavelength range starts falling outside the
   template's declared 1000-11000 Å range. This isn't a rare tail case; it's close to half the class's
   simulated catalog.
3. Applying a gate that replicates SNANA's real suppression condition (band-by-band, redshift-aware)
   before flattening the light curve output: 14.7% of all generated observations for `SLSN-I` get
   suppressed. Detection ratio (LightCurveLynx/SNANA) for that class moves from 1.604±0.036 to
   1.577±0.039 — a real, small improvement (direction correct, though within 1σ of seed-to-seed
   noise at 5 seeds).

**Suggested fix**

`evaluate_sed()` should check the wavelength axis the same way it already checks the phase axis —
either return zero (matching the documented behavior for phase) or, ideally, propagate a clear
"out of range" signal so the calling code can suppress the observation the way SNANA does, instead of
silently returning a physically meaningless clamped value. At minimum, a loud warning the first time
a query falls outside the native wavelength range would prevent this exact failure mode (population
biased toward the tail of the redshift distribution, where clamped-and-real-looking flux can pull in
spurious detections) for the next user of a wide-redshift-range model.

A working reference implementation of the gate exists in this project's exploratory code
(`restlambda_gate()`/`restlambda_gate_vec()` in `run_simsed_poc.py`) — happy to share it, or open a
PR against LightCurveLynx's `SEDTemplate` implementation directly.
