# Bitácora de sesión — 2026-08-03 — para retomar mañana

Estado real de `full_v5.3_10yrs` tras el primer intento con los 10 años
completos: **15/84 GENVERSION terminaron de verdad** (WFD), **0/84 DDF**.
El resto abortó por 4 causas distintas, ya diagnosticadas. Nada de esto es
"casi listo" — son bloqueos reales que requieren decisiones tuyas antes de
seguir. Ver detalle completo en `README.md` → "Decisiones y correcciones"
(ítems 13-15 ya agregados hoy).

**Ojo con la marca de éxito real:** es `DONE with snlc_sim.` en el `.out`
de cada job — **no** `DONE EVERYTHING` como decía el README viejo (ya
corregido). Un GENVERSION con `.FITS` en `$SNDATA_ROOT/SIM/` **no implica
que terminó bien** — SNANA escribe eventos progresivamente y puede abortar
a mitad de camino dejando un FITS parcial. Siempre verificar con:
```bash
grep -L 'DONE with snlc_sim' build/full_v5.3_10yrs/*.out   # los que NO terminaron
```

## Las 4 causas de falla (ninguna es un bug de este pipeline en sí, salvo la ya arreglada)

### 1. Cuota de disco casi llena — 99.94 / ~100 GB — **RESUELTO (2026-08-06)**
No hay `/scratch` en este login node — todo vive en `/home` (GPFS) con
cuota por usuario. Con 30+ jobs grandes escribiendo FITS en paralelo, la
cuota se agotó a mitad de campaña → `FITSIO status = 106: error writing to
FITS file` (cfitsio `WRITE_ERROR`) en 16 clases WFD. Esto probablemente
explica la mayoría de las fallas WFD que no son por otra causa conocida.

Desglose de los 100GB (revisado, nada borrado todavía):
- `DATASIM_LSST_1` — 56 GB (simulaciones manuales previas, pre-pipeline)
- `run_SNANA` — 18 GB
- `SNDATA_ROOT` — 15 GB (salida de la campaña actual)
- `AUTOSIM` — 4.8 GB
- `SIMLIBv5` / `SIMLIBv5.3` — 3.2 + 2.9 GB (candidatos a borrar: parecen
  reemplazados por `AUTOSIM/data/simlib`, que ya tiene los SIMLIB reales
  de 10 años regenerados hoy — confirmar antes de borrar)
- `OTMODEL_NON1ASED` — 1.1 GB

**Resuelto:** se liberaron ~60GB (`SIMWv6`/`SIMDv6` borrados sin respaldo —
reproducibles desde config; `SIMWv7`/`SIMDv7` comprimidos y verificados;
`SNDATA_ROOT/SIM` del último intento borrado; `venv_zen4_broken` borrado).
`home` bajó de 100G a ~39G. La solicitud de aumento de cuota a NLHPC sigue
en paralelo por las dudas, pero ya no bloquea relanzar.

### 2. `MXOBS_SIMLIB=30000` — límite fijo del binario SNANA 11.05p — **RESUELTO (2026-08-06)**
Afectaba **el 100% de las clases DDF**. 104 de los 1000 campos DDF superan
30,000 observaciones en 10 años completos (hasta 47,210 en algunos).

**Resuelto:** ya existía un clone actualizado de SNANA en
`~/github/SNANA_src` (NLHPC, `RickKessler/SNANA` commit `2f0773e3`,
`v12_02-66-g2f0773e3`) donde `MXOBS_SIMLIB` está atado a `MXEPOCH=60000`
(`sndata.h`) — por encima del máximo real, sin tocar ninguna constante.
Se compiló (`src/Makefile.legacy`, target `snlc_sim.exe`, con 2 parches
triviales para no requerir Python/ROOT dev — ver README ítem 16) y se
dejó en `~/AUTOSIM/bin/snana_custom/snlc_sim.exe`. `campaigns/full_v5.3.yaml`
→ `batch.snana_login_setup` ahora antepone ese binario al `PATH` después
del `ml SNANA/11.05p` — sin tocar código del pipeline.

