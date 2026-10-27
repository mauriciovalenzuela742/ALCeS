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

## Pendiente
- Agente 2 (armado de templates desde los datos).
- NMF, exportación a SNANA y validación.
