# `kcor_LSST` — calibración/K-correction para toda la campaña

`kcor_LSST.fits` (generado a partir de `kcor_LSST.input`, este directorio) es el
archivo `KCOR_FILE:` usado por **las 80 GENVERSION** de la campaña (todas las clases,
WFD y DDF — ver `campaigns/full_v5.3.yaml` y `campaigns/test_small.yaml`,
`defaults.kcor_file`). Provee las curvas de transmisión de filtro LSST (`ugrizY`) y el
SED primario (`Hsiao07.dat`) que SNANA usa para sintetizar fotometría observer-frame.

## Procedencia

Hasta 2026-08, el `.fits` desplegado en NLHPC (`~/run_SNANA/kcor_LSST.fits`) era una
copia binaria sin versionar, generada en 2024 en la Mac personal de una practicante
anterior del proyecto (la cabecera FITS delataba `CWD: /Users/isidoramancilla/...`).
Al investigarlo se confirmó que su contenido (filtros, grid, SED) es **idéntico campo
a campo** a la muestra oficial que el propio equipo de SNANA distribuye para LSST:

```
$SNDATA_ROOT/kcor/LSST/baseline_1.9/kcor_LSST.input
```

(generado originalmente por el equipo de SNANA en `/project2/rkessler/PRODUCTS/...`,
según su propio `.log`). No es un archivo de prueba mal reusado — es el estándar
SNANA-LSST recomendado, sin overrides. Este directorio versiona ese mismo `.input`
como fuente reproducible, en vez de depender de una copia binaria sin origen.

Los throughputs de filtro (`$SNDATA_ROOT/filters/LSST/baseline_1.9`) corresponden al
tag oficial `lsst/throughputs@1.9` (github.com/lsst/throughputs). Se confirmó
(2026-08, `gh api repos/lsst/throughputs/compare/1.9...v1.9.1`) que la única release
más nueva disponible (`v1.9.1`, sep-2025) solo modifica filtros Johnson-Cousins y
archivos README — las curvas `LSST_{u,g,r,i,z,y}.dat` reales no cambiaron. No hace
falta actualizar los throughputs.

## ¿Por qué el grid de época/z/Av (TMIN=-20/TMAX=+85, 1 bin de z, 1 bin de Av) no es un problema?

`kcor.exe` con este `.input` (sin overrides) genera una tabla de K-correction con
`NKCOR=0` — es decir, en modo efectivamente `SKIPKCOR`: solo trae filtros + SED
primario, sin tabla de K-correction real.

Esto es exactamente lo que necesita este pipeline. Se confirmó contra el código fuente
de SNANA (`snlc_sim.c`, función `init_read_calib_wrapper`): la tabla de K-correction
solo se consulta cuando `GENFRAME_OPT == GENFRAME_REST` (modelos `mlcs2k2`, `snoopy`,
`stretch`). **Ninguna clase de este catálogo usa esos modelos** — las ~50
`SIMGEN_INCLUDE_*.INPUT` (`run_SNANA/model_config/`, `run_SNANA/elastic/model_config/`)
son `SALT2`, `SIMSED` (las variantes "MOSFIT"/NMF/91bg/BULLA/K17/STELLA/CaRT/ILOT/
PISN/SLSN/TDE), `NON1ASED` o `LCLIB` — todas hard-codeadas a `GENFRAME_OPT = GENFRAME_OBS`
en el propio `snlc_sim.c`, que sintetiza fotometría integrando el SED del modelo
directamente contra el filtro en cada época pedida, sin pasar por el grid de época/z/Av
del kcor. Por eso el `GENRANGE_TREST` amplio de varias clases (hasta -100/+300,
+500 o +1000 días en TDE/SLSN-I/PISN/ILOT/CaRT/KN-BULLA/NON1ASED) no entra en conflicto
con el TMIN/TMAX=-20/+85 del kcor — esa tabla nunca se consulta para esos modelos.

## Cómo regenerar

En un login node de NLHPC (liviano — no requiere SLURM):

```bash
cd ~/AUTOSIM/pipeline/kcor
source ~/AUTOSIM/activate_all.sh
kcor.exe kcor_LSST.input
```

Verificar en el `.log` resultante: `NFILTERS=6` (LSST-u/g/r/i/z/Y), rango de longitud
de onda 2100–12000 Å, `Found 106 epochs from day -20.0 to 85.0`, `NKCOR=0`. Esto debe
coincidir con `$SNDATA_ROOT/kcor/LSST/baseline_1.9/kcor_LSST.log` (la corrida oficial
de referencia del equipo SNANA).
