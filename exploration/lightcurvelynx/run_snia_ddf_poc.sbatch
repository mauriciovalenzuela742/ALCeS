#!/bin/bash
# ============================================================================
# run_snia_ddf_poc.sbatch — Fase 1 LightCurveLynx: PoC SNIa_DDF
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_snia_ddf_poc.sbatch
#
# Liviano (NGENTOT_LC=2000, DDF, ~seg de simulacion segun bench_snia.py) pero
# via SLURM de todas formas, nunca en el login node para nada no trivial
# (misma convencion que el resto del pipeline).
# ============================================================================
#SBATCH -J lcl_snia_ddf_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:30:00
#SBATCH -o logs/lcl_snia_ddf_poc_%j.out
#SBATCH -e logs/lcl_snia_ddf_poc_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 1 LightCurveLynx: SNIa_DDF PoC · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 run_snia_ddf_poc.py

echo "=== terminado ==="
date
