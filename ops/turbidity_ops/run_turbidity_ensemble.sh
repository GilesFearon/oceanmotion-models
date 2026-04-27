#!/bin/bash
# Run an 11-member operational turbidity ensemble. Each member uses a
# different multiplicative perturbation on the WW3 bottom orbital velocity
# components (uubr, vubr) — the perturbations are deterministic quantiles
# of a normal distribution centred on 1.0 with sigma = SI, where SI is the
# scatter index (RMSE/mean_obs) of the WW3 Hs hindcast against L3 altimeter
# data computed in:
#   configs/gulf_01/ww3_v6.07.1/hindcast/RUN_02/postprocess/colocated_hs.nc
#   (see plot_scatter_hs.py for the formula)
#
# Because tau_w ~ ubr^2 and ubr scales linearly with Hs, a fractional Hs
# error of SI maps directly to a fractional ubr error of SI.
#
# Member 6 is the median (scale = 1.0) and is the closest analogue to the
# old deterministic forecast. Each member restarts from its own previous
# cycle's output (memNN restarts from memNN), so every member has a
# continuous history — important for timeseries plots that combine recent
# hindcast cycles with the current forecast.
set -e
source "$(dirname "$0")/../my_env.sh"

# --- Hs scatter index (computed once from RUN_02 hindcast validation) ---
# Restricted to the storm-relevant band that drives resuspension (Hs > 1 m):
#   N = 5934 colocations, mean_obs = 1.532 m, bias = -0.200 m,
#   rmse = 0.321 m, SI = rmse / mean_obs = 0.21.
# Rounded to 0.20 and used directly as sigma for the ubr perturbation.
#
# We use the *total* (biased) SI as the spread and centre the ensemble on 1.0
# rather than splitting into bias + scatter. The hindcast was forced with ERA5,
# but the operational system runs on GFS, so the bias number is not a
# calibrated correction for the operational forecast — only a hint that WW3
# may under-predict storm Hs by O(15%). Treating the total error as a single
# bulk uncertainty implicitly absorbs that bias-magnitude uncertainty
# (e.g. ~16% of members sit above ubr_scale = 1.20). Revisit once we have
# enough operational forecasts to compare against altimeters/buoys directly.
SIGMA_UBR="0.20"

# --- Ensemble size ---
N_MEMBERS=11

