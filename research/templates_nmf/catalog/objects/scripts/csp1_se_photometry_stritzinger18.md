# csp1_se_photometry_stritzinger18 (Stritzinger+18a, VizieR J/A+A/609/A134)

- **34 SNe** (10 IIb, 11 Ib, 11 Ic, 2 Ic-BL), igual al paper. n_phot suma 4029 magnitudes no nulas en las tablas 4 a 8 (óptico Swope y du Pont, y NIR).
- z heliocéntrico de table1 (NED o líneas del host), con `z_type=host_spec`.
- Fase: (JD - T(B)max)/(1+z) sobre todas las épocas. No coincide con las columnas Phase1/Phase2 de table1 (por ejemplo, 2008aq: +311 en table1 y +121 en la fotometría). Esas columnas deben describir otra cosa, quizás la espectroscopía; el ReadMe solo dice "Phase range".
- **ebv_host** sale del paper compañero Stritzinger+18b (arXiv:1707.07615, título verificado), que no está en VizieR. El script baja su fuente LaTeX y toma -E(V-B)_host de la tabla tab:EVMX. Hay **21 SNe** con valor.
  - Las SNe "minimally reddened" no aparecen en esa tabla: el paper dice 9, pero la resta da 10.
  - Tampoco aparecen 2006fo, 2008gc y 2009ca.
  - Todas ellas quedan vacías; no se les pone 0.
- La tabla de VizieR no trae E(B-V) de la Vía Láctea.
