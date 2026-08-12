#!/bin/bash
# ============================================================================
# run_capa4_full_capa5.sbatch — cierra la campana full_v5.3_10yrs de verdad
# ----------------------------------------------------------------------------
# Corre, en un solo job (nunca en el login node):
#   1. Capa 4 (QC) para las 80 GENVERSION de la campana (WFD+DDF), resolviendo
#      la raiz real de simulacion (DATASIM_LSST_1/{WFD,DDF}/SIM{W,D}v8) en vez
#      del $SNDATA_ROOT/SIM por defecto (vacio tras la limpieza de cuota).
#      Reescribe el postprocess_manifest.json completo.
#   2. Capa 5 (procedencia) sobre la campana completa.
#
# Supersede a run_capa4_capa5_remainder.sbatch, que solo cubria 2 GENVERSION
# y dejaba el manifiesto con ~58 "skipped" que en realidad ya existian.
#
# Uso:
#     sbatch slurm/run_capa4_full_capa5.sbatch
# ============================================================================
#SBATCH -J capa4_full_capa5
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=180G
#SBATCH -t 03:00:00
#SBATCH -o logs/capa4_full_capa5_%j.out
#SBATCH -e logs/capa4_full_capa5_%j.err
#SBATCH --mail-type=END,FAIL

# 180G porque el PHOT.FITS mas grande (d-Scuti_DDF) pesa 8.9GB sin comprimir;
# fitsio/astropy + conversion a DataFrame + byte-order nativo puede multiplicar
# eso varias veces en memoria. El primer intento con 16G murio con OOM.

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
source activate_all.sh

echo "=== Capa 4 full (80 GENVERSION, WFD+DDF) · job=$SLURM_JOB_ID · nodo=$(hostname) ==="
date
python3 -u pipeline/tools/run_qc_full.py --force

echo "=== Capa 5 (procedencia) · campaign=build/full_v5.3_10yrs ==="
date
python -m pipeline.tag_campaign --campaign build/full_v5.3_10yrs

echo "=== terminado ==="
date
