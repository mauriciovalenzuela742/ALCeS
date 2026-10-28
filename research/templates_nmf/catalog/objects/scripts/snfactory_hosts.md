# snfactory_hosts: notas del inventario

Script: `snfactory_hosts.py`. Tabla VizieR `J/ApJ/770/107/galaxies` (Childress+13a, arXiv:1304.4719,
título verificado en arxiv.org), bajada por `asu-tsv`. El ftp/ReadMe de CDS no respondía
desde este equipo durante la sesión; se usó el espejo `vizier.idia.ac.za` (`viz_tsv` en
`_ia_common.py`). Las descripciones de columna salen de la cabecera de asu-tsv; las notas
(2) y (4) del ReadMe (referencias de z) no se pudieron leer.

## Resultado
- 460 filas (460 SNe distintas): 382 `SNF...`, 57 `SN ...`, 21 `PTF...`. `sources.csv` dice 469;
  la tabla VizieR tiene 460 registros. Diferencia no resuelta sin el ReadMe/paper completo.
- Todas `Ia` (muestra de SNe Ia de SNfactory; la tabla no da subtipo).
- z: heliocéntrico del host para 455 (`host_spec`). Las 5 sin z (PTF10qyz, PTF10wnm,
  PTF10xyt, PTF10yut, PTF10zdk) tienen flag "masa derivada con el z de la SN".
- Metalicidad: 191 hosts con `ZT04` (escala Tremonti+04), `oh12_type=host_global`. Indicador
  original: 162 N2 (PP04), 20 R23 (KK04), 9 O3N2 (PP04); `oh12_calib` = `<indicador>->T04`.
  La nota de `sources.csv` hablaba de 327 registros de metalicidad; en la tabla VizieR solo
  191 tienen valor final (las demás son AGN/compuestas o sin espectro: Class = 53 AGN,
  50 Comp., 205 SF, 152 vacías).
- No se copian RA/Dec (son del host) ni E(B-V) (del host entero, no de la línea de visión
  de la SN). Las columnas de SN (bandas, fotometría, espectros, fase) quedan vacías: esta
  fuente es solo de hosts y sirve para unir metalicidad por nombre.
