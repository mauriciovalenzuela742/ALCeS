# foundation_dr1: notas del inventario

Script: `foundation_dr1.py`. Fuentes:
- Zip del repo GitHub `djones1040/Foundation_DR1` (rama master, ~1-2 MB): archivos SNANA de
  `Foundation_DR1/` (180) y `Foundation_DR1_NoCosmo/` (45), y `Foundation_DR1.FITRES.TEXT`.
- VizieR J/MNRAS/475/193 (Foley+18) por asu-tsv (espejo idia si CDS no responde):
  `table1` (274 SNe con nombres y tipo), `table3` (72 redshifts no catalogados con su origen).

## Resultado
- 225 filas = 225 curvas de luz del paper (180 "cosmológicas" + 45 NoCosmo). Coincide.
- Subclase (columna Type de table1, que ya incluye las reclasificaciones de table5):
  181 `Ia`, 31 `Ia-91T` (incluye "91T?"), 5 `Ia-91bg`, 7 `Ia-other` (06gz-like y
  "00cx?; 91bg?"), 1 `Ic` (PS15zn, reclasificada como SN Ic en table5).
- 8 SNe del repo no aparecen en table1 (ASASSN-17co, AT2016aj, ATLAS16dqf, PS16cqa, PS16em,
  PS17tn, PS17yt, PS16drf): quedan como `Ia` (SNTYPE=1 en el archivo SNANA).
- Nombre: IAU de table1 si existe (`SN 2016afk`), si no el SNID del repo; los demás nombres
  (descubrimiento, alternativos, SNID) van en `alt_names`.
- z: REDSHIFT_HELIO del header. `z_type`: `spec` si table3 dice que sale de rasgos de la SN
  (7); `host_spec` si sale del núcleo/posición de la SN en el host (table3) o es redshift
  catalogado del host (resto, 218). Supuesto: los no listados en table3 son de NED (host),
  como dice el paper para los "catalogados".
- `ebv_mw`: MWEBV del header (SFD98 con corrección SF11, según el README).
- Fotometría: g;r;i;z, 7 174 puntos (líneas OBS). Fase en reposo respecto de PKMJD de SALT2
  (FITRES, 180 SNe) o SEARCH_PEAKMJD (45 NoCosmo). 14 SNe con fase mínima < -30 d y 14 con
  máxima > +200 d (extremos -58 y +670 d),
  que vienen de epochs sueltas en los archivos; no se filtraron.
- Sin espectros publicados en el repo (`n_spec` vacío), sin distancia ni metalicidad. El
  repo trae masa del host (ZPEG), que no es una columna del esquema.