# --- Precompute member scales once via python (inverse normal CDF quantiles) ---
SCALES_CSV=$(conda run -n "${TURB_ENV}" python -c "
import numpy as np
from scipy.stats import norm
sigma = ${SIGMA_UBR}
n = ${N_MEMBERS}
q = np.linspace(0.05, 0.95, n)
scales = 1.0 + norm.ppf(q) * sigma
print(','.join(f'{s:.6f}' for s in scales))
")
IFS=',' read -ra SCALES <<< "${SCALES_CSV}"

SCRATCH_DIR="${TURB_OPS_DIR}/scratch"
OUTPUT_DIR="${TURB_OPS_DIR}/output"

# --- Required inputs from the CROCO and WW3 operational runs ---
CROCO_FILE="${OPS_DIR}/${RUN_NAME}/output/croco_avg.nc"
WW3_FILE="${WW3_OPS_DIR}/output/ww3_ounf.nc"
GRD_FILE="${CONFIG_DIR}/GRID/croco_grd.nc"

# Derive member output file names from TURB_OUT_FILE (e.g. turbidity_3d.nc -> turbidity_3d_mem01.nc)
TURB_OUT_BASE="${TURB_OUT_FILE%.nc}"

echo "=== Run Turbidity Ensemble ==="
echo "  RUN_DATE:       ${RUN_DATE}"
echo "  TURB_RUN:       ${TURB_RUN_NAME}"
echo "  N_MEMBERS:      ${N_MEMBERS}"
echo "  SIGMA_UBR:      ${SIGMA_UBR}"
echo "  SCALES:         ${SCALES_CSV}"
echo "  CROCO_FILE:     ${CROCO_FILE}"
echo "  WW3_FILE:       ${WW3_FILE}"
echo "  GRD_FILE:       ${GRD_FILE}"
echo "  OUTPUT_DIR:     ${OUTPUT_DIR}"
echo "  TURB_RST_HOURS: ${TURB_RST_HOURS}"
echo "==============================="

for f in "${CROCO_FILE}" "${WW3_FILE}" "${GRD_FILE}"; do
  if [ ! -f "${f}" ]; then
    echo "Error: required input not found: ${f}"
    exit 1
  fi
done

mkdir -p "${SCRATCH_DIR}" "${OUTPUT_DIR}"

# --- a) Determine the first time in the current CROCO avg file ---
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

# --- b) Per-member restart search ---
# Each member restarts from its own previous output (memNN -> memNN) so each
# member carries a continuous history across cycles.
MAX_RST_STEPS=$(awk "BEGIN {print int(${FDAYS} * 24 / 6)}")
RUN_EPOCH=$(date -u -d "${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00" +%s)

# find_restart <member_filename>
# Prints the path to the matching previous output file, or empty if none found.
find_restart() {
  local rst_name="$1"
  local i prev_epoch prev_date prev_out match
  for i in $(seq 1 ${MAX_RST_STEPS}); do
    prev_epoch=$((RUN_EPOCH - i * 6 * 3600))
    prev_date=$(date -u -d "@${prev_epoch}" +"%Y%m%d_%H")
    prev_out="${REPO_DIR}/data/${prev_date}/turbidity_ops/${DOMAIN}/${TURB_MODEL}/${TURB_RUN_NAME}/output/${rst_name}"
    if [ ! -f "${prev_out}" ]; then
      continue
    fi
    match=$(conda run -n "${TURB_ENV}" python -c "
import xarray as xr, numpy as np, sys
ds = xr.open_dataset('${prev_out}')
if 'restart_time' not in ds.variables:
    sys.exit(0)
rst = ds['restart_time'].values.astype('datetime64[ns]')
target = np.datetime64('${TARGET_TIME}')
dts = np.abs(rst - target).astype('timedelta64[s]').astype(np.int64)
idx = int(np.argmin(dts))
if dts[idx] <= 60:
    print(idx)
" 2>/dev/null || true)
    if [ -n "${match}" ]; then
      echo "${prev_out}"
      return 0
    fi
  done
  return 0
}

# --- c) Launch all members in parallel ---
cd "${SCRATCH_DIR}"

declare -a PIDS
declare -a MEM_LOGS
declare -a MEM_TAGS

for m in $(seq 1 ${N_MEMBERS}); do
  MEM_TAG=$(printf "mem%02d" "${m}")
  SCALE="${SCALES[$((m - 1))]}"
  MEM_OUT="${TURB_OUT_BASE}_${MEM_TAG}.nc"
  MEM_LOG="${SCRATCH_DIR}/${MEM_TAG}.log"

  # Each member restarts from its own previous output file (memNN -> memNN).
  INI_FILE=$(find_restart "${MEM_OUT}")
  if [ -z "${INI_FILE}" ]; then
    echo "  ${MEM_TAG}: no restart found -- cold start from C_bg"
    INI_ARGS=""
  else
    echo "  ${MEM_TAG}: restart from ${INI_FILE}"
    INI_ARGS="--ini_file ${INI_FILE} --ini_time ${TARGET_TIME}"
  fi

  echo "Launching ${MEM_TAG}: ubr_scale=${SCALE} -> ${MEM_OUT}"
  (
    conda run -n "${TURB_ENV}" python "${TURB_CODE_DIR}/offline_3d_model.py" run \
        --croco_file "${CROCO_FILE}" \
        --ww3_file "${WW3_FILE}" \
        --grd_file "${GRD_FILE}" \
        --yorig ${YORIG} \
        --out_dir "${OUTPUT_DIR}" \
        --out_file "${MEM_OUT}" \
        --ws_fine ${WS_FINE} \
        --ws_coarse ${WS_COARSE} \
        --M_fine ${M_FINE} \
        --M_coarse ${M_COARSE} \
        --tau_cr_fine ${TAU_CR_FINE} \
        --tau_cr_coarse ${TAU_CR_COARSE} \
        --C_bg ${C_BG} \
        --restart_interval_hours ${TURB_RST_HOURS} \
        --ubr_scale ${SCALE} \
        ${INI_ARGS}
  ) > "${MEM_LOG}" 2>&1 &
  PIDS+=($!)
  MEM_LOGS+=("${MEM_LOG}")
  MEM_TAGS+=("${MEM_TAG}")
done

# --- d) Wait and check exit codes ---
FAIL=0
for i in "${!PIDS[@]}"; do
  if wait "${PIDS[$i]}"; then
    echo "  ${MEM_TAGS[$i]} OK"
  else
    echo "  ${MEM_TAGS[$i]} FAILED -- log: ${MEM_LOGS[$i]}"
    tail -n 30 "${MEM_LOGS[$i]}" || true
    FAIL=1
  fi
done

if [ "${FAIL}" -ne 0 ]; then
  echo "One or more ensemble members failed. Aborting."
  exit 1
fi

echo "Done. ${N_MEMBERS} members archived to ${OUTPUT_DIR}"
