#!/bin/bash
# Standalone environment for the gulf_01 turbidity hindcast calibration run.
# This file intentionally does NOT source ops/my_env.sh — it is a self-contained
# hindcast test. Operational wiring will be added separately when needed.
#
# Usage:
#   source configs/gulf_01/turbidity/hindcast/calib_01/my_env.sh

# --- Repo root (four levels up from this file) ---
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)}"

# --- Location of the generic turbidity Python code ---
TURB_CODE_DIR="${TURB_CODE_DIR:-${REPO_DIR}/turbidity}"

# --- Calibration run directory (this file's directory) ---
CALIB_DIR="${CALIB_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

# --- Yorig for the CROCO hindcast files ---
YORIG="${YORIG:-1993}"

# --- Input files (gulf_01 hindcast, Jan 2022) ---
CROCO_FILE="${CROCO_FILE:-${REPO_DIR}/configs/gulf_01/croco_v1.3.1/hindcast/C04_I02_GLORYS_ERA5/output/croco_avg_Y2022M01.nc}"
WW3_FILE="${WW3_FILE:-${REPO_DIR}/configs/gulf_01/ww3_v6.07.1/hindcast/RUN_02/output/ww3.202201.nc}"
GRD_FILE="${GRD_FILE:-${REPO_DIR}/configs/gulf_01/croco_v1.3.1/hindcast/GRID/croco_grd.nc}"

# --- Output (stays inside this calib directory) ---
TURB_OUT_DIR="${TURB_OUT_DIR:-${CALIB_DIR}/output}"
TURB_OUT_FILE="${TURB_OUT_FILE:-turbidity_3d_Y2022M01.nc}"

# --- Observation point for diagnostics ---
OBS_LON="${OBS_LON:-54.072347}"
OBS_LAT="${OBS_LAT:-24.368937}"
OBS_FILE="${OBS_FILE:-/home/gfearon/projects/ocean-motion/data/ntu_obs/NTU_obs.csv}"

# --- Two-class sediment parameters ---
# Settling velocity (m/s): fine, coarse
WS_FINE="${WS_FINE:-1e-4}"
WS_COARSE="${WS_COARSE:-1e-3}"

# Erosion rate (NTU m/s): fine, coarse
M_FINE="${M_FINE:-0.0003}"
M_COARSE="${M_COARSE:-0.003}"

# Critical bed shear stress (N/m^2): fine, coarse
TAU_CR_FINE="${TAU_CR_FINE:-0.1}"
TAU_CR_COARSE="${TAU_CR_COARSE:-0.25}"

# Background concentration (NTU)
C_BG="${C_BG:-3.0}"

# --- Conda environment ---
TURB_ENV="${TURB_ENV:-somisana_croco}"
