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
| `sample.csv` | 122 SNe de Gutiérrez+17: z heliocéntrico, E(B−V)_MW (Schlafly+11), época de explosión con su error y método, 12+log(O/H) local (M13 N2, Anderson+16), s2 y OPTd de Anderson+14 (66 SNe, vía la tabla A.1 de Anderson+16), puntos y noches con espectro |
| `photometry.csv` | 11 689 puntos de Anderson+24 (uBgVri + YJH): magnitud natural, AB, corregida por la Vía Láctea, f_ν en µJy, fase en reposo desde la explosión y λ_eff en reposo |
| `spectra.csv` | Índice de los 989 FITS de Gutiérrez+17: fecha, rango de λ, brazo, fase en reposo |

Qué se hace:
- **AB:** m_AB = m_natural + offset del filtro, con λ_eff y offsets de la tabla de CSP
  (Krisciunas+17), por instrumento y fecha (`csp_system.py`). La V de CSP-I cambió de filtro
  dos veces en enero de 2006 y la J de la Swope en enero de 2009.
- **Vía Láctea:** CCM89 + O'Donnell94 con R_V = 3.1 (`mw_extinction.py`; no se llama `extinction.py` para no chocar con el paquete `extinction` que instala sncosmo), evaluada en la λ_eff del
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

## Paso 2: fin del plateau de las SNII (`fit_plateau_end.py`)

```
python research/templates_nmf/assemble/fit_plateau_end.py
```

Mide t_PT, el centro de la caída del plateau a la cola, ajustando a la curva en V (fase ≥ 25
días) el modelo de Olivares+10 sin el máximo temprano. Escribe `out/csp_snii/plateau_end.csv`.
Sirve para alinear las curvas por el fin del plateau en el NMF (ver `nmf/README.md`) sin
depender solo de los OPTd publicados.

- **Pasada 1:** todos los parámetros libres. Se exigen 3 puntos en el plateau y 2 después de
  t_PT. El error de t_PT es al menos la mitad del hueco entre el último punto del plateau y el
  primero después, porque con la cola mal muestreada la covarianza lo subestima. Si el error
  supera los 10 días, el estado es `mal_medido`.
- **Pasada 2,** para las curvas que terminan dentro de la caída sin llegar a la cola: a0 y w0
  quedan fijos en la mediana de los ajustes buenos de la pasada 1 (1.82 mag y 4.7 días); el
  error suma la diferencia al usar los percentiles 16 y 84.

### Resultado (2026-10-30)
- De 70 SNe con V: **23 con t_PT** (15 libres y 8 con a0 y w0 fijos), 34 cuya curva termina
  antes de la caída (`sin_caida`: solo vale t_PT > última fase), 10 con pocos puntos, 2 mal
  medidas y 1 falla.
- **Concuerda con OPTd de Anderson+14 con un corrimiento casi constante:** t_PT − OPTd tiene
  mediana 12 días y MAD 5 días (21 SNe). Es lo esperado, porque OPTd marca el inicio de la
  caída y t_PT su centro; la dispersión equivale a un bin del NMF. Las diferencias grandes
  (2004fx +33, 2004er +26, 2005dz +25, 2008ag +23 días) pueden deberse a otra definición del
  fin del plateau o a la época de explosión (Anderson+14 usó fotometría propia más completa).
- Solo agrega **2 SNe sin OPTd** (2007aa y 2008K). La fotometría pública de CSP-I no alcanza
  para medir el fin del plateau en la mayoría de las curvas: la mitad termina antes de la caída.
  Para usar toda la muestra, el fin del plateau tendría que entrar al modelo como un
  corrimiento libre por objeto (las curvas `sin_caida` aportan entonces una cota inferior).

## Paso 3: SN despojadas de CSP-I (`build_csp_sesn.py`)

```
python research/templates_nmf/assemble/build_csp_sesn.py
```

Toma Stritzinger+18a (J/A+A/609/A134) y la extinción del host de Stritzinger+18b, con el mismo
sistema AB y la misma corrección por la Vía Láctea que las SNII. Escribe en `out/csp_sesn/`
`sample.csv` y `photometry.csv`, con las mismas columnas que en SNII salvo la fase.

Diferencias con las SNII:
- **Fase desde T(B)max** (en reposo), porque el paper no da épocas de explosión. En 17 SNe
  T(B)max no está medido, sino estimado con la relación de la fig. 3 de Taddia+18
  (`tbmax_from_relation`).
