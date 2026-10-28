# cfa_snii_hicken17

- Datos: los dos tarballs del archivo CfA (`fmalcolm2017/`, 0.5 MB de curvas y 12.6 MB de espectros) y la Tabla 1 del fuente LaTeX de arXiv:1706.01030 (título verificado).
- Resultado: 60 SNe (34 II, 5 IIP, 19 IIn, 1 IIb y 1 Ibn, SN2010al), igual que el paper. Hay 54 SNe con óptico y 14 con NIR (46+8 y 6+8 según el paper). NIR: 816 puntos, **igual que el paper**.
- **Diferencia:** el archivo óptico (sistema natural) tiene 3143 puntos y el paper dice 2932. No hay filas duplicadas. Incluye 34 puntos en R y 34 en I (4Shooter), aunque el paper dice que las bandas son u'UBVr'i'. No se pudo aclarar el origen de los 211 de más; se cuentan las filas del archivo.
- Espectros: `cfasnII_mjdspec.dat` lista 195 espectros de 48 SNe (lo mismo dice el README); la Tabla 1 suma 192 de 47. Las diferencias son SN2005ay (4 espectros en el archivo, 0 en la tabla) y SN2007rt (2 frente a 3). `n_spec` usa el archivo.
- z: z_helio del host (NED) → `host_spec`, salvo 2006at, 2006iw y 2008bx (z de CBET o D'Andrea+) → `unknown`. La fuente no da coordenadas, E(B−V), distancias ni fases.
