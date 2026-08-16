#!/bin/bash
# ============================================================================
# fase11_zgrid_compare.sbatch -- Fase 11: corre fase11_zgrid_compare.py para
# ambas clases (control SNIa-91bg + hipotesis SLSN-I-MOSFIT) contra los .log
# ya generados por run_fase11_zgrid.sbatch.
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/fase11_zgrid_compare.sbatch
# ============================================================================
#SBATCH -J fase11_zgrid_cmp
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 2
#SBATCH --mem=8G
#SBATCH -t 00:30:00
#SBATCH -o logs/fase11_zgrid_cmp_%j.out
#SBATCH -e logs/fase11_zgrid_cmp_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

cd exploration/lightcurvelynx

echo "=== Fase 11: comparacion SNIa-91bg (control) · job=$SLURM_JOB_ID ==="
date
python3 fase11_zgrid_compare.py SNIa-91bg

echo "=== Fase 11: comparacion SLSN-I-MOSFIT (hipotesis) · job=$SLURM_JOB_ID ==="
date
python3 fase11_zgrid_compare.py SLSN-I-MOSFIT

echo "=== terminado ==="
date
