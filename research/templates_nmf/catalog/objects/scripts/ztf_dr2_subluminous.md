# ztf_dr2_subluminous: SALTADA (sin part CSV propio)

Paper: arXiv:2512.21256, "ZTF SN Ia DR2 follow-up: Characterization of subluminous Type Ia
supernovae in the ZTF DR2 full sample" (título y abstract verificados en arxiv.org). Muestra:
124 subluminosas (87 91bg-like, 12 86G-like, 18 04gs-like, 7 02es-like) y 194 espectros.

## Por qué no hay part CSV
- La sección "Data availability" (versión HTML de arXiv) dice que las tablas completas
  (Tablas 3 y 4) solo están en CDS. El FTP/VizieR de CDS no respondía desde este equipo y el
  espejo vizier.idia.ac.za no se consultó por número de catálogo porque el paper no lo da
  (solo "J/A+A/"). La HTML de arXiv solo muestra versiones parciales (32 nombres ZTF).
- Los 124 objetos son un subconjunto de ZTF DR2, ya inventariado en `ztf_dr2_ia` con los
  mismos datos (curvas y espectros). Un part separado duplicaría `n_phot`/`n_spec` en la unión
  por nombre de `viability.py`.
- La tabla de DR2 (`snia_data.csv`, columna `sub_type`) ya trae las etiquetas: 81 `91bg`,
  11 `91bg/86G`, 18 `norm/04gs`, 7 `02es` = 117 (el paper reclasifica hasta 124). En
  `ztf_dr2_ia` se mapean 91bg y 91bg/86G a `Ia-91bg`, 02es a `Ia-other` y norm/04gs a `Ia`.

Pendiente: cuando CDS responda, buscar el catálogo del paper (A&A 2026) y, si tiene tipo por
objeto, usarlo para corregir la subclase en `ztf_dr2_ia` en vez de crear filas nuevas.
