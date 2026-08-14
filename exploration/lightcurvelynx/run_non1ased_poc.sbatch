#!/bin/bash
# ============================================================================
# run_non1ased_poc.sbatch — Fase 6: PoC GENMODEL: NON1ASED
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_non1ased_poc.sbatch <clase>
#     (clases: SNIa-91bg, SNIax, TDE, SLSN-I, KN-BULLA-BNS-M2COMP)
# ============================================================================
#SBATCH -J lcl_non1ased_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 02:00:00
# Nota (Fase 7): SNIa-91bg/TDE/SLSN-I cargan rapido (35 templates o 1 solo),
# pero SNIax tiene 1001 templates (~13.6 min medido, smoke job 11483743) y
# KN-BULLA-BNS-M2COMP 550 -- mismo margen generoso que run_simsed_poc.sbatch.
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
