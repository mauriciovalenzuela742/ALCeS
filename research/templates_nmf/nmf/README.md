# NMF con pesos y datos faltantes

- `wnmf.py`: V ≈ W H con W, H ≥ 0, minimizando Σ w (V − WH)² con w = 1/σ² y w = 0 en celdas sin
  dato (objetivo de Blanton & Roweis 2007 y Zhu 2016). Se resuelve con mínimos cuadrados
  alternados y NNLS exacto: el objetivo nunca sube y V puede tener valores negativos (flujo con
  ruido), que las reglas multiplicativas no admiten. Incluye `transform` (coeficientes de
  objetos nuevos con H fijo), `cv_score` (validación cruzada ocultando celdas) y una
  penalización ridge opcional `alpha` sobre W y H.
- `explore_csp_snii_phot.py`: NMF fotométrico **exploratorio** de las SNII de CSP-I (entrada:
  `assemble/out/csp_snii/photometry.csv`). Salidas en `out/` (ignorado por git).
- `explore_csp_sesn_phot.py`: lo mismo para las despojadas de CSP-I (entrada:
  `assemble/out/csp_sesn/photometry.csv`), con fase desde T(B)max.

```
python research/templates_nmf/nmf/explore_csp_snii_phot.py [--kmax 8] [--alphas 0.01]
python -m pytest research/templates_nmf/nmf/tests -q
```

## Exploración fotométrica de SNII (2026-10-30)

Matriz: 64 SNe × 150 celdas (bandas uBgVri × bins de 4 días entre 0 y 144 días desde la
explosión, en reposo), con 44 % de las celdas observadas. Se descartan las celdas con menos de
10 SNe. Cada SN se divide por su flujo medio en V entre 20 y 60 días, así que el NMF ve
**forma y color, no luminosidad** (la luminosidad necesita distancias; pregunta 4 al profesor).

**Sin regularizar, la validación cruzada es inestable.** Algunos pliegues dan errores enormes:
un objeto con huecos toma un coeficiente gigante en una componente casi nula donde tiene datos
(2008bm: predice 20 donde el dato es 0.4). La mediana mejora con k, pero la media no. Con ridge
`alpha = a · mediana(w)` y a = 0.01 o 0.1, la validación queda estable:

| k | χ² medio por celda oculta (a = 0.01) | mediana |
|---|---|---|
| 1 | 128 ± 14 | 31 |
| 2 | 67 ± 11 | 13 |
| 3 | 43 ± 10 | 7.2 |
| 4 | 38 ± 26 | 4.4 |
| 5 | 21 ± 6 | 3.1 |
| 6 | 37 ± 23 | 2.5 |
| 7 | 115 ± 172 | 2.1 |
| 8 | 19 ± 7 | 1.9 |

Se elige **k = 5**: es el k más chico cuya media no la mejora un k mayor por más que la
dispersión entre pliegues. Con k = 6 y 7 vuelven las extrapolaciones catastróficas, y k = 8
empata con k = 5. Con 64 SNe, más componentes no están respaldadas por los datos.

Los χ² son grandes porque los errores son solo fotométricos (con un piso de 0.03 mag). La
dispersión intrínseca entre SNe no está en σ.

**Componentes (k = 5):** fase temprana caliente y azul, plateau, caída tipo IIL, fin del
plateau y cola. Varias componentes representan **distintas duraciones del plateau**: el NMF
gasta componentes en un corrimiento temporal. Si se alinean las curvas por el fin del plateau
(o se modela la duración aparte), probablemente bastan menos componentes. Esto conviene
discutirlo con el profesor junto con la pregunta 1 (NMF espectral o fotométrico).

## Alineación por fin del plateau (2026-10-30)

`--align ptend` mide el tiempo como τ = fase − OPTd, donde OPTd es la duración de la fase
ópticamente gruesa (explosión → fin del plateau en V) de Anderson+14, tomada de la tabla A.1 de
Anderson+16 (`sample.csv`, columna `optd_a14_d`). Hay OPTd para 66 SNe (igual que el paper), y
37 de ellas quedan en la matriz. Para comparar en igualdad de condiciones, ambas alineaciones
se corren solo con esas SNe (`--require-optd`):

