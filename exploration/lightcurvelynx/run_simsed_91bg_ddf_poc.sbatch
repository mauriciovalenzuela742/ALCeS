#!/bin/bash
# ============================================================================
# run_simsed_91bg_ddf_poc.sbatch — Fase 2 parte B: primer PoC SIMSED
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_simsed_91bg_ddf_poc.sbatch
#
# SNIa-91bg_DDF, la mas simple de las 11 clases SIMSED del catalogo (35
# templates, NPAR=2). Requiere setup_simsed_91bg_local.py corrido antes al
# menos una vez (copia local con el fix de SED.INFO).
# ============================================================================
#SBATCH -J lcl_91bg_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:30:00
#SBATCH -o logs/lcl_91bg_poc_%j.out
#SBATCH -e logs/lcl_91bg_poc_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 2 parte B: SIMSED SNIa-91bg_DDF PoC · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 run_simsed_91bg_ddf_poc.py

echo "=== terminado ==="
date