Efecto colateral encontrado y corregido: el source nuevo (~v12_02) ya no
asume `GENSIGMA_MWEBV_RATIO: 0.16` por defecto como sí lo hacía 11.05p —
se agregó explícito en `pipeline/campaign/templates.py::render_survey_include`
para que el comportamiento sea idéntico entre ambos binarios.

Validado con jobs reales en partición `general` (Skylake) contra el SIMLIB
DDF completo de 10 años: termina con `DONE with snlc_sim.`, sin abort de
MXOBS_SIMLIB (antes: `FATAL ERROR ABORT ... MXOBS_SIMLIB=30000 -> array
overflow`, confirmado en el log original `run_CaRT_DDF_..._11021830.out`).
**Confirmado de forma definitiva (no solo probabilística):** job adicional
con `SIMLIB_MINOBS: 40000` (fuerza a usar solo campos por encima de ese
umbral — garantizado a tocar uno de los 104 problemáticos, máximo real
47,210 obs) terminó con `DONE with snlc_sim.` sin ningún error. El fix
queda 100% confirmado para el caso peor real, no solo estadísticamente
probable.

### 3. 5 clases NON1ASED "en desarrollo" — bloque `NON1A:` **ya generado y validado (2026-08-06)**
`SIMGEN_INCLUDE_{SNIax,SNIa-91bg,TDE,SLSN-I}_NON1ASED.INPUT` y
`SIMGEN_INCLUDE_BULLA-BNS-M2-2COMP.INPUT` (en
`run_SNANA/elastic/model_config/`) declaran `GENMODEL: NON1ASED` y un
`PATH_NON1ASED:` que sí apunta a un `NON1A.LIST` real y completo (1008
templates para SNIax, generados por
`convert_SIMSED_to_NON1ASED.py` — herramienta oficial de SNANA/NERSC) —
faltaba el bloque `NON1A: <index> <peso> <MAGOFF> <MAGSMEAR> <SNTYPE>`
que selecciona/pesa esos templates; sin eso, `prep_NON1ASED` abortaba con
"found no NON1A".

**Resuelto:** `pipeline/tools/generate_non1a_block.py` (nuevo, peso uniforme
`1/N` sobre los índices reales del `NON1A.LIST` de cada clase, `MAGOFF`/
`MAGSMEAR` en 0.0 por falta de calibración observacional documentada,
`SNTYPE` pasado como argumento) generó el bloque para las 5 clases y se
insertó en NLHPC (los 5 `SIMGEN_INCLUDE_*.INPUT` en
`run_SNANA/elastic/model_config/`, modificados 2026-08-06 09:44):

| Clase | SNTYPE | Templates (N) | Peso c/u |
|---|---|---|---|
| `SIMGEN_INCLUDE_BULLA-BNS-M2-2COMP.INPUT` (KN-BULLA-BNS-M2COMP) | 62 | 550 | 1.818182e-03 |
| `SIMGEN_INCLUDE_SLSN-I_NON1ASED.INPUT` | 41 | 1 | 1.0 |
| `SIMGEN_INCLUDE_SNIa-91bg_NON1ASED.INPUT` | 13 | 35 | 2.857143e-02 |
| `SIMGEN_INCLUDE_SNIax_NON1ASED.INPUT` | 12 | 1001 | 9.990010e-04 |
| `SIMGEN_INCLUDE_TDE_NON1ASED.INPUT` | 51 | 1 | 1.0 |

**Validación mecánica (`build/test_non1a_fix`, NGENTOT_LC=300 WFD c/u,
lanzados como jobs SLURM 11081774–11081778):** las 5 terminaron con `DONE
with snlc_sim.` en su `.out` y sin `ABORT`/`FATAL` (`.err` vacío en las 5) —
el fix del bloque `NON1A:` funciona para las 5 clases, ya no abortan.

