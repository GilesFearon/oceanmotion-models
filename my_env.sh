#!/bin/bash
# Shared environment for all oceanmotion-models scripts.
# All variables can be overridden by setting them before sourcing this file.
#
# Usage:
#   source my_env.sh                    # use all defaults
#   DOMAIN=gulf_02 source my_env.sh     # override domain
#   RUN_DATE=20260317_00 source my_env.sh  # override run date

# --- Run date (auto-calculate if not set) ---
if [ -z "${RUN_DATE}" ]; then
  _hour=$(date -u +'%H' | awk '{print int($1 - ($1%12))}')
  RUN_DATE=$(date -u +"%Y%m%d_$(printf '%02d' ${_hour})")
fi
# Formatted for somisana CLI commands: "YYYY-MM-DD HH:00:00"
RUN_DATE_FMT="${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00"

# --- Run parameters ---
HDAYS="${HDAYS:-0}"
FDAYS="${FDAYS:-7}"
YORIG="${YORIG:-2000}"

# --- Domain and model identifiers ---
DOMAIN="${DOMAIN:-gulf_01}"
MODEL="${MODEL:-croco_v1.3.1}"

# --- Forcing / compilation identifiers ---
COMP="${COMP:-C06}"
INP="${INP:-I01}"
OGCM="${OGCM:-MERCATOR}"
BLK="${BLK:-GFS}"
TIDE_FRC="${TIDE_FRC:-TPXO10}"

# --- CROCO source and MPI ---
CROCO_SOURCE="${CROCO_SOURCE:-/home/$USER/code/croco-v1.3.1/OCEAN/}"
CROCO_MPI_NUM_X="${CROCO_MPI_NUM_X:-5}"
CROCO_MPI_NUM_Y="${CROCO_MPI_NUM_Y:-3}"
CROCO_MPI_NUM_PROCS=$(( CROCO_MPI_NUM_X * CROCO_MPI_NUM_Y ))

# --- WW3 model identifiers ---
WW3_MODEL="${WW3_MODEL:-ww3_v6.07.1}"
WW3_EXE_DIR="${WW3_EXE_DIR:-/home/$USER/code/WW3/model/exe_Ifremer1}"
WW3_MPI_NUM_PROCS="${WW3_MPI_NUM_PROCS:-16}"

# --- CLI repo paths and conda environments ---
DOWNLOAD_REPO="${DOWNLOAD_REPO:-/home/${USER}/code/somisana-download}"
CROCO_REPO="${CROCO_REPO:-/home/${USER}/code/somisana-croco}"
WW3_REPO="${WW3_REPO:-/home/${USER}/code/somisana-ww3}"
DOWNLOAD_ENV="${DOWNLOAD_ENV:-download}"
CROCO_ENV="${CROCO_ENV:-somisana_croco}"
WW3_ENV="${WW3_ENV:-wavespectra}"

# --- CMEMS credentials (required for download only) ---
# COPERNICUS_USERNAME and COPERNICUS_PASSWORD should be set via .env or env vars

# --- Derived paths (also overridable) ---
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
CONFIG_DIR="${CONFIG_DIR:-${REPO_DIR}/configs/${DOMAIN}/${MODEL}/forecast}"
TPXO_DATA_DIR="${TPXO_DATA_DIR:-/home/gfearon/code/somisana-croco/DATASETS_CROCOTOOLS/TPXO10}/"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-${REPO_DIR}/data/downloads/${RUN_DATE}/${DOMAIN}}"
DOMAIN_DOWNLOAD="${DOMAIN_DOWNLOAD:-45,60,21,33}"
OPS_DIR="${OPS_DIR:-${REPO_DIR}/data/croco_ops/${RUN_DATE}/${DOMAIN}/${MODEL}}"
RUN_NAME="${RUN_NAME:-${COMP}_${INP}_${OGCM}_${TIDE_FRC}}"

# --- Postprocessing paths ---
OBS_COEF_DIR="${OBS_COEF_DIR:-/home/${USER}/projects/gulf/data/water_level_obs/from_Chris_2024-03-30/postprocess}"
TIDAL_ANALYSIS_DIR="${TIDAL_ANALYSIS_DIR:-${REPO_DIR}/configs/${DOMAIN}/${MODEL}/hindcast/tidal_analysis}"
MERCATOR_ANALYSIS_DIR="${MERCATOR_ANALYSIS_DIR:-/home/${USER}/projects/ocean-motion/data/MERCATOR/gulf_ssh}"

# --- WW3 derived paths ---
WW3_CONFIG_DIR="${WW3_CONFIG_DIR:-${REPO_DIR}/configs/${DOMAIN}/${WW3_MODEL}/forecast}"
WW3_OPS_DIR="${WW3_OPS_DIR:-${REPO_DIR}/data/ww3_ops/${RUN_DATE}/${DOMAIN}/${WW3_MODEL}}"
