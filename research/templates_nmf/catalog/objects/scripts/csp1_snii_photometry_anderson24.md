# csp1_snii_photometry_anderson24

- Datos: VizieR J/A+A/692/A95 por FTP de CDS (sn.dat, photopt.dat, photnir.dat). Paper verificado: arXiv:2410.06738.
- Resultado: 94 SNe, 9817 puntos ópticos y 1872 NIR en 76 SNe. **Coincide exactamente con el abstract.**
- Sin z, E(B−V) ni época de explosión: VizieR no los trae y en Zenodo (13743303) solo están como imágenes PNG, que no se pueden leer por máquina. Los 74 objetos de CSP-I reciben z de Gutiérrez+17 o Galbany+16 al cruzar por nombre. Los ~20 de CSP-II (ASASSN-*, LSQ*, SN 2012–2015) quedan sin z.
- Nombres: se usa el nombre de Simbad sin espacios (`ASASSN-14gm`) y el corto de la tabla (`ASASS14gm`) va como alternativo.
- CDS bloquea los User-Agent con "Mozilla" con una página anti-bot (Anubis). `_common.fetch` usa otro UA y rechaza las respuestas HTML.
