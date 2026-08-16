#!/bin/bash
# ============================================================================
# run_fase11_zgrid.sbatch -- Fase 11: muestrea densamente una ventana
# estrecha de redshift (3-5 celdas de la grilla LOGZBIN de SNANA) para
# SNIa-91bg (control, LOGZBIN=0.02) y SLSN-I-MOSFIT (hipotesis afilada,
# LOGZBIN=0.1), y conserva el .DUMP real (PEAKMAG_r, ZCMB, "SELECTION:
# NONE" -- TODO lo generado, no solo detectados).
# ----------------------------------------------------------------------------
# Uso:
#     cd ~/AUTOSIM
#     sbatch exploration/lightcurvelynx/fase11_simsed_zgrid/run_fase11_zgrid.sbatch
#
# Solo conserva los dos .DUMP (texto, chicos) -- el FITS/SIM real que
# snlc_sim.exe escribe en $SNDATA_ROOT/SIM/<GENVERSION> se borra al final,
# no hace falta para esta prueba (evita repetir el incidente de cuota de
# Fase 8/10).
# ============================================================================
#SBATCH -J fase11_zgrid
#SBATCH -p general
#SBATCH -n 1
#SBATCH -c 2
#SBATCH --mem=8G
#SBATCH -t 00:30:00
#SBATCH -o logs/fase11_zgrid_%j.out
#SBATCH -e logs/fase11_zgrid_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
source activate_all.sh

cd exploration/lightcurvelynx/fase11_simsed_zgrid

echo "=== Fase 11: SNIa-91bg (control, LOGZBIN=0.02) · job=$SLURM_JOB_ID ==="
date
snlc_sim.exe debug_SNIa91bg.INPUT > debug_SNIa91bg.log 2>&1
cp "$SNDATA_ROOT/SIM/Fase11_zgrid_SNIa91bg_DDF/Fase11_zgrid_SNIa91bg_DDF.DUMP" ./
echo "  filas en el .DUMP: $(wc -l < Fase11_zgrid_SNIa91bg_DDF.DUMP)"
# limpiar YA (no al final) -- SLSN-I-MOSFIT tiene muchas mas columnas
# SIMSED_PAR* y su FITS puede no caber si el de SNIa-91bg sigue ocupando
# espacio (incidente real: job 11561880, "FITSIO status = 106: error
# writing to FITS file" por cuota agotada a mitad de SLSN-I-MOSFIT).
rm -rf "$SNDATA_ROOT/SIM/Fase11_zgrid_SNIa91bg_DDF"

echo "=== Fase 11: SLSN-I-MOSFIT (hipotesis, LOGZBIN=0.1) · job=$SLURM_JOB_ID ==="
date
snlc_sim.exe debug_SLSNIMOSFIT.INPUT > debug_SLSNIMOSFIT.log 2>&1
cp "$SNDATA_ROOT/SIM/Fase11_zgrid_SLSNIMOSFIT_DDF/Fase11_zgrid_SLSNIMOSFIT_DDF.DUMP" ./
echo "  filas en el .DUMP: $(wc -l < Fase11_zgrid_SLSNIMOSFIT_DDF.DUMP)"
rm -rf "$SNDATA_ROOT/SIM/Fase11_zgrid_SLSNIMOSFIT_DDF"

echo "=== terminado ==="
date
