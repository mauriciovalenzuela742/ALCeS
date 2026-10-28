# cfa3_cfa4_photometry: notas del inventario

Script: `cfa3_cfa4_photometry.py`. Tablas de VizieR J/ApJ/700/331 (CfA3, Hicken+09) y
J/ApJS/200/12 (CfA4, Hicken+12), sistema estándar.

Nota técnica: el ftp de CDS (`cdsarc.cds.unistra.fr`) dejó de responder a mitad de la sesión;
la table6 de CfA4 se baja por `asu-tsv` (solo columnas SN y Filt) con espejo de respaldo
`vizier.idia.ac.za` (función `viz_tsv` en `_ia_common.py`). Mismo contenido.

## Resultado
- 279 filas = 185 (CfA3) + 94 (CfA4). Sin SNe en común: coincide con los papers.
- 16 984 puntos = 11 499 (CfA3 table5) + 5 485 (CfA4 table6). Coincide con los registros.
- PTF10bjs y SN 2009hp (CfA4) no tienen filas en la table6 estándar (sí podrían estar en la
  table5 natural, 5 522 filas); quedan con n_phot=0.
- Bandas: U, B, V, R, I, r', i' (CfA3) y U/u', B, V, r', i' (CfA4).
- Subclase: todas `Ia`; las tablas no dan subtipo por objeto.
- z: CfA4 da z heliocéntrico "principalmente de NED" -> `host_spec` (94). CfA3 table1 no tiene
  z; se usa el zCMB de table8 (solo 72 de las 185 están en esa tabla, que cubre CfA3+OLD con
  buen muestreo) con `z_type=unknown`. 113 SNe CfA3 sin z: la unión por nombre con
  `cfa_ia_spectra` u otras fuentes debería completarlo.
- Extinción: `ebv_mw` de CfA4 table1 (94); `ebv_host` = E(B-V) de MLCS2k2 (R_V=1.7) de CfA3
  table8 (72).
- Sin fecha de máximo en estas tablas: fases vacías.
