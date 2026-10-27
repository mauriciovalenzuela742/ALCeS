# Esquema del catálogo de fuentes de templates (agente 1)

Primera etapa: inventario **a nivel de fuente** (un template, un modelo o un conjunto de datos
observados), solo supernovas. El inventario por objeto (`objects.csv`) viene después, para las
clases que pasen el informe de viabilidad.

Cada fila de `sources.csv` es una fuente. Los campos con `;` admiten varios valores.

| Columna | Tipo | Valores / formato | Qué es |
|---|---|---|---|
| `source_id` | texto | `snake_case`, único | Identificador corto (`csp_ii_photometry`) |
| `name` | texto | | Nombre legible |
| `kind` | enum | `template`, `model_grid`, `observed_dataset`, `archive` | `template` = series espectrales ya armadas (Nugent, V19); `model_grid` = modelos teóricos; `observed_dataset` = datos de un survey o paper; `archive` = repositorio que agrega muchos (WISeREP) |
| `subclasses` | lista | ver `SUBCLASSES` en `validate_catalog.py` | Subclases de SN que contiene |
| `data_type` | enum | `spectra`, `photometry`, `both`, `sed` | `sed` = series espectrales en tiempo listas para SNANA o sncosmo |
| `n_objects` | entero o vacío | | Número de SNe (vacío si no se sabe) |
| `bands` | texto | ej. `uBgVri;YJH` | Filtros de la fotometría |
| `phase_range_d` | texto | ej. `-15:+120` | Cobertura de fase respecto del pico, en días |
| `wave_range_A` | texto | ej. `3300:9500` | Cobertura en λ, Å |
| `redshift` | enum | `spec`, `photo`, `mixed`, `none`, `unknown` | Calidad del redshift |
| `distance` | enum | `independent`, `hubble_flow`, `host`, `none`, `unknown` | Si hay distancias más allá del redshift |
| `metallicity` | enum | `host_global`, `host_local`, `model`, `none`, `unknown` | Si hay metalicidad y de qué tipo |
| `extinction` | enum | `mw_only`, `mw_and_host`, `none`, `unknown` | Correcciones de extinción incluidas o publicadas |
| `access_url` | URL | `https://...` | Dónde se obtienen los datos |
| `access_method` | enum | `download`, `api`, `vizier`, `paper_tables`, `on_request`, `unknown` | Cómo |
| `license` | texto | | Licencia o condiciones (vacío si no se encontró) |
| `reference` | texto | `arXiv:XXXX.XXXXX`, bibcode o DOI | Paper que describe la fuente |
| `in_alces` | enum | `yes`, `no` | Si ALCeS ya la usa |
| `verified` | enum | `yes`, `partial`, `no` | `yes` = se abrió la página del paper y la del acceso, y los números salen de ahí |
| `found_by` | texto | | Búsqueda o cadena que llevó a la fuente |
| `notes` | texto | | Advertencias, limitaciones |

**Reglas:** nada se completa sin fuente. Si un dato no aparece, la celda queda vacía o en
`unknown`. Los números (`n_objects`, rangos) se copian del paper o de la página, no se estiman.