- **E(B−V)_MW** no está en el paper: se consulta el servicio DUST de IRSA (Schlafly &
  Finkbeiner 2011, igual que Gutiérrez+17 para las SNII) en las coordenadas de table1. Queda
  en caché en `out/csp_sesn/ebv_mw_irsa.csv`.
- **E(B−V)_host** de Stritzinger+18b (21 SNe) queda en `sample.csv` sin aplicar, igual que en
  SNII (pendiente: pregunta al profesor sobre la extinción del host).
- No hay espectros ópticos públicos de CSP-I para estas SNe en el catálogo: la muestra es
  solo fotométrica.

### Resultado (2026-10-30)
- 34 SNe: 11 Ib, 11 Ic, 10 IIb y 2 Ic-BL, igual que el paper.
- 4029 puntos (2986 ópticos y 1043 NIR), igual que el inventario del catálogo. 31 son de
  du Pont + Tek5, sin calibración AB (NaN, como en las SNII).
- E(B−V)_MW: mediana 0.039, máximo 0.17; 33 de 34 bajo 0.1.
- Cobertura antes del máximo en óptico: **12 SNe desde 5 días antes**, igual que el abstract.
  Con algún punto antes de T(B)max salen 22 (el abstract dice 20); 5 de ellas tienen T(B)max
  estimado, así que la cuenta depende de cómo se trate ese caso. No reproduje el 20 exacto.
- Mediana de noches ópticas por SN: 12 (Ic) a 18 (Ib). Con 34 SNe repartidas en cuatro
  subtipos, un NMF por subtipo tendría 10 objetos o menos: conviene un NMF conjunto de las
  despojadas, o sumar CfA (Bianco+14, otro sistema fotométrico) antes de separar.

## Paso 3b: SN despojadas de CfA (`build_cfa_sesn.py`)

```
python research/templates_nmf/assemble/build_cfa_sesn.py
```

Toma Bianco+14 (J/ApJS/213/19) y escribe en `out/cfa_sesn/` `sample.csv` y `photometry.csv`
con las mismas columnas que CSP-I (salvo `mag_nat` y `filter`, con `mag_std` y `code` en su
lugar). Si existe `out/csp_sesn/`, compara además las SNe comunes.

- **Sistema:** se usa la fotometría estándar (table6), porque CfA no publica curvas de
  transmisión por cámara. UBVRI (Bessell) y JHKs (2MASS) pasan a AB con m_AB − m_Vega y
  λ_eff de la tabla 1 de Blanton & Roweis (2007); u'r'i' (SDSS) ya están en AB.
- **T(B)max:** VizieR no trae el máximo; sale de las tablas 4–6 de la fuente LaTeX
  (arXiv:1405.1428, se baja sola). Si B no está medido se usa V, R, I o U corrido por la
  mediana del desfase respecto de V (tabla 7 del paper), con su dispersión sumada al error
  (`tbmax_band` dice de dónde sale). Los picos NIR no se usan (3–5 días de dispersión).
- **Sanidad:** se rechaza un máximo más de 25 días después del descubrimiento
  (`tbmax_rejected_mjd`). Cae 2004gt: Bianco+14 da B en MJD 53388.5 y CSP-I 53359.6,
  probablemente una errata de 30 días en el paper. Las fechas de descubrimiento de 2009jf y
  2007aw en VizieR son de otra SN (el año no calza) y quedan en NaN.
- **E(B−V)_MW** viene en table2 (Schlafly & Finkbeiner 2011, el mismo mapa que IRSA).

### Resultado (2026-10-30)
- 64 SNe (23 Ib, 19 Ic, 9 IIb, 9 Ic-BL, 2 Ibn, 1 Ca-rich, 1 Ic/Ic-BL) y 6462 puntos (4543
  ópticos, 1919 NIR), igual que el ReadMe de VizieR.
- T(B)max en 38 SNe: 17 medido en B, 12 desde V, 5 desde I y 4 desde R. 25 sin máximo.
- 19 SNe están también en CSP-I. En las 14 con ambos máximos, CfA − CSP da mediana +0.1 d y
  MAD 2.5 d; difieren más de 5 días 2006bf (+6) y 2007rz (+18), las dos con el T(B)max de
  CSP-I estimado por relación.
- **Validación de la conversión a AB:** en las SNe comunes, misma noche (±0.6 d), CfA − CSP en
  AB corregido por MW da +0.05 (B), +0.03 (V), +0.03 (r') y +0.05 (i') mag, con MAD ≤ 0.05.
  Es el orden esperado entre fotometría estándar y natural sin correcciones S
  (`out/cfa_sesn/compare_csp.csv`).
