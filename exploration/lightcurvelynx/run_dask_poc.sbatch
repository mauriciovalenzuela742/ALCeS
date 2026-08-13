#!/bin/bash
# ============================================================================
# run_dask_poc.sbatch — validacion de orquestacion dask para Fase 2
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/run_dask_poc.sbatch
#
# Un solo job SLURM levanta un dask.distributed.LocalCluster interno -- todo
# el ciclo de vida del cluster (scheduler + workers) vive dentro de esta
# asignacion, nunca toca el login node. 4 workers, cada uno carga su propia
# copia de OpSim/passbands (no se comparte estado entre procesos), asi que
# se pide memoria generosa.
# ============================================================================
#SBATCH -J lcl_dask_poc
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH -t 00:30:00
#SBATCH -o logs/lcl_dask_poc_%j.out
#SBATCH -e logs/lcl_dask_poc_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
module load python/3.12.3-legacy-skylake
source exploration/lightcurvelynx/venv/bin/activate

echo "=== Fase 2 (prep): dask LocalCluster PoC · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
cd exploration/lightcurvelynx
python3 run_dask_poc.py

echo "=== terminado ==="
date
