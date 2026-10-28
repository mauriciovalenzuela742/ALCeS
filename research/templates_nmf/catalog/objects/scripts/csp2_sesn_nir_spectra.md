# csp2_sesn_nir_spectra (Shahbandeh+22, arXiv:2110.12083)

- Datos: SESNe_NIR_reduced_data.tgz (1,9 MB) de csp.obs.carnegiescience.edu/data, con licencia CC BY 4.0. Trae **75 FITS de 34 SNe**, igual al abstract.
- Tipo, z y fase salen de la fuente LaTeX del paper (título verificado):
  - tipo: tab:classification (columna "This work");
  - z: tab:redshift_JD y tab:1specs;
  - fase: tab:journal, respecto del máximo en B (LSQ13ddu respecto de LSQ-gr y 2013dk respecto de V).
- Cinco SNe quedan como SN-other:
  - 4 sin tipo en el paper: LSQ12fwb, OGLE-2013-SN-134, OGLE-2014-SN-014 y PSN J11220840-3804001;
  - LSQ13doo, que el paper clasifica como "Ic/Ic-BL".
- Las 8 SNe de tab:1specs quedan sin fase y con `z_type=unknown`. El paper las excluye del análisis por no tener fase fiable, y no distingue si su z viene de ATels o del host.
- ra/dec quedan vacíos:
  - las coordenadas de tab:redshift_JD están en columnas ocultas y corridas una fila desde SN 2012P;
  - las del header FITS son de apuntado.
