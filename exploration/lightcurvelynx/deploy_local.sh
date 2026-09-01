#!/usr/bin/env bash
# Fase 66: "deploy de un click" desde la maquina LOCAL del usuario (no
# desde NLHPC) -- automatiza el scp+ssh manual que se ha hecho a mano
# durante toda esta investigacion. Pieza SECUNDARIA/opcional: el flujo
# primario de un click sigue siendo `sweep_launch.py` corrido directamente
# en el login node (esto solo evita tener que hacer `ssh` a mano primero).
#
# Requiere: `ssh`/`scp` disponibles (Git Bash en Windows los trae), y un
# alias `nlhpc` ya configurado en ~/.ssh/config (uso manual preexistente
# de este proyecto, no algo nuevo que este script instale).
#
# Uso:
#   ./deploy_local.sh sweeps/<archivo>.yaml [--dry-run]
#
# Con --dry-run: sincroniza el codigo y compila el sweep en remoto, pero
# NO lo somete a SLURM -- pensado para probar el mecanismo antes de dejarlo
# lanzar sweeps reales de un solo comando.
set -euo pipefail

SWEEP_YAML="${1:?uso: deploy_local.sh sweeps/<archivo>.yaml [--dry-run]}"
DRY_RUN_FLAG="${2:-}"

REMOTE_HOST="nlhpc"
REMOTE_ROOT="AUTOSIM/exploration/lightcurvelynx"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$LOCAL_DIR/$SWEEP_YAML" ]; then
  echo "error: no existe $LOCAL_DIR/$SWEEP_YAML" >&2
  exit 1
fi

echo "» sincronizando codigo hacia $REMOTE_HOST:$REMOTE_ROOT ..."
# scp explicito de los .py de nivel superior + el YAML del sweep pedido --
# no todo exploration/lightcurvelynx/ (evita subir sweep_runs/, datasets/,
# poc_output_*, venv/, todo pesado y/o gitignorado). Si `rsync` esta
# disponible localmente, es una alternativa mas prolija (excluye por
# patron en vez de listar archivo por archivo):
#   rsync -avz --exclude 'sweep_runs' --exclude 'datasets' \
#       --exclude 'poc_output_*' --exclude '__pycache__' --exclude 'venv' \
#       "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_ROOT/"
scp "$LOCAL_DIR"/sweep_*.py "$REMOTE_HOST:$REMOTE_ROOT/"
scp "$LOCAL_DIR/$SWEEP_YAML" "$REMOTE_HOST:$REMOTE_ROOT/$(dirname "$SWEEP_YAML")/"

echo "» disparando compile+launch remoto ..."
ssh "$REMOTE_HOST" "cd $REMOTE_ROOT && module load python/3.12.3-legacy-skylake && \
    source venv/bin/activate && python3 sweep_launch.py $SWEEP_YAML $DRY_RUN_FLAG"
