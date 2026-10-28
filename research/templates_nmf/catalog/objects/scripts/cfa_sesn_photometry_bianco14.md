# cfa_sesn_photometry_bianco14 (Bianco+14, VizieR J/ApJS/213/19)

- Tablas: table1 (tipo, coordenadas, descubrimiento), table2 (cz NED del host, m-M, E(B-V) MW SF11) y table6 (fotometría estándar).
- **64 SNe**, igual al paper. **6462 medidas** = 4543 ópticas + 1919 NIR, igual al ReadMe de VizieR (el arXiv dice 2142 NIR).
- Tipos: 23 Ib, 19 Ic, 9 IIb, 9 Ic-BL, 2 Ibn (2005la "Ib-n/IIb-n" y 2006jc), 1 Ca-rich (2007ke) y 1 SN-other (2007iq "Ic/Ic-BL"). "Ib-pec" se asigna a Ib.
- z = cz/c del host (NED), con `z_type=host_spec`. Hay valores negativos (2004gk, cz=-122 km/s, en Virgo); se dejan como los da la fuente.
- dist_mod viene de NED/HyperLEDA sin método declarado, por eso `dist_method=unknown`.
- Fase: VizieR no trae fecha de máximo, así que la fase va respecto del **descubrimiento** (días del observador). Queda vacía en 2 SNe porque el año de descubrimiento no coincide con el nombre: 2009jf (VizieR repite la fecha de 2001ej) y 2007aw (dice 2006 Mar 22).
- Sin ebv_host.
