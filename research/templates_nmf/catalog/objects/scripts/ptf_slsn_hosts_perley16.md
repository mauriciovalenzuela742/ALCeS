# ptf_slsn_hosts_perley16 (Perley+16, arXiv:1604.08207)

- No está en VizieR: se usa la fuente LaTeX del paper (título verificado). Se leen la tabla 1 (tab:slsne) y la tabla 6 (tab:linediagnostics).
- **32 SNe**, igual al paper. Las clases I e I-R se asignan a SLSN-I y la clase II a SLSN-II.
- oh12 = columna "PP04 O3" (O3N2, calculada con el código de Bianco+16), para que sea comparable con Modjaz+20.
  - Hay **26 con valor**.
  - Quedan vacías las 6 sin líneas (09atu, 09cwl, 10scc, 10vwg, 12gwu y 12mkp) y las cotas superiores ("<").
- oh12_type = **host_global**: según la sección 3, la extracción incluye todo el flujo nebular del host. Esto confirma lo que se suponía en sources.csv. La excepción es PTF10tpz, cuyo espectro es solo nuclear (`unknown`).
- ebv_mw sale de la tabla 1 (SF11). El A_V de la tabla 6 es del gas del host y no se usa.
- z_type=unknown: la tabla no dice si el z es del host o de la SN.
