# ptf_iin_nyholm20

- Metadatos: tablas `IInsummary` y `speclog` del fuente LaTeX de arXiv:1906.05812 (título verificado). Resultado: **42 SNe IIn**, igual que el paper. Cada una trae coordenadas, z (0.0288–0.3135), μ, E(B−V)_MW, nombres alternativos y un espectro de clasificación con su fase respecto del pico (en reposo).
- z: medido por los autores con gaussianas sobre Hα de sus espectros → `spec`. μ: calculado desde z (ΛCDM, H0=70, corrección de infall) → `hubble_flow`.
- Fotometría: tabla `table2` de VizieR J/A+A/637/A73 vía `asu-tsv`. CDS dejó de responder el 2026-10-27, así que el script prueba primero `vizier.cds.unistra.fr` y después el espejo `vizier.idia.ac.za`; el FTP de CDS queda como último recurso. Resultado (2026-10-28, espejo IDIA): **42/42 SNe con fotometría, 19 251 filas, 3787 detecciones** (las filas sin `mag` son límites superiores, `lmag`). Mediana de 65 detecciones por SN; 6 SNe solo tienen R (P48).
- Según el paper, las bandas son B, g, R, r, i y z (P48: Mould R y g; P60: griz y B).
- PTF10fjh = SN2010bq, que también está en Hicken+17 (cruce por `alt_names`).
