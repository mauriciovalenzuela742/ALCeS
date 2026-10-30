# NMF con pesos y datos faltantes

- `wnmf.py`: V ≈ W H con W, H ≥ 0, minimizando Σ w (V − WH)² con w = 1/σ² y w = 0 en celdas sin
  dato (objetivo de Blanton & Roweis 2007 y Zhu 2016). Se resuelve con mínimos cuadrados
  alternados y NNLS exacto: el objetivo nunca sube y V puede tener valores negativos (flujo con
  ruido), que las reglas multiplicativas no admiten. Incluye `transform` (coeficientes de
  objetos nuevos con H fijo), `cv_score` (validación cruzada ocultando celdas) y una
  penalización ridge opcional `alpha` sobre W y H.
- `explore_csp_snii_phot.py`: NMF fotométrico **exploratorio** de las SNII de CSP-I (entrada:
  `assemble/out/csp_snii/photometry.csv`). Salidas en `out/` (ignorado por git).

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