- **SLSN-I_NON1ASED**: `NGENLC_WRITE: 111/300` (EFF=0.37) — curvas de luz reales generadas. OK.
- **TDE_NON1ASED**: `NGENLC_WRITE: 44/300` (EFF=0.147) — OK.
- **SNIa-91bg_NON1ASED**: `NGENLC_WRITE: 12/300` (EFF=0.04) — OK.
- **SNIax_NON1ASED**: `NGENLC_WRITE: 2/300` (EFF=0.0067) — OK (eficiencia baja
  pero sí produjo curvas).
- **KN-BULLA-BNS-M2COMP**: `NGENLC_WRITE: 0/300` (EFF=0.0000,
  `NREJECT: [1,0,0, 299,0]` — 299/300 rechazados por `SEARCHEFF`, i.e. no
  cumplen "2 detecciones"). El `HEAD.FITS`/`PHOT.FITS` resultante son FITS
  válidos pero con `NAXIS2=0` (confirmado con `astropy.io.fits`, 0 filas en
  ambos) — **por eso no vienen comprimidos en `.gz`**: no es un bug, SNANA
  no gzipea un output vacío al no haber datos que escribir ("wrote 0 events
  and 0 spectra to FITS format" en el log). No es un ABORT ni indica que el
  bloque `NON1A:` esté mal — es consistente con que las kilonovas son
  intrínsecamente débiles/rápidas y difíciles de detectar en WFD, y a
  `NGENTOT_LC=300` (tamaño de prueba, no el valor real de producción) 0/300
  detectadas es estadísticamente plausible. **Pendiente:** repetir con un
  `NGENTOT_LC` mayor (valor real de campaña, no el de prueba) para confirmar
  que la clase sí produce curvas de luz utilizables antes de darla por
  completamente validada — las otras 4 sí quedaron confirmadas con datos
  reales.

### 4. Cepheid — sin templates LCLIB para latitud galáctica alta — **investigado, queda pausado (2026-08-06)**
`readNext_LCLIB: Unable to find 5.0 deg b-angle match ... Sim b=-58.71 deg`.
El catálogo LCLIB de Cepheid (`LCLIB_Cepheid-LSST.TEXT`, modelo
`ZTFDR3VSXCEPHEID`) solo cubre |b|≈-52° a +49° (disco galáctico); WFD
cubre mayormente cielo extragaláctico, fuera de ese rango.

**Investigado:** `SIMLIB_GALB_RANGE` **no es una keyword real de SNANA**
(cero resultados en el manual — probablemente una confusión de sesiones
anteriores). `SOLID_ANGLE` tampoco aplica: solo normaliza el conteo de
SNe/temporada en el README de salida, no afecta la generación de eventos
ni el matching de LCLIB. El mecanismo real es `ANGLEMATCH_b` (header del
propio LCLIB, no seteable desde `.INPUT`) y la única salida de emergencia
a nivel de config es `GENMODEL_MSKOPT: 1` (ignora el angle-match) — pero
eso haría que campos a |b| alto usen templates de latitud galáctica
incorrecta, una aproximación no física, no un fix real de cobertura.

**Decisión:** se descarta `GENMODEL_MSKOPT: 1` por la aproximación no
física que introduce. Cepheid queda pausado para v8, igual que
`VC25_SNII` — no se toca ningún `.INPUT`. Retomar solo si aparece un
catálogo LCLIB full-sky para Cepheid.

## Ya arreglado hoy (sincronizado a NLHPC, no repetir)

- **`temporal_cut` en `pipeline/simlib.yaml`** recortaba a ~3.5 años en vez
  de los 10 años completos — corregido a `null/null`. SIMLIB WFD y DDF ya
  regenerados con cobertura real de ~10 años.
- **Bug de nombres de archivo en `build_simlib.py`** (`save_reports`) —
  `Path.with_suffix()` aplicado dos veces truncaba nombres con puntos
  (`baseline_v5.3.1_10yrs` → `baseline_v5.3`), por lo que `compile_campaign`
  nunca encontraba el `.coverage.json` real y caía en silencio al rango MJD
  viejo por defecto. Corregido.
- **venv con intérprete Zen4** crasheaba con `Illegal instruction` en los
  nodos de cómputo (Skylake). Reconstruido con
  `module load python/3.12.3-legacy-skylake`. `activate_all.sh` actualizado
  para cargar ese módulo siempre.
- **13 rutas rotas en `pipeline/models.yaml`** apuntaban a
  `run_SNANA/model_config/` en vez de `run_SNANA/elastic/model_config/`.
- **`OPT_MWEBV`/`OPT_MWCOLORLAW` duplicado** — algunos modelos LCLIB ya
  traen su propio valor; el survey include ya no los fuerza, se inyectan
  por clase solo si el archivo curado no los define (`compiler.py` +
  `templates.py`).
- **QC (Capa 4)**: columna `BAND` vs `FLT`, cálculo de `MAG`/`MAGERR` desde
  `FLUXCAL`/`ZEROPT`, y normalización de byte-order (FITS es big-endian) —
  ver README ítem 14.

## Pausado por decisión tuya

**`VC25_SNII`** — faltan 21 de 31 SED (`.dat` fuente sí existen en
`OTMODEL_NON1ASED/dataPignataRamirez/datos/Procesados/Con mangling/II`).
Intenté convertir con `Convert_dat_to_sed.ipynb` + `maximum_II.txt` (peak
MJD) pero el rango de fase resultante (-86 a -12 días) no coincide con el
del `SED.gz` que sí funciona para el mismo objeto (-1 a 30 días) — algo no
cuadra en cómo se calculó la fase de los 10 originales. No toqué nada real
(quedó en `OTMODEL_NON1ASED/SNtypes/II/NON1ASED_VC25_SNII_new/`, se puede
borrar o investigar cuando retomes).

## Checklist para la próxima sesión

- [x] Decidir limpieza de disco (ítem 1) — ~60GB liberados, `home` en ~39G.
- [x] Investigar `MXOBS_SIMLIB` (ítem 2) — binario custom compilado y
      apuntado desde `campaigns/full_v5.3.yaml`, confirmado de forma
      definitiva contra el LIBID DDF real de 47,210 obs (`SIMLIB_MINOBS:
      40000`, job 11083357) sin ningún error.
- [x] Definir SNTYPE/pesos para las 5 clases NON1ASED (ítem 3) — bloque `NON1A:`
      generado e insertado en NLHPC, 4/5 validadas con curvas de luz reales
      (`build/test_non1a_fix`, 2026-08-06); `KN-BULLA-BNS-M2COMP` terminó sin
      abortar pero con 0/300 curvas escritas a `NGENTOT_LC` de prueba —
      repetir con NGEN real antes de darla por completa (ver ítem 3).
- [x] Decidir qué hacer con Cepheid (ítem 4) — investigado, sin fix de config
      real sin introducir una aproximación no física; queda **pausado** para
      v8 (igual que VC25_SNII).
- [ ] Resolver origen de la fase real para VC25_SNII (o descartarlo) — sigue
      **pausado** para v8, sin tocar.
- [ ] Validación agregada final: correr todas las clases DDF que antes
      fallaban (no solo `CaRT`) + las 5 NON1ASED a escala de producción, y
      con eso confirmar el alcance real de v8 = catálogo completo **menos**
      `VC25_SNII` y `Cepheid`.
- [ ] Lanzar `full_v5.3_10yrs`-v8 completa (WFD+DDF, catálogo confirmado) y
      verificar con la marca correcta (`DONE with snlc_sim.`).
