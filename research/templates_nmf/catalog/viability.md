# Viabilidad de templates NMF por subclase

Generado por `viability.py`. No editar a mano.

- Filas de entrada: 20905 de 25 fuentes; objetos únicos tras cruzar nombres y posiciones (≤3"): 15912.
- `foto`: z espectroscópico, ≥3 bandas y ≥15 puntos.
- `espectro`: `foto` y ≥3 espectros.
- `completo`: `espectro`, metalicidad y distancia usable (independiente o z ≥ 0.01).
- Los conteos de puntos y espectros suman entre fuentes: si dos fuentes publican los mismos datos, se cuentan dos veces.

| Subclase | Objetos | z espec. | foto | espectro | Metalicidad | completo | Conflictos de tipo |
|---|---|---|---|---|---|---|---|
| Ia | 10506 | 4249 | 2716 | 308 | 188 | 8 | 0 |
| II | 2543 | 406 | 146 | 111 | 115 | 72 | 0 |
| Ia-91T | 539 | 366 | 279 | 46 | 3 | 2 | 0 |
| IIn | 440 | 109 | 16 | 8 | 4 | 0 | 3 |
| SLSN-I | 329 | 259 | 232 | 87 | 16 | 9 | 9 |
| Ic | 320 | 86 | 24 | 10 | 32 | 0 | 0 |
| Ib | 277 | 58 | 27 | 18 | 0 | 0 | 3 |
| IIb | 257 | 58 | 15 | 5 | 3 | 0 | 1 |
| Ia-91bg | 187 | 126 | 94 | 24 | 0 | 0 | 0 |
| Ic-BL | 147 | 45 | 10 | 6 | 15 | 0 | 0 |
| Ia-other | 82 | 31 | 25 | 2 | 0 | 0 | 0 |
| SLSN-II | 73 | 15 | 0 | 0 | 8 | 0 | 10 |
| SN-other | 62 | 9 | 1 | 0 | 0 | 0 | 0 |
| Ibn | 54 | 11 | 3 | 3 | 0 | 0 | 0 |
| Iax | 53 | 26 | 18 | 9 | 0 | 0 | 0 |
| Ia-CSM | 33 | 16 | 14 | 6 | 0 | 0 | 0 |
| Icn | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Ca-rich | 4 | 1 | 1 | 0 | 0 | 0 | 0 |

## Fuentes incluidas

- `ztf_bts`: 11484 filas
- `ztf_dr2_ia`: 3628 filas
- `pantheon_plus`: 1542 filas
- `ptf_ccsn_hosts_schulze21`: 888 filas
- `ztf_bts_snii_hinds25`: 493 filas
- `cfa_ia_spectra`: 462 filas
- `snfactory_hosts`: 460 filas
- `cfa3_cfa4_photometry`: 279 filas
- `gomez24_slsn_catalog`: 265 filas
- `aamer25_slsn_spectra`: 233 filas
- `foundation_dr1`: 225 filas
- `csp_i_ia`: 134 filas
- `csp_snii_spectra_gutierrez17`: 122 filas
- `anderson16_snii_hii_metallicity`: 119 filas
- `csp1_snii_photometry_anderson24`: 94 filas
- `cfa_sesn_spectra_modjaz14`: 73 filas
- `cfa_sesn_photometry_bianco14`: 64 filas
- `cfa_snii_hicken17`: 60 filas
- `galbany16_ubvriz`: 51 filas
- `ptf_ic_icbl_hosts_modjaz20`: 48 filas
- `ptf_iin_nyholm20`: 42 filas
- `taddia16_iptf_snii_metallicity`: 39 filas
- `csp1_se_photometry_stritzinger18`: 34 filas
- `csp2_sesn_nir_spectra`: 34 filas
- `ptf_slsn_hosts_perley16`: 32 filas
