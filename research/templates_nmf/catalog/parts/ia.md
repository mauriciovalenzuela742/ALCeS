# Fuentes de la familia SN Ia (agente template-scout)

CSV: `parts/ia.csv`. Tiene 31 filas, 17 con `verified=yes`, y pasa `validate_catalog.py`.

## Búsquedas y verificaciones hechas
- **API de arXiv** (`export.arxiv.org/api/query?id_list=...`): sirvió para comprobar títulos de unos 28 IDs que salían de conocimiento previo. Hubo dos IDs mal asociados que se descartaron: 1006.4613, que es un paper de tasas de LOSS y no las curvas de Ganeshalingam, y 1710.06404, que es filosofía de la física y no Shen+18. Después la API devolvió 429 y seguí abriendo `arxiv.org/abs/<id>` uno por uno.
- **Página de fuentes de sncosmo**: confirma hsiao, nugent-sn1a/sn91t/sn91bg, salt2, salt3, salt3-nir, snemo2/7/15 y sugar. No incluye BayeSN ni modelos Iax.
- **Páginas de acceso abiertas**:
  - templates de Nugent (c3.lbl.gov)
  - página de datos de CSP (DR2/DR3 de fotometría, DR1 de espectros, espectros NIR y template de Lu+23, 03fg-like)
  - archivo CfA
  - ztfcosmo.in2p3.fr y su repo en GitHub
  - GitHub de bayesn, Foundation_DR1 y PantheonPlusSH0ES
  - documentación de saltshaker
  - página de SNEMO y página de releases de SNfactory
  - ReadMe de VizieR J/ApJ/770/107
  - Zenodo de PLAsTiCC (2612896)
  - hesma.h-its.org
- **Búsquedas web**:
  - "Ganeshalingam 2010 LOSS BVRI 165": el ID de arXiv no apareció. Uso el DOI, confirmado vía Crossref.
  - "Shen Kasen sub-Chandrasekhar detonations revisited": arXiv:1706.01898.
  - "ZTF SN Ia DR2 spectroscopic": dio Burgaz+24 (2407.06828) y el overview (2409.04346).
  - "HESMA Kromer 2017": arXiv:1706.09879.
  - "SNfactory companion datasets": arXiv:2005.03462.
  - "Childress 2013 SNfactory hosts": 1304.4719 y 1304.4720.
  - "Lu 2023 CSP-II NIR template": 2211.05998.
  - "Sharma 2023 ZTF Ia-CSM": 2301.04637.
  - "Ashall 2021 2003fg-like": 2106.12140.
  - También salió el paper de subluminosas de ZTF DR2 (2512.21256).

## Descartadas o no incluidas
- WISeREP, el Open Supernova Catalog y TNS: son archivos genéricos que probablemente cubren otras partes. Se evitó duplicar `source_id`.
- SN 2011fe de SNfactory (Pereira+13): es un solo objeto, útil como validación pero no como muestra.
- DES-SN5YR, PS1-MDS, SNLS y SDSS-II: son muestras de alto z con espectros solo de clasificación. Su prioridad es baja para NMF a bajo z, y quedan cubiertas indirectamente por Pantheon+ y SALT3.
- Swift UVOT (SOUSA): queda pendiente y sería útil para el UV.

## Limitaciones y pendientes
- Faltan los rangos de fase y de λ de Hsiao, SALT2 y SUGAR, porque no aparecían en las páginas abiertas. Se pueden leer de los archivos de sncosmo.
- **ZTF DR2**:
  - La página /papers dice 3268 SNe y el abstract 3628. Usé 3628.
  - No hay metalicidad del host (solo masa y color).
  - No se pudo abrir /download/data porque la página pesa más de 10 MB.
- **BSNIP**: la SNDB de Berkeley rechazó la conexión. **LOSS (Ganeshalingam+10)**: VizieR la bloqueó con Anubis. **CSP-II**: no se encontró un release de fotometría.
- **SNfactory companion**: falta confirmar el archivo exacto de descarga y el rango λ de SNIFS.
- **HESMA**: requiere registro. No se confirmaron el número de modelos ni los rangos.
- **Goldstein & Kasen 2018 y Shen+18**: no se sabe dónde están los espectros y las curvas de luz sintéticas.
- **Templates de 91T e Iax**: no se encontraron templates observacionales recientes más allá de Nugent (91T, basado en un objeto) y PLAsTiCC Iax (basado en SN 2005hk). Faltaría buscar compilaciones de Iax (Jha 2017, Magee et al.) y muestras de 91T (Phillips+22).
- **Validador**: el regex de bibcode no acepta bibcodes con puntos en la página (por ejemplo `2010ApJS..190..418G`). Usé el DOI.
