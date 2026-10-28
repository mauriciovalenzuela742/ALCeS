# ztf_bts_snii_hinds25

- Datos: archivo auxiliar `anc/Hinds_ea_25.dat` de arXiv:2503.19969v3 (título verificado), en formato CDS.
- Resultado: **493 filas** (377 II, 35 IIb, 81 IIn), con z entre 0.0024 y 0.263. El abstract habla de 639 SNe II del BTS y de una submuestra "highly complete" de 377 clasificadas espectroscópicamente. Las 377 II coinciden con esa submuestra. La tabla publicada no trae las 639: tiene las 377 II más las IIb y las IIn, que el paper analiza aparte. La nota de `sources.csv` (`n_objects=639`) habla de la muestra inicial.
- `z_type=unknown`: según el paper, clasificaciones y redshifts vienen del BTS (Qin et al., en prep.) o de TNS, sin decir si el z es del host o de la SN. Por eso estos objetos no cuentan como `spec` en viability.
- No hay conteo de puntos, espectros ni coordenadas. Las bandas son ZTF g y r (`ztfg;ztfr`), porque el paper mide subidas en las dos. La columna `Ahostg` es A_g del host estimada por color, no E(B−V), y no se copia.
- Una fila no tiene nombre TNS ("-"): queda sin `alt_names`.