```
python explore_csp_snii_phot.py --kmax 6 --alphas 0.01 0.1 --require-optd --align expl
python explore_csp_snii_phot.py --kmax 6 --alphas 0.01 0.1 --require-optd --align ptend
```

χ² medio por celda oculta (± dispersión entre pliegues), mejor de a = 0.01 y 0.1:

| k | desde la explosión | desde el fin del plateau |
|---|---|---|
| 1 | 155 ± 29 | 117 ± 15 |
| 2 | 407 ± 615 | 53 ± 5 |
| 3 | 48 ± 7 | 23 ± 2 |
| 4 | 31 ± 7 | 17 ± 2 |
| 5 | 28 ± 10 | 22 ± 7 |
| 6 | 35 ± 11 | 17 ± 3 |

**Alinear por el fin del plateau baja el error a la mitad para cada k**, y con k = 3 ya supera
a la mejor alineación por explosión. Es decir, ahorra unas dos componentes, que antes se
gastaban en representar el corrimiento temporal. La CV también queda más estable (pliegues
con menos dispersión). Con alineación por plateau, k = 3–4 basta; la regla automática elige
k = 6 con a = 0.1, pero k = 4 con a = 0.01 empata (17 ± 2) y con 37 SNe conviene el k chico.

Advertencias:
- OPTd se mide desde la época de explosión de Anderson+14; para las SNe en que Gutiérrez+17
  cambió esa época (`t_expl_changed_vs_a14`), τ queda corrido por la diferencia. Tampoco se
  pasa OPTd a reposo (z < 0.06: < 5 días, un bin).
- La caída en las componentes aparece en τ ≈ +10 a +20 días, no en 0: OPTd marca el fin del
  plateau, no el medio de la caída.
- Solo 66 de 122 SNe tienen OPTd. Para usar esta alineación con toda la muestra (o con SNe
  nuevas) habría que medir el fin del plateau de cada curva, por ejemplo con el ajuste de
  Olivares+10, o tratarlo como parámetro libre del modelo (un corrimiento por objeto).

## Exploración fotométrica de SN despojadas (2026-10-30)

```
python explore_csp_sesn_phot.py                       # las 33 SNe con datos suficientes
python explore_csp_sesn_phot.py --exclude 2005bf      # sin la Ib de doble máximo
```

Matriz: uBgVri × bins de 4 días entre −20 y +80 días desde T(B)max (en reposo); quedan las
celdas entre −8 y +56 días, que tienen al menos 8 SNe. Cada SN se normaliza por su flujo en V
entre −5 y +15 días. Hay 33 SNe (11 Ib, 10 IIb, 10 Ic, 2 Ic-BL) y la cobertura es del 57 %. El
NMF es conjunto porque por subtipo hay 10 SNe o menos.

- **Con todas, la CV es inestable** incluso con ridge (a = 0.1: k = 2 da 197 ± 247). Una
  componente queda dedicada casi solo a **SN 2005bf**, la Ib peculiar de doble máximo (70 % de
  su peso).
- **Sin 2005bf**, la CV es estable y elige **k = 3** (a = 0.1):

| k | χ² medio por celda oculta | mediana |
|---|---|---|
| 1 | 40.9 ± 8.0 | 13.4 |
| 2 | 21.4 ± 1.8 | 8.6 |
| 3 | 14.5 ± 1.5 | 5.5 |
| 4 | 14.1 ± 2.1 | 5.4 |
| 5 | 13.4 ± 1.4 | 4.3 |

- **Componentes:** un pico rojo con caída rápida (la curva típica), un pico temprano azul y
  breve, y una curva ancha de declinación lenta. La mezcla de la primera y la tercera codifica
  el ancho de la curva (como el Δm15 de las Ia): otra vez el NMF gasta componentes en una
  escala temporal, como con el plateau de las SNII.
- **Las componentes no separan los subtipos.** La fracción de cada componente por SN no
  difiere entre IIb, Ib e Ic (Kruskal-Wallis, p = 0.21 a 0.89). Es lo esperado: el subtipo se
  define por líneas espectrales (H, He), no por la forma de la curva de luz. Templates por
  subtipo necesitarían espectros o tomar el subtipo como etiqueta externa; con fotometría
  sola, un único NMF de despojadas tiene la misma información.
