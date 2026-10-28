# ztf_dr2_ia: notas del inventario

Script: `ztf_dr2_ia.py`. El zip completo (`/download/data`, ztfsniadr2_lite.zip) pesa 1.37 GB:
no se bajó. Se usan los archivos remotos que lee el paquete `ztfcosmo` (repo GitHub
ZwickyTransientFacility/ztfcosmo, `io.py`: `https://ztfcosmo.in2p3.fr/download/<ruta con "/"
cambiado por "__">`):
- `tables__snia_data.csv` (1.5 MB) y `tables__spec_dataframe.parquet` (0.3 MB).
- Solo los primeros 8 kB de cada curva de luz (HTTP Range) para leer la cabecera; total
  ~30 MB descargados, 47 MB en disco con las tablas, en `raw/ztf_dr2_ia/lc_headers/` (3628 archivos). La corrida tarda ~30 min la primera
  vez; luego usa la caché.

## Resultado
- 3628 filas = 3628 SNe Ia del paper (Rigault+25). Coincide.
- 5138 espectros (spec_dataframe) = 5138 del paper. Todas las SNe tienen >= 1 espectro.
- Subclase desde `sub_type`: norm, norm/99aa, norm/04gs y vacío -> `Ia` (3186);
  91t, 99aa, 99aa/91t -> `Ia-91T` (269); 91bg, 91bg/86G -> `Ia-91bg` (92); iax -> `Iax` (23);
  csm -> `Ia-CSM` (14); 03fg, 02es, 18byg, 00cx, 19yvq -> `Ia-other` (44). Los "norm/X" son
  ambiguos y se dejan como `Ia`.
- z y origen (`source`): z_gal (2203) y z_SEDm/z_nonSEDm (320, líneas del host en el espectro
  de la SN) -> `host_spec`; z_snid (1081) -> `spec`; z_override/z_unknown (24) -> `unknown`.
  La correspondencia sale de las fracciones de arXiv:2407.06828 (61% catálogo, 9% líneas del
  host, 30% SNID), que coinciden con estos conteos; los códigos no están documentados.
- `ebv_mw` = mwebv; RA/Dec de la SN; IAU en `alt_names` (`SN 2018lq`).
- Fotometría: de la tabla "baseline_corr (applied)" de cada cabecera se suma `n_sn` por filtro
  (puntos dentro de `sn_range`, la ventana de la SN, que es amplia: del orden de -100 a +500 d
  respecto del máximo). Por eso `n_phot` (mediana 472) **sobrestima** los puntos útiles
  alrededor del máximo e incluye no detecciones. Bandas: g;r;i (2635), g;r (945), otras (12).
- 36 SNe sin curva en el servidor (devuelve la página HTML en vez del CSV): `n_phot` y `bands`
  vacíos.
- Fases vacías: la cabecera no da la cobertura real con detecciones.
- Sin distancia ni metalicidad (las tablas de host dan masa y color, no O/H).
