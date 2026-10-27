# Esquema del inventario por objeto (`objects/parts/*.csv`)

Segunda etapa del agente 1. Cada fila es **una SN en una fuente** (la misma SN aparece una vez
por cada fuente que la tiene). `viability.py` une las filas por nombre y cuenta, por subclase,
cuántos objetos cumplen los requisitos de cada nivel de NMF.

**Regla de origen:** cada `objects/parts/<source_id>.csv` lo genera un script
`objects/scripts/<source_id>.py` que descarga la tabla pública y la convierte. No se escriben
filas a mano. Las tablas descargadas van a `objects/raw/` (ignorado por git).

| Columna | Obligatoria | Formato | Qué es |
|---|---|---|---|
| `sn_name` | sí | texto | Nombre como lo da la fuente (`SN 2004et`, `ZTF19abcdefg`, `2019abc`) |
| `alt_names` | no | lista `;` | Otros nombres que da la fuente (IAU, ZTF, PTF) |
| `source_id` | sí | igual a `sources.csv` | Fuente de la fila |
| `subclass` | sí | ver `SUBCLASSES` en `validate_catalog.py` | Tipo según la fuente |
| `ra`, `dec` | no | grados decimales | Para cruzar cuando los nombres no coinciden |
| `z` | no | número | Redshift |
| `z_type` | no | `spec`, `host_spec`, `photo`, `unknown` | Origen del redshift |
| `dist_mod` | no | mag | Módulo de distancia si la fuente da uno |
| `dist_method` | no | `hubble_flow`, `independent`, `unknown` | Cómo se obtuvo |
| `ebv_mw` | no | mag | E(B−V) de la Vía Láctea |
| `ebv_host` | no | mag | E(B−V) del host, si la fuente lo estima |
| `bands` | no | lista `;` | Filtros con fotometría de esta SN en esta fuente |
| `n_phot` | no | entero | Número de puntos fotométricos (todas las bandas) |
| `n_spec` | no | entero | Número de espectros |
| `phase_min`, `phase_max` | no | días | Cobertura respecto de `phase_ref` |
| `phase_ref` | no | `peak`, `explosion`, `discovery`, `unknown` | Referencia de la fase |
| `oh12` | no | número | Metalicidad 12+log(O/H) |
| `oh12_type` | no | `host_global`, `host_local`, `unknown` | Tipo de metalicidad |
| `oh12_calib` | no | texto | Calibración (`N2_M13`, `O3N2_PP04`...) |

Las columnas vacías significan "esta fuente no lo da", no "no existe".
