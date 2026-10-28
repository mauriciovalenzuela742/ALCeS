# cfa_ia_spectra: notas del inventario

Script: `cfa_ia_spectra.py`. Usa solo tablas de VizieR J/AJ/143/126 (Blondin+12); no baja el
tarball de espectros (`cfaspec_snIa_20120322.tar.gz`, 164 MB), que no hace falta para contar.

## Resultado
- 462 filas = 462 SNe Ia del paper. 2603 espectros en `tablea1` = 2603 del paper. Coincide.
- Subclase: clasificación Wang+09 de `table4` (solo 246 SNe con espectro a <=7 d del máximo):
  18 `Ia-91T`, 20 `Ia-91bg`; 7 marcadas "peculiar, sin clase Wang" (2000cx, 2002cx, 2005hk,
  2006gz, 2007if, 2008A, 2008ae) -> `Ia-other`. El resto -> `Ia`. No se separan Iax ni
  super-Chandra porque la tabla no los nombra por subtipo (solo los marca como peculiares).
  Las 216 SNe sin espectro cerca del máximo quedan como `Ia` aunque puedan ser peculiares.
- z: heliocéntrico de NED (galaxia huésped) -> `host_spec`, salvo las 24 de `table3`:
  `SNID` -> `spec` (7); líneas del host propio (`abs`, `em`, Scalzo+10) -> `host_spec`;
  cúmulo cercano (flag f), CBET o Bailey+09 -> `unknown` (5).
- Fase: rango de la fase en reposo de `tablea1` respecto del máximo en B; los espectros con
  flag `@` (sin t_max fiable) se excluyen. 271 SNe con fase; 191 sin máximo fiable quedan vacías.
- Sin coordenadas, distancia, extinción ni metalicidad por objeto en estas tablas.
