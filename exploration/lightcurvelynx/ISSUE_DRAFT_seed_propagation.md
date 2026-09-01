# Borrador de issue — lincc-frameworks/LightCurveLynx

Redactado en Fase 19-20 (`NOTES.md`), evaluado (sin duplicados en el repo real, confirmado presente en
`main` a la fecha de redacción). **PUBLICADO** el 2026-09-01, con confirmación explícita del usuario,
combinado en un solo issue junto con `ISSUE_DRAFT_add_effect_param_collision.md` e
`ISSUE_DRAFT_sed_wavelength_range.md`: https://github.com/lincc-frameworks/lightcurvelynx/issues/955

## Título

seed= passed to samplers is silently dropped by internal child nodes (ObsTableRADECSampler,
TableSampler, SIMSEDModel, MultiSEDTemplateModel)

## Cuerpo

**Bug report**

Several samplers construct an internal child node (`NumpyRandomFunc`/`GivenValueSampler`) without
forwarding the `seed=`/`rng_info` that was passed to (or configured on) the parent. The parent node
itself is seeded correctly, but the randomness that actually matters (which row/template/position gets
picked) comes from the unseeded child — so two runs with the same top-level seed still diverge.
Confirmed by reading the installed source (0.5.2) and cross-checked against `main` on GitHub as of
today; reproduced with two independent processes using the same seed.

**Environment**
- lightcurvelynx 0.5.2 (pattern also present on `main`)
- Python 3.12.3, Linux

**Instances found**

1. `ObsTableRADECSampler.compute()` (`math_nodes/ra_dec_sampler.py`): when `self.radius > 0`, sub-FOV
   jitter uses `rng = rng_info if rng_info is not None else np.random.default_rng()` — `rng_info` never
   gets populated when constructing the sampler directly and calling `simulate_lightcurves()`, so it
   silently falls back to unseeded. Workaround: `radius=0.0` (not usable if you need the jitter).

2. `TableSampler.__init__` (`math_nodes/given_sampler.py`, base class of `ObsTableRADECSampler`):
   `self.add_parameter("selected_table_index", NumpyRandomFunc("integers", low=0, high=self._num_values), ...)`
   — no `seed=` forwarded, even though this decides which real row/pointing gets assigned to each
   object. Workaround: `sampler.setters["selected_table_index"].dependency.set_seed(my_seed)` after
   construction.

3. `SIMSEDModel.from_dir()` (`models/sed_template_model.py`): `self._sampler_node =
   GivenValueSampler(all_inds, weights=weights)` — same pattern, template selection isn't reproducible.
   Workaround: `model._sampler_node.set_seed(my_seed)`.

4. `MultiSEDTemplateModel.__init__` (same module, used by NON1ASED-style multi-template classes):
   same pattern — its internal template-selection sampler is built without forwarding `seed=`.
   Confirmed with the same two-separate-processes test as the other three (byte-identical output
   after seeding it manually, divergent before).

**Reproduction**: run the same script twice as separate processes with an identical seed; resulting
photometry (row counts, SNR, detections) differs. Seeding the four sites above manually makes results
byte-identical between runs.

**Suggested fix**: forward the parent's `seed=`/`rng_info` into these internally-constructed nodes at
construction time, or document the workaround prominently (none of the three mention it). Happy to
share our reproduction script or open a PR.
