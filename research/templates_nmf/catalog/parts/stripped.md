# Parte `stripped`: SN despojadas e interactuantes sin H, SLSN-I, PISN y archivos generales

Inventario hecho el 2026-10-27. Contiene 37 fuentes: 19 con `verified=yes`, 18 con `partial` y ninguna con `no`.
Lo valida `validate_catalog.py` con OK.

## Búsquedas hechas

| Búsqueda | Qué salió |
|---|---|
| API de arXiv `id_list=` con unos 25 IDs candidatos | 24 títulos correctos; `1709.09630` era otro paper (r-process), así que lo reemplacé por `1707.07616` |
| arXiv `ti:"Carnegie Supernova Project" AND ti:stripped` | CSP-I: fotometría (1707.07616), análisis (1707.07614), host (1707.07615), espectros (2302.11303/11304); CSP-II NIR (2110.12083) |
| arXiv `au:Williamson AND au:Modjaz` | Williamson+19 PCA (1903.06815) y Pellegrino+22 Icn (2205.07894) |
| arXiv `ti:"Type Icn"` | Solo objetos individuales (2021ckj, 2023xgo, 2024abvb) además de Pellegrino+22 |
| arXiv `ti:"Palomar Transient Factory" AND ti:host AND ti:core-collapse` | Schulze+21 (2008.05988) |
| arXiv `au:Kozyreva AND ti:pair` | Modelos PISN STELLA (1610.01086 y otros) |
| Web: "Gomez Type I superluminous supernova catalog github" | gmzsebastian/SLSNe, slsne.readthedocs.io y Aamer+25 (2503.21874) |
| Web: "Modjaz 2014 Optical spectra of 73 stripped-envelope" | 1405.1910 y CDS J/AJ/147/99 |
| Web: "Dessart 2016 radiative transfer stripped-envelope" y "Dessart CMFGEN zenodo" | 1602.06280, 2008.07601, 2306.12092 y Zenodo 8185503 |
| Web: "Srinivasaragavan ZTF broad-lined Ic" | 2408.14586 |
| Web: "ELASTiCC PISN-STELLA Kozyreva" | Archivo CCSN de Garching y OpenUniverse2024 (2501.05632), que explica el origen de PISN-STELLA |
| Páginas de datos abiertas | GitHub nyusngroup (SESNtemple, SESNspectraLib, SESNspectraPCA), cosmo.nyu.edu/SNYU, CfA SNarchive, CDS ReadMe (J/AJ/147/99, J/ApJS/213/19, J/A+A/609/A134), csp.obs.carnegiescience.edu/data, Zenodo 2612896 y 8185503, wiserep.org, sne.space, astrocatalogs, ZTF BTS, ATLAS forcedphot, SOUSA, pessto.org |

La API de arXiv empezó a devolver 429 a mitad de la sesión. Desde ese momento verifiqué los IDs abriendo `arxiv.org/abs/<id>`.

## Fuentes descartadas o no incluidas

- **TNS** (wis-tns.org): es imprescindible como fuente de tipos y redshift, pero no tiene un paper de referencia en un formato que acepte el validador, y la API requiere bot o key. Queda fuera de la tabla. Se usa a través de BTS y WISeREP.
- **SESNspectraLib**: es código (suavizado FFT y ajuste de Ic-BL), no datos. Solo trae un `IcTemplates/` sin describir. Quedó cubierto por SESNtemple.
- **MOSFiT SLSN (Nicholl+17, 1706.00825)**: solo verifiqué el título. El modelo que usa ALCeS ya está en la fila `plasticc_models_sesn_slsn_pisn`.
- **Modjaz+16 (1509.07124)**: verifiqué el título y lo uní a la fila de espectros medios de SESNtemple.
- **Lyman+16, Prentice+16/19 y Fremling+18**: no los revisé por falta de tiempo y porque sus datos están en WISeREP/OSC.
- **CSP-I SE, espectros en CDS**: `J/A+A/675/A82` devuelve 404.

## Pendiente

1. **Espectros de CSP-I SESN (Stritzinger+23)**: falta encontrar dónde se descargan. Probablemente WISeREP o el material suplementario de A&A.
2. **Metalicidad del host**: hay que confirmar si Modjaz+20 (PTF Ic/Ic-BL) y Perley+16 (SLSN) son globales o locales. En la tabla dejé `unknown` y `host_global` (este último supuesto), respectivamente. Ningún conjunto de datos de SN que revisé publica metalicidad junto con la curva de luz. Habrá que cruzar por objeto.
3. **Redshift, distancia y extinción**: en casi todos los conjuntos observados quedaron en `unknown` porque los abstracts no lo dicen. Hay que revisarlo en las tablas de cada paper (CSP y CfA casi seguro tienen z espectroscópico y E(B-V) del host).
4. **sne.space**: hoy sirve unos 110k transientes con API REST+MCP. Parece un servicio nuevo sobre el dominio del OSC original. Hay que confirmar quién lo mantiene antes de usarlo.
5. **Aamer+25 (espectros de SLSN)**: falta confirmar si los archivos están en el paquete `slsne` o en otro lugar.
6. **Pierel+18**: falta confirmar el número de templates y el rango de λ en la documentación (readthedocs no lo mostraba).
7. **Rango de fase de V19**: no está en el README. Hay que mirarlo en los archivos SNANA de ALCeS.
8. **VC25_SNIbc**: el paper (2409.10701) solo cubre Ia y II. Hay que pedir al grupo la descripción de la versión Ibc.
9. **Ibn, Icn y Ca-rich**: hay muy pocos objetos (22, 4 y unos 18) y los datos están dispersos en WISeREP. Para NMF probablemente no alcanza.
