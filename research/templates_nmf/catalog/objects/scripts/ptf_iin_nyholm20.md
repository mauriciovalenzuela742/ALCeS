# ptf_iin_nyholm20

- Metadatos: tablas `IInsummary` y `speclog` del fuente LaTeX de arXiv:1906.05812 (título verificado). Resultado: **42 SNe IIn**, igual que el paper. Cada una trae coordenadas, z (0.0288–0.3135), μ, E(B−V)_MW, nombres alternativos y un espectro de clasificación con su fase respecto del pico (en reposo).
- z: medido por los autores con gaussianas sobre Hα de sus espectros → `spec`. μ: calculado desde z (ΛCDM, H0=70, corrección de infall) → `hubble_flow`.
- **Falta la fotometría.** La tabla completa está solo en VizieR J/A+A/637/A73 (CDS). Durante esta sesión todo el dominio de CDS (cdsarc, vizier, cds.unistra.fr) dejó de responder por TCP, en los puertos 443 y 80. El espejo de CfA redirige a CDS. Por eso `bands` y `n_phot` quedaron vacíos y estas SNe no pasan el nivel `foto` de viability.
- El script ya intenta bajar el ReadMe y los archivos de CDS: lee el layout byte a byte y cuenta las detecciones (mag < 90; 99 = límite superior) por SN y filtro. **Hay que volver a correrlo cuando CDS responda**; no se ha probado contra el archivo real, así que conviene revisar lo que imprime ("archivos de CDS usados").
- Según el paper, las bandas son B, g, R, r, i y z (P48: Mould R y g; P60: griz y B).
- PTF10fjh = SN2010bq, que también está en Hicken+17 (cruce por `alt_names`).
