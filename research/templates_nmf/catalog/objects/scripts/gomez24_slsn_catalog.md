# gomez24_slsn_catalog (Gomez+24, github.com/gmzsebastian/SLSNe)

- El commit queda fijado en raw/gomez24_slsn_catalog/commit.txt (302369769afa). Se bajan sne_data.txt y 265 archivos de fotometría <SN>.txt (unos 6 MB).
- El repo tiene **265 SNe**; el abstract del paper (título verificado) dice **262**. Por calidad: 171 Gold, 70 Silver y 24 Bronze. No identifiqué las 3 extra; probablemente se agregaron después del paper.
- n_phot cuenta las detecciones con UL=False e Ignore=False: **33014** en total, coherente con las ">30000 detecciones" del paper.
- z_type según la columna Method:

  | Method | z_type | SNe |
  |---|---|---|
  | Host_lines, Host_spectrum | host_spec | 159 |
  | SN_features, Mg_Lines | spec | 89 |
  | Photo-z | photo | 1 |
  | Lyman_break, Unknown | unknown | 16 |

- ebv_mw = columna EBV. Se interpreta como E(B-V) de la Vía Láctea porque el paper corrige con SF11, pero el archivo no lo dice explícitamente.
- Fase como en slsne.lcurve: (MJD - Peak)/(1+z), respecto del pico en r y en reposo. Algunas phase_max llegan a unos 1070 d por la fotometría tardía.
- bands son los nombres de la columna Filter tal cual (r, g, i, orange, cyan, UVW1...). No normalicé los sistemas.
