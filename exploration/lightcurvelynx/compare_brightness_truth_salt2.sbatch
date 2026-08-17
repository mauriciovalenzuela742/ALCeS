#!/bin/bash
# ============================================================================
# compare_brightness_truth_salt2.sbatch -- Fase 16: brillo sin ruido para
# SNIa/SALT2 (nunca antes probado -- Fase 7 solo cubrio SIMSED).
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/compare_brightness_truth_salt2.sbatch
# ============================================================================
#SBATCH -J cmp_truth_salt2
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:30:00
#SBATCH -o logs/cmp_truth_salt2_%j.out
#SBATCH -e logs/cmp_truth_salt2_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 16: brillo sin ruido SNIa/SALT2 · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 compare_brightness_truth_salt2.py

echo "=== terminado ==="
date
