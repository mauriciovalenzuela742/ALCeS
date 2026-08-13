#!/bin/bash
# ============================================================================
# run_simsed_poc.sbatch — Fase 2 parte B: PoC SIMSED generalizado
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_simsed_poc.sbatch <clase>
#     (clases: KN-K17, CaRT, SLSN-I)
# ============================================================================
#SBATCH -J lcl_simsed_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 02:00:00
# Nota: la carga de templates SIMSED puede ser mucho mas lenta que en
# SNIa-91bg (35 templates, ~0.5s c/u) -- KN-K17 (329 templates) midio
# ~3.4s/template (~18.5 min solo para cargar), ver NOTES.md Fase 2 parte B.
# SLSN-I-MOSFIT tiene 960 templates -- tiempo generoso por las dudas.
#SBATCH -o logs/lcl_simsed_poc_%j.out
#SBATCH -e logs/lcl_simsed_poc_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
CLASS_KEY="${1:?uso: sbatch run_simsed_poc.sbatch <clase> [seed_index]  (KN-K17, CaRT, SLSN-I, ...)}"
SEED_INDEX="${2:-0}"

cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 2 parte B: SIMSED $CLASS_KEY DDF PoC (seed_index=$SEED_INDEX) · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 run_simsed_poc.py "$CLASS_KEY" "$SEED_INDEX"

echo "=== terminado ==="
date
