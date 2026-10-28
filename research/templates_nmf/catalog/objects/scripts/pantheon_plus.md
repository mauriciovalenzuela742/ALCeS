# pantheon_plus: notas del inventario

Script: `pantheon_plus.py`. Archivo `Pantheon+SH0ES.dat` (580 kB) del repo GitHub
PantheonPlusSH0ES/DataRelease; definiciones de columnas en el README de
`Pantheon+_Data/4_DISTANCES_AND_COVAR/`.

## Resultado
- 1701 curvas de luz, 1543 CID distintos, 1542 SNe tras unir `2005df_ANU` con `2005df`
  (`2008fv_comb` solo aparece con sufijo; queda como `SN 2008fv`). El paper/abstract dice
  1550 SNe; diferencia de 8 no resuelta (posible conteo distinto de duplicados entre surveys).
- Todas `Ia`. 43 calibradores (IS_CALIBRATOR=1): `dist_mod` = CEPH_DIST (distancia Cefeida
  del host SH0ES), `dist_method=independent`. Resto (1499): `dist_mod` = media de MU_SH0ES
  entre apariciones (Tripp estandarizado con M de SH0ES), `dist_method=hubble_flow`.
- z = zHEL. `z_type=unknown`: el archivo no dice si cada z es del host o de la SN (la
  muestra es de SNe confirmadas espectroscópicamente, pero el origen por objeto no está aquí).
- `ebv_mw` = MWEBV. Sin bandas, puntos ni fases a propósito: la fotometría es la de los
  surveys originales y ya se cuenta en `csp_i_ia`, `cfa3_cfa4_photometry`, `foundation_dr1`.
- Nombres: CIDs tipo IAU -> `SN 2011fe`; CIDs numéricos se prefijan con el survey de su
  primera aparición (`SDSS-16314`, `PS1MD-...`, `DES-...`, `SNLS-...`) para que no colisionen;
  el CID original va en `alt_names`.
