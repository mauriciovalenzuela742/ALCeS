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

### 1. Cuota de disco casi llena — 99.94 / ~100 GB — PENDIENTE, decisión tuya
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

**Pendiente:** decidir qué borrar (o pedir aumento de cuota a NLHPC) antes
de relanzar la campaña completa. Sin esto resuelto, cualquier relanzamiento
masivo va a volver a fallar igual.

### 2. `MXOBS_SIMLIB=30000` — límite fijo del binario SNANA 11.05p — SIN solución de pipeline
Afecta **el 100% de las clases DDF**. 104 de los 1000 campos DDF superan
30,000 observaciones en 10 años completos (hasta 47,210 en algunos). No es
un parámetro de entrada — es una constante de compilación
(`strings snlc_sim.exe | grep MXOBS_SIMLIB` lo confirma, sin flag de
override). Opciones para cuando retomemos:
- Revisar si hay una versión más nueva de SNANA en NLHPC (`module avail SNANA`)
  con el límite más alto o corregido.
- Filtrar el SIMLIB DDF para no incluir campos con >30000 obs (perdiendo
  esos campos, no el rango temporal).
- Pedir a NLHPC/soporte SNANA si hay un binario custom compilado con
  `MXOBS_SIMLIB` más alto.
- Contactar a los devs de SNANA (RickKessler/SNANA en GitHub) — no encontré
  el límite documentado como configurable.

### 3. 5 clases NON1ASED "en desarrollo" — falta bloque `NON1A:` — necesita tu criterio científico
`SIMGEN_INCLUDE_{SNIax,SNIa-91bg,TDE,SLSN-I}_NON1ASED.INPUT` y
`SIMGEN_INCLUDE_BULLA-BNS-M2-2COMP.INPUT` (en
`run_SNANA/elastic/model_config/`) declaran `GENMODEL: NON1ASED` y un
`PATH_NON1ASED:` que sí apunta a un `NON1A.LIST` real y completo (1008
templates para SNIax, generados por
`convert_SIMSED_to_NON1ASED.py` — herramienta oficial de SNANA/NERSC) —
pero **falta el bloque `NON1A: <index> <peso> <MAGOFF> <MAGSMEAR> <SNTYPE>`**
que selecciona/pesa esos templates. Sin eso, `prep_NON1ASED` aborta con
"found no NON1A". Mecánicamente completable (autogenerar 1008 líneas con
peso uniforme), pero antes de generar eso para 5 clases distintas hace
falta definir el `SNTYPE` code correcto por clase y el criterio de peso —
no algo que deba inventar yo solo.

### 4. Cepheid — sin templates LCLIB para latitud galáctica alta — límite de catálogo
`readNext_LCLIB: Unable to find 5.0 deg b-angle match ... Sim b=-58.71 deg`.
El catálogo LCLIB de Cepheid solo cubre el disco galáctico; varios campos
WFD/DDF están a alta latitud galáctica (extragaláctico) donde no hay
templates. Esto es una limitación real del catálogo, no algo que el
pipeline pueda inventar — habría que confirmar si existe una versión del
catálogo con cobertura full-sky, o aceptar que Cepheid solo puede
simularse en el subconjunto de campos cercanos al plano galáctico.

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

- [ ] Decidir limpieza de disco (o pedir cuota — ítem 1)
- [ ] Investigar `MXOBS_SIMLIB` — versión SNANA alternativa o filtrar SIMLIB DDF (ítem 2)
- [ ] Definir SNTYPE/pesos para las 5 clases NON1ASED (ítem 3)
- [ ] Decidir qué hacer con Cepheid (ítem 4)
- [ ] Resolver origen de la fase real para VC25_SNII (o descartarlo)
- [ ] Una vez resuelto lo anterior: recompilar + relanzar `full_v5.3_10yrs`
      completa, y verificar con la marca correcta (`DONE with snlc_sim.`)
