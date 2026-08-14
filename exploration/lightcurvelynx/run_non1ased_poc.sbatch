#!/bin/bash
# ============================================================================
# run_non1ased_poc.sbatch — Fase 6: PoC GENMODEL: NON1ASED
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_non1ased_poc.sbatch <clase>
#     (clases: SNIa-91bg)
# ============================================================================
#SBATCH -J lcl_non1ased_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:30:00
# Nota: SNIa-91bg NON1ASED son los mismos 35 templates .SED que
# SIMSED.SNIa-91bg (~0.5s/template, ver run_simsed_poc.sbatch) -- carga
# rapida, tiempo generoso por las dudas.
#SBATCH -o logs/lcl_non1ased_poc_%j.out
#SBATCH -e logs/lcl_non1ased_poc_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
CLASS_KEY="${1:?uso: sbatch run_non1ased_poc.sbatch <clase> [seed_index]  (SNIa-91bg)}"
SEED_INDEX="${2:-0}"

cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 6: NON1ASED $CLASS_KEY DDF PoC (seed_index=$SEED_INDEX) · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 run_non1ased_poc.py "$CLASS_KEY" "$SEED_INDEX"

echo "=== terminado ==="
date
