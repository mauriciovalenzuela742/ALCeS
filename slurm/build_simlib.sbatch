#!/bin/bash
# ============================================================================
# build_simlib.sbatch — Capa 1 completa (sin --limit) via SLURM
# ----------------------------------------------------------------------------
# Uso:
#     sbatch slurm/build_simlib.sbatch <RUN> <STRATEGY>
#
# Ejemplos:
#     sbatch slurm/build_simlib.sbatch baseline_v5.3.1_10yrs WFD
#     sbatch slurm/build_simlib.sbatch baseline_v5.3.1_10yrs DDF
#
# Requiere que 'logs/' exista (SLURM no crea el directorio de salida solo):
#     mkdir -p logs
#
# Ajusta -p (partition), --mem y -t (walltime) segun lo que muestre `sinfo`
# y segun cuanto tarde tu corrida con --limit (para estimar el caso completo).
#
# NOTA: usamos 'largemem' por defecto. NLHPC reasigna automaticamente a esta
# particion cuando la razon memoria/CPU solicitada (aqui 16G/4 = 4096 MB/core)
# calza mejor con sus nodos largemem (16000 MB/core) que con 'general'. Pedirla
# explicito evita el mensaje de reasignacion y la reasignacion misma.
# ============================================================================
#SBATCH -J build_simlib
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 04:00:00
#SBATCH -o logs/build_simlib_%x_%j.out
#SBATCH -e logs/build_simlib_%x_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

RUN="${1:?uso: sbatch slurm/build_simlib.sbatch <RUN> <STRATEGY>}"
STRATEGY="${2:?uso: sbatch slurm/build_simlib.sbatch <RUN> <STRATEGY>}"

cd "$SLURM_SUBMIT_DIR"
source activate_all.sh   # venv (auto-detectado) + module load SNANA + SNDATA_ROOT

echo "=== build_simlib · run=$RUN strategy=$STRATEGY · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date

python -m pipeline.build_simlib --run "$RUN" --strategy "$STRATEGY"

echo "=== terminado ==="
date
