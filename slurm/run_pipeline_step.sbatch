#!/bin/bash
# ============================================================================
# run_pipeline_step.sbatch — wrapper generico para cualquier paso del pipeline
# ----------------------------------------------------------------------------
# Uso:
#     sbatch slurm/run_pipeline_step.sbatch <modulo.python> [args...]
#
# Ejemplos:
#     sbatch slurm/run_pipeline_step.sbatch pipeline.build_simlib \
#         --run baseline_v5.3.1_10yrs --strategy WFD
#     sbatch slurm/run_pipeline_step.sbatch pipeline.postprocess \
#         --campaign build/full_v5.3
#     sbatch slurm/run_pipeline_step.sbatch pipeline.tag_campaign \
#         --campaign build/full_v5.3
#
# Requiere 'logs/' existente. Ajusta recursos segun el paso: postprocess con
# muchas clases puede necesitar mas memoria; build_simlib WFD completo puede
# necesitar mas walltime.
#
# NOTA: usamos 'largemem' por defecto (misma razon que build_simlib.sbatch:
# NLHPC reasigna automaticamente jobs con esta razon memoria/CPU a largemem,
# asi que la pedimos explicito para evitar el mensaje de reasignacion).
# ============================================================================
#SBATCH -J pipeline_step
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 04:00:00
#SBATCH -o logs/step_%x_%j.out
#SBATCH -e logs/step_%x_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

MODULE="${1:?uso: sbatch slurm/run_pipeline_step.sbatch <modulo.python> [args...]}"
shift

cd "$SLURM_SUBMIT_DIR"
source activate_all.sh   # venv (auto-detectado) + module load SNANA + SNDATA_ROOT

echo "=== $MODULE $* · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date

python -m "$MODULE" "$@"

echo "=== terminado ==="
date
