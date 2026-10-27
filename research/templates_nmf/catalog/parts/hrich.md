# Fuentes de SN con hidrógeno (II, IIP, IIL, IIb, IIn, SLSN-II)

Archivo: `hrich.csv`: 33 filas, 14 con `verified=yes`, validado con `validate_catalog.py` (OK).

## Búsquedas hechas

| Cadena / vía | Qué salió |
|---|---|
| Kessler+19 (arXiv:1903.11756), sección de modelos SNII y referencias [8],[75],[79],[194] | Datos de entrenamiento de SNII-NMF: Anderson+14, Galbany+16, Sako+18 (SDSS), González-Gaitán+15 (SNLS). SNII-Templates heredados de SNPhotCC (Kessler+10) con extensión IR de Pierel+18. SNIIn-MOSFIT con rangos de Villar+17 |
| Zenodo 2612896 (PLAsTiCC models) | Archivos SIMSED.SNII-NMF, NON1ASED.SNII-Templates, SIMSED.SNIIn-MOSFIT; licencia CC BY 4.0 |
| API arXiv `id_list` y `ti:"Carnegie Supernova Project" AND ti:"Type II"` | CSP-I Anderson+24 (94 SNe II), Martinez+22 I/II, Davis+19 (NIR), de Jaeger+18 (colores, no registrado aparte) |
| Página de datos CSP | Espectros de Gutiérrez+17 (tarball de 8.7 MB, comprobado con HEAD), templates SNID, curvas bolométricas de Martinez+22, espectros y templates NIR de Davis+19, fotometría SE (IIb) |
| ReadMe de VizieR por FTP (J/A+A/692/A95, J/A+A/637/A73, J/A+A/609/A134, J/ApJ/959/142) | Confirmados archivos y conteos (p. ej. 10 IIb en CSP-I SE) |
| `ti:"probes of environment metallicity"`, `ti:"low luminosity host galaxies"`, `au:Taddia AND ti:metallicity`, búsqueda web "Type II host metallicity MUSE" | Anderson+16 (HII, local), Gutiérrez+18 (proxy de masa), Taddia+16 (iPTF), PISCO (Galbany+18), ASAS-SN+MUSE (Pessi+23) |
| Búsquedas web de "hydrogen-rich superluminous ZTF" | Kangas+22 (14 SLSN-II), Pessi+25 (107 SLSN-II) |
| Búsquedas web de "Type IIn sample ZTF" | Hiramatsu+24 (487 IIn), Nyholm+20 (42 IIn de PTF), Ransome & Villar+24 (no registrado) |
| Búsquedas web de "ZTF Type II sample" | Hinds+25 (639 SNe II de BTS, con tabla auxiliar), Silva-Farfán+24 (186 de ZTF+ATLAS), Sit+23 (CLU, subida larga) |
| `au:Moriya AND ti:grid` + Dryad | Grilla STELLA de 228 016 modelos, SED de 1 a 50 000 Å, 73.7 GB |
| GitHub API de PyCoCo_templates + PDF de V19 | 67 SED; las que tienen H son 23 II + 11 IIb + 7 IIn + 87A |
| Archivo CfA (SNarchive.html) | Tarballs de espectros y curvas de Hicken+17 |
| Zenodo `q=Dessart supernova`, `q="Type II" supernova models CMFGEN` | Ninguna grilla de Dessart; solo inlists de MESA y una charla de Gutiérrez (descartada) |

## Descartadas o no registradas

- **Valenti+16 (LCO)**: solo 12 SNe II; el aporte es menor que el de las demás muestras.
- **de Jaeger+18, colores de CSP-I**: se deriva de los mismos datos que Anderson+24.
- **Gutiérrez+17 II (arXiv:1709.02799)**: va dentro de la fila de los espectros de Gutiérrez+17.
- **Ransome & Villar+24 (MOSFiT de 142 IIn)**: son ajustes de modelos, no datos nuevos; queda pendiente.
- **Zenodo 3478044**: es la presentación de una charla, no datos.
- **Open Supernova Catalog**: no se revisó (ver pendientes).
- **arXiv:1709.02796 y 1803.07604**: los ID que tenía de memoria apuntaban a papers equivocados (manchas solares y cuandles). Se corrigieron por búsqueda a 1709.02487 y 1802.07254.

## Pendiente o dudoso

- **SNLS de González-Gaitán+15**: no hay tabla pública de curvas. Hay que pedirla a los autores (Galbany o González-Gaitán), que además construyeron SNII-NMF y podrían tener la matriz de entrenamiento original.
- **URL de datos de SDSS-II** (`sdssdp62.fnal.gov`): no resolvió por DNS. Buscar un espejo, por ejemplo en SNANA (`SDSS_allCandidates+BOSS`) o en VizieR.
- **Berkeley SNDB**: no respondió. WISeREP devolvió 403, así que no se pudo confirmar si exige cuenta o clave de API.
- **Kessler+19**: no da el número de SNe ni los rangos de fase y λ del entrenamiento de SNII-NMF. Habría que revisar el README de la tarball o preguntar a los autores.
- **Distancias de Anderson+14 y de Jaeger+19**: son mixtas (flujo de Hubble más distancias independientes de NED). En el CSV quedaron como `hubble_flow` con una nota.
- **Metalicidad por objeto**: Anderson+16 (local, CSP/CATS) cruzado con Gutiérrez+17 y Anderson+24 daría la muestra con fotometría, espectros y metalicidad local. Falta confirmar cuántas SNe se solapan.
- **Subclases de PISCO y Pessi+23**: no se desglosaron por tipo.
- **Ítems no revisados**: redshifts de Davis+19 y Sit+23, y si los modelos de Morozova+18 y Dessart+13 son públicos.
- **Duplicados con otros agentes**: V19 (fila restringida a la parte con H), CSP-I SE (incluye Ib/Ic) y PISCO/MUSE (todas las clases).

## Nota de la unión (2026-10-27)
Se quitaron de `hrich.csv` las filas `wiserep` y `ztf_bts`, que también estaban en `stripped.csv` cubriendo todas las subclases y con `verified=yes`.
