# csp_i_ia: notas del inventario

Script: `csp_i_ia.py`. Descarga (~13 MB en total):
- `CSP_Photometry_DR3.tgz` (tab1 + un archivo SNooPy por SN) y `CSP_spectra_DR1.tgz`, desde
  https://csp.obs.carnegiescience.edu/data
- VizieR J/AJ/154/211 `table2.dat` (subtipo SNID) y `table3.dat` (MJD del máximo en B).

## Resultado
- 134 filas = 134 SNe del paper (Krisciunas+17). Coincide.
- Subclases (table2, columna Subtype1): 96 normal + 4 sin subtipo -> `Ia` (100); 13 91bg-like
  -> `Ia-91bg`; 5 91T-like -> `Ia-91T`; 5 `Iax`; 2 `Ia-CSM`; 9 `Ia-other` (2 SC, 1 06gz-like,
  2 06bt-like, 4 86G-like). Decisión: 86G-like va a `Ia-other`, no a `Ia-91bg`, para no mezclar
  transicionales en un template de 91bg.
- z: heliocéntrico de la galaxia huésped (NED/SDSS según la nota de tab1) -> `z_type=host_spec`,
  rango 0.0037-0.0835 (igual al paper).
- Fotometría: 19 376 puntos en total. Bandas normalizadas (V0/V1 -> V; Jrc2/Jdw -> J;
  Ydw -> Y; Hdw -> H). 118 SNe con alguna banda NIR en los archivos SNooPy; el paper dice 120.
  No se investigó la diferencia de 2.
- Espectros: 630 archivos de 91 SNe en el tarball DR1. El paper dice 604 espectros CSP de 93
  SNe (más 228 de literatura que no van en el tarball). Diferencia no resuelta: el tarball
  puede incluir los 35 espectros "de otros observadores" y faltarían 2 objetos.
- Fase: días en reposo respecto de T(Bmax) (table3; si falta, Tpeak), unión de fotometría y
  épocas de espectros. 4 SNe sin máximo en table3 (2005gj, 2006bt, 2009J, 2010ae) quedan sin
  fase. SN 2007if (super-Chandra) da phase_min = -56 d: hay datos muy anteriores al máximo
  o el máximo de table3 es poco fiable; no se corrigió.
- Sin distancia, extinción ni metalicidad en estas tablas (columnas vacías).
