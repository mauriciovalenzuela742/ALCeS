# csp_snii_spectra_gutierrez17

- Datos: tablas del fuente LaTeX de arXiv:1709.02487 (`table_info.tex` y `table_spec.tex`) y el tarball de CSP (8.7 MB), que solo se usa como control.
- Resultado: 122 SNe y 888 espectros (filas de `table_spec`). **Coincide con el abstract (888 espectros, 122 SNe).** La fase va de 3 a 363 d desde la explosión y z de 0.00076 a 0.077, también como en el paper.
- La columna "N of spectra" de `table_info` suma 891: 1999em dice 12 pero lista 10, y 2007X dice 12 pero lista 11. Se usa el número de filas de `table_spec`, que coincide con los FITS por fecha del tarball.
- El tarball tiene 123 carpetas: incluye SN00cb (2000cb, parecida a 87A), que no está en la tabla del paper. Son 989 FITS, porque los brazos azul y rojo van en archivos separados.
- z = v_helio/c. `host_spec` si la velocidad es de NED, `spec` si es de espectros propios (^1) y `unknown` si viene de Asiago (^2). E(B−V)_MW de Schlafly+11 según la tabla.
- "SN 210" (SNFactory, sin nombre IAU) es el mismo objeto que "SN 200210" en Galbany+16. Los nombres no cruzan y esta fuente no da coordenadas.
