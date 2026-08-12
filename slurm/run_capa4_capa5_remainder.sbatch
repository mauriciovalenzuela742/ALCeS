#!/bin/bash
# ============================================================================
# run_capa4_capa5_remainder.sbatch — cierra la campana full_v5.3_10yrs
# ----------------------------------------------------------------------------
# Corre, en un solo job (nunca en el login node):
#   1. Capa 4 (QC) para las 2 GENVERSION que llegaron despues del batch
#      principal (job 11337320): SNIa_WFD y SNII_WFD. Fusiona el resultado
#      en el postprocess_manifest.json existente.
#   2. Capa 5 (procedencia) sobre la campana completa, ya con las 75
#      GENVERSION disponibles.
#
# Uso:
#     sbatch slurm/run_capa4_capa5_remainder.sbatch
# ============================================================================
#SBATCH -J capa4_5_remainder
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 02:00:00
#SBATCH -o logs/capa4_5_remainder_%j.out
#SBATCH -e logs/capa4_5_remainder_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
source activate_all.sh

echo "=== Capa 4 remainder (SNIa_WFD, SNII_WFD) · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
python3 pipeline/tools/run_qc_remainder.py

echo "=== Capa 5 (procedencia) · campaign=build/full_v5.3_10yrs ==="
date
python -m pipeline.tag_campaign --campaign build/full_v5.3_10yrs

echo "=== terminado ==="
date
