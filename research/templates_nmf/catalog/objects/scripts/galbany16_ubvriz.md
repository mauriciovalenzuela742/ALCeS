# galbany16_ubvriz

- Datos: repositorio de los autores `lgalbany/51_SNeII_LC` (la URL del paper dice `51_SNII_LC` y da 404), tarball de 55 kB (Zenodo 10.5281/zenodo.1172117). Tabla 1 del fuente LaTeX de arXiv:1511.08402 para las notas.
- Resultado: 51 SNe, 2516 puntos. **Coincide con el paper ("2,516 photometric points").** Las bandas son U (7 SNe), B, V, R (28), I y z (3).
- `dist_method`: `independent` para Tully–Fisher de NED (notas d y f, 14 SNe); `hubble_flow` para la distancia de luminosidad por z con H0=68 (paper §absmag); `unknown` para 2002gw (nota e, DM con datos de SN II).
- `z_type`: `spec` si el z fue medido por los autores (^*), `host_spec` si viene de NED.
- Subclase: IIb para 2003bg (nota h), II para las parecidas a 87A (1999br, 2000cb, 2003cv; nota g) e IIP para el resto según el `.info`.
- La línea `Filter:` de un archivo `.out_` está mal (dice B donde debía decir R). Se usa el sufijo del nombre de archivo.
- "SN 200210" es "SN 210" en Gutiérrez+17 y Anderson+16; los nombres no cruzan (ver la nota de gutierrez17).
- Resuelto en `viability.py` con `NAME_ALIASES` ("SN 210" → "200210").
