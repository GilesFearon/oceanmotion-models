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
# (I don't see a scenario where we have to make HDAYS>0, but if we do just beware - I'm not sure the restart handling will automatically work)
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
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG_DIR="${CONFIG_DIR:-${REPO_DIR}/configs/${DOMAIN}/${MODEL}/forecast}"
TPXO_DATA_DIR="${TPXO_DATA_DIR:-/home/gfearon/code/somisana-croco/DATASETS_CROCOTOOLS/TPXO10}/"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-${REPO_DIR}/data/${RUN_DATE}/downloads/${DOMAIN}}"
DOMAIN_DOWNLOAD="${DOMAIN_DOWNLOAD:-45,60,21,33}"
OPS_DIR="${OPS_DIR:-${REPO_DIR}/data/${RUN_DATE}/croco_ops/${DOMAIN}/${MODEL}}"
RUN_NAME="${RUN_NAME:-${COMP}_${INP}_${OGCM}_${TIDE_FRC}}"

# --- Postprocessing paths ---
OBS_COEF_DIR="${OBS_COEF_DIR:-/home/${USER}/projects/gulf/data/water_level_obs/from_Chris_2024-03-30/postprocess}"
TIDAL_ANALYSIS_DIR="${TIDAL_ANALYSIS_DIR:-${REPO_DIR}/configs/${DOMAIN}/${MODEL}/hindcast/tidal_analysis}"
MERCATOR_ANALYSIS_DIR="${MERCATOR_ANALYSIS_DIR:-/home/${USER}/projects/ocean-motion/data/MERCATOR/gulf_ssh}"

# --- WW3 derived paths ---
WW3_CONFIG_DIR="${WW3_CONFIG_DIR:-${REPO_DIR}/configs/${DOMAIN}/${WW3_MODEL}/forecast}"
WW3_OPS_DIR="${WW3_OPS_DIR:-${REPO_DIR}/data/${RUN_DATE}/ww3_ops/${DOMAIN}/${WW3_MODEL}}"

# --- Turbidity model identifiers and paths ---
TURB_MODEL="${TURB_MODEL:-turbidity_v1}"
TURB_RUN_NAME="${TURB_RUN_NAME:-calib_01}"
TURB_CODE_DIR="${TURB_CODE_DIR:-${REPO_DIR}/turbidity}"
TURB_ENV="${TURB_ENV:-somisana_croco}"
TURB_OPS_DIR="${TURB_OPS_DIR:-${REPO_DIR}/data/${RUN_DATE}/turbidity_ops/${DOMAIN}/${TURB_MODEL}/${TURB_RUN_NAME}}"
TURB_OUT_FILE="${TURB_OUT_FILE:-turbidity_3d.nc}"
# Restart snapshots are written every TURB_RST_HOURS hours of model time.
# Must be consistent across operational cycles so that each new run finds
# a snapshot at its own RUN_DATE in the previous cycle's output.
TURB_RST_HOURS="${TURB_RST_HOURS:-6}"

# --- Turbidity sediment parameters (two classes: fine, coarse) ---
# Defaults match configs/gulf_01/turbidity/hindcast/calib_01 calibration.
WS_FINE="${WS_FINE:-1e-4}"
WS_COARSE="${WS_COARSE:-1e-3}"
M_FINE="${M_FINE:-0.0003}"
M_COARSE="${M_COARSE:-0.003}"
TAU_CR_FINE="${TAU_CR_FINE:-0.1}"
TAU_CR_COARSE="${TAU_CR_COARSE:-0.25}"
C_BG="${C_BG:-3.0}"

# --- Latest hindcast/forecast publishing tier ---
# data/latest/{raw,postprocess,web}/{DOMAIN}/... is rebuilt every cycle from
# the most recent HDAYS_LATEST + FDAYS_LATEST window of per-cycle raw output.
HDAYS_LATEST="${HDAYS_LATEST:-10}"
FDAYS_LATEST="${FDAYS_LATEST:-7}"
# Single source of truth for the regular-grid spacing on which all spatial
# zarr stores (CROCO, WW3, turbidity) are published. Keeps the front-end
# free to overlay any product on any other on a shared grid.
LATEST_GRID_SPACING="${LATEST_GRID_SPACING:-0.01}"
LATEST_RAW_DIR="${LATEST_RAW_DIR:-${REPO_DIR}/data/latest/raw/${DOMAIN}}"
LATEST_PP_DIR="${LATEST_PP_DIR:-${REPO_DIR}/data/latest/postprocess/${DOMAIN}}"
LATEST_WEB_DIR="${LATEST_WEB_DIR:-${REPO_DIR}/data/latest/web/${DOMAIN}}"
