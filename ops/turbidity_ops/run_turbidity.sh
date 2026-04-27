#!/bin/bash
# Run the offline 3D turbidity model operationally, using the output of the
# CROCO and WW3 forecast runs for this RUN_DATE as input. If a previous
# turbidity run contains a C_3d restart snapshot whose restart_time exactly
# matches the first time of the current CROCO avg file, the model is
# initialised from that snapshot; otherwise it starts from C_bg (cold start).
set -e
source "$(dirname "$0")/../my_env.sh"

SCRATCH_DIR="${TURB_OPS_DIR}/scratch"
OUTPUT_DIR="${TURB_OPS_DIR}/output"

# --- Required inputs from the CROCO and WW3 operational runs ---
CROCO_FILE="${OPS_DIR}/${RUN_NAME}/output/croco_avg.nc"
WW3_FILE="${WW3_OPS_DIR}/output/ww3_ounf.nc"
GRD_FILE="${CONFIG_DIR}/GRID/croco_grd.nc"

echo "=== Run Turbidity ==="
echo "  RUN_DATE:     ${RUN_DATE}"
echo "  TURB_RUN:     ${TURB_RUN_NAME}"
echo "  CROCO_FILE:   ${CROCO_FILE}"
echo "  WW3_FILE:     ${WW3_FILE}"
echo "  GRD_FILE:     ${GRD_FILE}"
echo "  OUTPUT_DIR:   ${OUTPUT_DIR}"
echo "  TURB_RST_HOURS: ${TURB_RST_HOURS}"
echo "====================="

for f in "${CROCO_FILE}" "${WW3_FILE}" "${GRD_FILE}"; do
  if [ ! -f "${f}" ]; then
    echo "Error: required input not found: ${f}"
    exit 1
  fi
done

mkdir -p "${SCRATCH_DIR}" "${OUTPUT_DIR}"

# --- a) Determine the first time in the current CROCO avg file ---
# The turbidity model steps on the CROCO avg time axis (WW3 is interpolated
# onto it), so the turbidity model's "t=0" is the first CROCO avg record,
# NOT the nominal CROCO run start (RUN_DATE). For a 1h avg window this is
# RUN_DATE + NH_AVG/2. Because every operational cycle uses the same avg
# stride and absolute time grid, the first avg time of this cycle always
# coincides exactly with one of the previous cycle's avg times, so matching
# on this time gives a perfect restart alignment. Use get_var via the conda
# env so calendar/Yorig handling is consistent with how the model itself
# reads times.
TARGET_TIME=$(conda run -n "${TURB_ENV}" python -c "
import sys, os, numpy as np
# get_var prints progress to stdout; redirect to stderr so the caller
# only captures the timestamp on stdout.
_stdout_fd = os.dup(1); os.dup2(2, 1)
from crocotools_py.postprocess import get_var
ds = get_var('${CROCO_FILE}', 'AKs',
             grdname='${GRD_FILE}', Yorig=${YORIG})
sys.stdout.flush(); os.dup2(_stdout_fd, 1); os.close(_stdout_fd)
t = np.datetime64(ds['time'].values[0], 's')
print(str(t))
")
echo "Target ini time (first CROCO avg time): ${TARGET_TIME}"

# --- b) Restart fallback logic ---
# Search back up to FDAYS worth of 6-hour steps for a previous turbidity
# run whose restart_time array contains TARGET_TIME. Max lookback matches
# the CROCO/WW3 restart search: FDAYS is the physical limit because the
# previous run's forecast only extends FDAYS ahead of its RUN_DATE.
MAX_RST_STEPS=$(awk "BEGIN {print int(${FDAYS} * 24 / 6)}")
RUN_EPOCH=$(date -u -d "${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00" +%s)

INI_FILE=""
for i in $(seq 1 ${MAX_RST_STEPS}); do
  prev_epoch=$((RUN_EPOCH - i * 6 * 3600))
  prev_date=$(date -u -d "@${prev_epoch}" +"%Y%m%d_%H")
  prev_out="${REPO_DIR}/data/${prev_date}/turbidity_ops/${DOMAIN}/${TURB_MODEL}/${TURB_RUN_NAME}/output/${TURB_OUT_FILE}"
  if [ ! -f "${prev_out}" ]; then
    continue
  fi
  # Check whether TARGET_TIME is present in this file's restart_time array.
  MATCH=$(conda run -n "${TURB_ENV}" python -c "
import xarray as xr, numpy as np, sys
ds = xr.open_dataset('${prev_out}')
if 'restart_time' not in ds.variables:
    sys.exit(0)
rst = ds['restart_time'].values.astype('datetime64[ns]')
target = np.datetime64('${TARGET_TIME}')
dts = np.abs(rst - target).astype('timedelta64[s]').astype(np.int64)
idx = int(np.argmin(dts))
if dts[idx] <= 60:
    # Print the 0-based index (what xarray .isel expects)
    print(idx)
" 2>/dev/null || true)
  if [ -n "${MATCH}" ]; then
    echo "Found restart: ${prev_out}"
    echo "  restart_time index (0-based) = ${MATCH} matches ${TARGET_TIME}"
    INI_FILE="${prev_out}"
    break
  fi
done

if [ -z "${INI_FILE}" ]; then
  echo "No matching turbidity restart found -- cold start from C_bg"
  INI_ARGS=""
else
  # Pass --ini_time so the Python side repeats the lookup and prints which
  # 0-based index it used; this guards against any zero/one indexing drift.
  INI_ARGS="--ini_file ${INI_FILE} --ini_time ${TARGET_TIME}"
fi

# --- c) Run the model ---
cd "${SCRATCH_DIR}"
conda run -n "${TURB_ENV}" python "${TURB_CODE_DIR}/offline_3d_model.py" run \
    --croco_file "${CROCO_FILE}" \
    --ww3_file "${WW3_FILE}" \
    --grd_file "${GRD_FILE}" \
    --yorig ${YORIG} \
    --out_dir "${OUTPUT_DIR}" \
    --out_file "${TURB_OUT_FILE}" \
    --ws_fine ${WS_FINE} \
    --ws_coarse ${WS_COARSE} \
    --M_fine ${M_FINE} \
    --M_coarse ${M_COARSE} \
    --tau_cr_fine ${TAU_CR_FINE} \
    --tau_cr_coarse ${TAU_CR_COARSE} \
    --C_bg ${C_BG} \
    --restart_interval_hours ${TURB_RST_HOURS} \
    ${INI_ARGS}

echo "Done. Output archived to ${OUTPUT_DIR}"
