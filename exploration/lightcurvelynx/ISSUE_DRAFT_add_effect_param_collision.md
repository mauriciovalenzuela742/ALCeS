# Borrador de issue — lincc-frameworks/LightCurveLynx

Redactado a partir de Fase 51 (`NOTES.md`), en el marco de una investigación de 59+ fases comparando
LightCurveLynx contra SNANA. **PUBLICADO** el 2026-09-01, con confirmación explícita del usuario,
combinado en un solo issue junto con `ISSUE_DRAFT_seed_propagation.md` e
`ISSUE_DRAFT_sed_wavelength_range.md`: https://github.com/lincc-frameworks/lightcurvelynx/issues/955

## Contexto para quien revise esto (no forma parte del reporte en sí)

De los 4 bugs reales de LightCurveLynx/sncosmo que encontró esta investigación, este es el que tiene
más peso técnico: no es una diferencia de convención astronómica ni una clave de configuración mal
leída — es un bug en el mecanismo genérico de composición de efectos (`add_effect()`), que afectaría
a cualquier usuario que combine dos efectos cuyos parámetros comparten un nombre, sin importar el
dominio. En este proyecto se encontró combinando extinción de la Vía Láctea y extinción de host
(ambas vía `ExtinctionEffect`, ambas registrando el parámetro `"ebv"`) — el efecto agregado en
segundo lugar (host) perdía su propio valor en silencio y heredaba el de MW. El bug apagó la
extinción de host real al ~2-8% de su valor nominal en las 12 clases del catálogo del proyecto que
la usan, durante todas las fases anteriores que las tocaron, antes de ser encontrado y corregido.

## Título propuesto

`PhysicalModel.add_effect()` silently drops a parameter when two effects register the same name —
breaks composing two `ExtinctionEffect` instances (e.g. Milky Way + host galaxy extinction)

## Cuerpo

**Bug report**

`add_effect()` (`lightcurvelynx/models/physical_model.py`, around line 470-476) registers each
effect's parameters by name:

```python
for param_name, setter in effect.parameters.items():
    if param_name not in self.setters:
        self.add_parameter(param_name, setter, ...)
```

If a second effect declares a parameter whose name is already registered by a previously-added
effect, it is simply skipped — no exception, no warning, nothing logged. The second effect's own
setter is never registered; at evaluation time it silently receives whatever value the first effect's
setter produces instead.

This is not a hypothetical collision: `ExtinctionEffect.__init__()` (`lightcurvelynx/effects/
extinction.py`), the library's own base class for extinction, always registers its parameter under
the fixed name `"ebv"`, regardless of what the effect instance is conceptually for. Any model that
adds two `ExtinctionEffect` instances — e.g. one for Milky Way foreground extinction and one for host
galaxy extinction, the standard setup for any realistic supernova/transient simulation — hits this
collision by construction. The second one added (in our case, host extinction) never gets its own
setter registered, and receives the first one's (MW's) value at every evaluation.

Confirmed with a real smoke test against a live `ModelNode` (not simulated, minimal repro): after
adding MW extinction (`ebv` sampled from a real Milky Way E(B-V) distribution, typically 0.006-0.025)
and then host extinction (`ebv` meant to be sampled independently, up to ~1.0), querying the host
effect's requested value returns the MW value instead:

```
host effect requested ebv=0.4 -> model delivers 0.02
```

**Environment**

- `lightcurvelynx` (installed via `pip install "lightcurvelynx[all]"`)
- Python 3.12.3, Linux (NLHPC cluster)

**Reproduction / evidence**

1. Minimal repro: build a `PhysicalModel`, call `add_effect()` with an `ExtinctionEffect` configured
   for MW extinction, then call `add_effect()` again with a second `ExtinctionEffect` configured for
   host extinction with a distinct, much larger `ebv` distribution. Query `model.setters` — only one
   setter under `"ebv"` exists (the first one added). Evaluate the model and confirm the "host" effect
   is actually using the MW-scale value.
2. Population-level impact measured in this project's real pipeline (12 classes in the catalog that
   declare host extinction): host `E(B-V)` effectively reduced to **~2-8% of its nominal value**
   across every one of those classes, for every phase of the investigation that touched them before
   this was found. Real before/after table for two of the affected classes (`SNIax`/`CaRT`, per-band
   photometric residual against SNANA, `u`/`g`/`r`/`i`/`z`/`y`):

   | class | band | Δmag before fix | Δmag after fix |
   |---|---|---:|---:|
   | `SNIax` | u | -2.018 | -0.760 |
   | `SNIax` | g | -1.114 | -0.208 |
   | `SNIax` | r | -0.609 | +0.122 |
   | `CaRT` | u | -1.200 | -0.623 |
   | `CaRT` | g | -0.884 | -0.283 |
   | `CaRT` | r | -0.602 | -0.117 |

   (Full 6-band table for both classes available on request.) A control class with no host extinction
   at all (`SNIa-91bg`) was re-run after the fix and came back byte-identical to its pre-fix output —
   confirming zero side effect for models that don't hit the collision.
3. Post-fix verification: a second smoke test with distinct parameter names for each effect
   (`ebv_param_name="host_ebv"` workaround, see below) shows two independent setters
   (`setters with ebv: ['ebv', 'host_ebv']`) sampling at the correct, distinct scales for MW vs. host.

**Suggested fix**

`add_effect()` should raise an exception (or, at minimum, emit a loud warning) when a parameter name
collision is detected, instead of silently discarding the second effect's setter. This is a generic
composition bug, not specific to extinction — any two effects sharing a parameter name would hit the
same silent failure. A reasonable API-level fix would be requiring effects to either declare
non-colliding parameter names by default (e.g. namespaced by effect instance) or requiring the caller
to pass an explicit alias when adding a second instance of an effect class that's already present.

The workaround used in this project (not a substitute for a library fix): a subclass
(`ClippedExtinctionEffect` in this project's `snana_params.py`) accepts an `ebv_param_name` override,
re-maps its own parameter to that name after `super().__init__()`, and the project adds an `assert`
right after `add_effect()` confirming the expected setter name exists — so if a collision like this
recurs (e.g. with a future third rest-frame effect), the run fails loudly instead of silently
producing wrong physics. Happy to share the reproduction script or open a PR.
