# Agente 2: armado de datos para templates

Librería determinista (no es un agente que decide): toma las descargas de la etapa 2 del
catálogo y las deja homogéneas para el NMF. Las salidas van a `out/` (ignorado por git) y se
regeneran con los scripts.

## Paso 1: SNII de CSP-I (`build_csp_snii.py`)

```
python research/templates_nmf/assemble/build_csp_snii.py
```

Necesita `catalog/objects/raw/` con Anderson+24, Gutiérrez+17 y Anderson+16 (si falta, correr
sus scripts en `catalog/objects/scripts/`). Escribe en `out/csp_snii/`:

| Archivo | Contenido |
|---|---|
| `sample.csv` | 122 SNe de Gutiérrez+17: z heliocéntrico, E(B−V)_MW (Schlafly+11), época de explosión con su error y método, 12+log(O/H) local (M13 N2, Anderson+16), puntos y noches con espectro |
| `photometry.csv` | 11 689 puntos de Anderson+24 (uBgVri + YJH): magnitud natural, AB, corregida por la Vía Láctea, f_ν en µJy, fase en reposo desde la explosión y λ_eff en reposo |
| `spectra.csv` | Índice de los 989 FITS de Gutiérrez+17: fecha, rango de λ, brazo, fase en reposo |

Qué se hace:
- **AB:** m_AB = m_natural + offset del filtro, con λ_eff y offsets de la tabla de CSP
  (Krisciunas+17), por instrumento y fecha (`csp_system.py`). La V de CSP-I cambió de filtro
  dos veces en enero de 2006 y la J de la Swope en enero de 2009.
- **Vía Láctea:** CCM89 + O'Donnell94 con R_V = 3.1 (`extinction.py`), evaluada en la λ_eff del
  filtro. Es una aproximación de banda ancha (no integra el espectro por el filtro); el error es
  pequeño para E(B−V) < 0.1, que cubre el 88 % de la muestra.
- **Fase:** (MJD − t_explosión) / (1 + z_helio).

Qué **no** se hace todavía (depende de las respuestas del profesor):
- distancia y luminosidad absoluta (flujo de Hubble o independiente; z_CMB);
- extinción del host;
- correcciones K, mangling de espectros a la fotometría y rejilla común fase × λ.

### Resultado (2026-10-28)
- 122 SNe en la muestra; 70 con fotometría de Anderson+24, 109 con metalicidad y **54 con
  fotometría, metalicidad y espectros en al menos 3 noches**.
- Fotometría: 11 689 puntos (= 9817 ópticos + 1872 NIR del abstract). 2618 son de 24 SNe que
  no están en Gutiérrez+17 (20 de CSP-II y SN 2005gk, 2005hd, 2005kh, 2009A): quedan con
  `in_sample=False` porque no tienen z ni época de explosión en esta muestra.
- 51 puntos de `duPont+TEK5` no tienen offset AB en la tabla de CSP: quedan con `mag_ab` vacío.
- Espectros: 989 FITS (los brazos azul y rojo van por separado). SN00cb no está en la tabla del
  paper. 5 FITS no traen solución de λ en la cabecera (SN 2008if, 4 de SN 1993K): quedan con
  `wave_min` vacío.
- **Fechas:** de 887 filas de `table_spec` del paper, 869 tienen un FITS a menos de 1 día. Las
  diferencias parecen erratas de la tabla: SN 2003ip trae JD con un dígito de menos y SN 210
  difiere en unos 30 días. Se usa la fecha del FITS (JD, MJD-OBS, DATE-OBS ISO o el nombre del
  archivo, en ese orden; ver `fits_mjd`). Hay espectros de SN 2008bk a 689 y 963 días que no
  están en la tabla.

## Tests
```
python -m pytest research/templates_nmf/assemble/tests -q
```
No necesitan descargas. No están en `testpaths` del repo, así que el CI no los corre.
