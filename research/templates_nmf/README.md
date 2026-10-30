# Base de templates y templates NMF para SNANA

Línea pedida por el profesor (2026-10-27). Es aditiva: los templates nuevos entrarán como modelos
nuevos en `pipeline/models.yaml` y no modifican los existentes ni el simulador.

- **Plan:** documento "Plan: base de templates y templates NMF para SNANA" (Claude Docs).
- **Alcance actual:** solo supernovas.
- **Cómputo:** Leftraru vía SLURM; Kimal (cluster de ALeRCE en el NLHPC) cuando haya acceso.

## Agente 1: búsqueda de fuentes (en curso)
- Definición: `agents/template-scout.md` (agente de IA). Como `.claude/` está en `.gitignore`, la
  copia versionada es esta; para usarlo como subagente de Claude Code, copiarla a `.claude/agents/`.
- Esquema de salida: `catalog/SCHEMA.md`. Validador: `catalog/validate_catalog.py`.
- Cada corrida escribe `catalog/parts/<grupo>.csv` más un `.md` con las búsquedas hechas.
  Después se unen con:
  ```
  python catalog/validate_catalog.py catalog/parts/*.csv --out catalog/sources.csv
  ```
- Las filas con `verified` distinto de `yes` necesitan revisión humana antes de usarse.

### Etapa 2: inventario por objeto e informe de viabilidad
- Esquema: `catalog/OBJECTS_SCHEMA.md`. Cada fuente tiene un script
  `catalog/objects/scripts/<source_id>.py` que descarga sus tablas públicas a
  `catalog/objects/raw/` (ignorado por git) y escribe `catalog/objects/parts/<source_id>.csv`.
- `catalog/viability.py` une las fuentes por nombre y posición y escribe
  `catalog/viability.md`: por subclase, cuántos objetos cumplen los niveles `foto`
  (z espectroscópico, ≥3 bandas, ≥15 puntos), `espectro` (además ≥3 espectros) y `completo`
  (además metalicidad y distancia usable). Ese informe decide con qué clases parte el NMF.

## Agente 2: armado de datos (en curso)
- `assemble/`: librería determinista. Paso 1 hecho para SNII de CSP-I (`build_csp_snii.py`):
  fotometría en AB corregida por la Vía Láctea, fase en reposo desde la explosión, índice de
  espectros y metalicidad local. Ver `assemble/README.md`.
- Falta, según lo que responda el profesor: distancia, extinción del host, mangling y rejilla.

## NMF (en curso)
- `nmf/wnmf.py`: NMF con pesos 1/σ², datos faltantes y ridge opcional, con tests.
- Exploración fotométrica de SNII de CSP-I (solo forma): k = 5 por validación cruzada; varias
  componentes codifican la duración del plateau. Ver `nmf/README.md`.
- Alineando por el fin del plateau (OPTd de Anderson+14, 37 SNe) el error de validación baja a
  la mitad para cada k y bastan 3–4 componentes.
- `assemble/fit_plateau_end.py` mide el fin del plateau en V (Olivares+10) en 23 SNe; coincide
  con OPTd con un corrimiento casi constante de unos 12 días, pero solo agrega 2 SNe sin OPTd.

## Pendiente
- NMF, exportación a SNANA y validación.
