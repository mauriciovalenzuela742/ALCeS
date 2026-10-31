#!/bin/bash
# ============================================================================
# e1_leakage.sbatch -- E1: fuga por template (particion aleatoria vs agrupada)
# ----------------------------------------------------------------------------
# Necesita corridas con TEMPLATE_INDEX en head_df (codigo de la Fase 98 o
# posterior). Las de kn_confusion_diag/runs anteriores no lo traen: primero
#     sbatch exploration/lightcurvelynx/kn_confusion_gen.sbatch
# y despues (o con --dependency=afterok:<jobid>):
#     cd ~/AUTOSIM
#     sbatch research/lc_images/slurm/e1_leakage.sbatch [RUNS_DIR] [TAG]
# RUNS_DIR por defecto: exploration/lightcurvelynx/kn_confusion_diag/runs
# El kNN usa solo numpy/pandas/pyarrow: corre en el venv del simulador sin
# instalarle nada. Para --model gbdt hace falta el venv aparte con sklearn.
# ============================================================================
#SBATCH -J e1_leakage
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o logs/e1_leakage_%j.out
#SBATCH -e logs/e1_leakage_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

RUNS_DIR=${1:-exploration/lightcurvelynx/kn_confusion_diag/runs}
TAG=${2:-kn_cart_$(date +%Y%m%d)}
OUT=research/lc_images/results/e1/$TAG

date
python3 research/lc_images/experiments/e1_leakage.py --runs-dir "$RUNS_DIR" --out "$OUT"
python3 research/lc_images/experiments/e1_leakage.py --runs-dir "$RUNS_DIR" --out "$OUT/with_z" --with-z
date
