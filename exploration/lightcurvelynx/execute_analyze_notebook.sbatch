#!/bin/bash
# ============================================================================
# execute_analyze_notebook.sbatch -- Fase 17: ejecuta analyze_phot_df.ipynb
# de punta a punta contra los datos reales ya en disco (nbconvert --execute),
# para verificar que corre sin error antes de dejarlo commiteado.
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/execute_analyze_notebook.sbatch
# ============================================================================
#SBATCH -J exec_nb
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:15:00
#SBATCH -o logs/exec_nb_%j.out
#SBATCH -e logs/exec_nb_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 17: ejecutar analyze_phot_df.ipynb · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
jupyter nbconvert --to notebook --execute --inplace analyze_phot_df.ipynb

echo "=== terminado ==="
date
