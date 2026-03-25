#!/bin/bash
# Run CROCO forecast: set up scratch dir, copy inputs, generate croco.in, run model, archive output.
set -e
source "$(dirname "$0")/../my_env.sh"

SCRATCH_DIR="${OPS_DIR}/${RUN_NAME}/scratch"
OUTPUT_DIR="${OPS_DIR}/${RUN_NAME}/output"

echo "=== Run CROCO ==="
echo "  RUN_DATE:    ${RUN_DATE}"
echo "  RUN_NAME:    ${RUN_NAME}"
echo "  SCRATCH_DIR: ${SCRATCH_DIR}"
echo "  OUTPUT_DIR:  ${OUTPUT_DIR}"
echo "==================="

# --- a) Create run directories ---
mkdir -p "${SCRATCH_DIR}" "${OUTPUT_DIR}"

# --- b) Copy ini file (restart fallback logic) ---
# Search back up to 20 x 6-hour steps for a previous croco_rst.nc
RST_STEP=1
INI_FILE=""
RUN_EPOCH=$(date -u -d "${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00" +%s)
for i in $(seq 1 20); do
  # Calculate previous run date (i * 6 hours back)
  prev_epoch=$((RUN_EPOCH - i * 6 * 3600))
  prev_date=$(date -u -d "@${prev_epoch}" +"%Y%m%d_%H")
  prev_rst="${REPO_DIR}/data/croco_ops/${prev_date}/${DOMAIN}/${MODEL}/${RUN_NAME}/output/croco_rst.nc"
  if [ -f "${prev_rst}" ]; then
    echo "Found restart file: ${prev_rst} (${i} x 6h back)"
    cp "${prev_rst}" "${SCRATCH_DIR}/croco_ini.nc"
    # RST_STEP = record in the restart file corresponding to RUN_DATE
    # Records are written every 6h, and the previous run started i * 6h ago,
    # so record i corresponds to the current RUN_DATE
    RST_STEP=${i}
    INI_FILE="restart"
    break
  fi
done

if [ -z "${INI_FILE}" ]; then
  echo "No restart file found, using MERCATOR ini"
  cp "${OPS_DIR}/${OGCM}/croco_ini_${OGCM}_${RUN_DATE}.nc" "${SCRATCH_DIR}/croco_ini.nc"
  RST_STEP=1
fi

# --- c) Copy other input files to scratch ---
cp "${OPS_DIR}/${OGCM}/croco_bry_${OGCM}_${RUN_DATE}.nc" "${SCRATCH_DIR}/croco_bry.nc"
cp "${OPS_DIR}/${TIDE_FRC}/croco_frc_${TIDE_FRC}_${RUN_DATE}.nc" "${SCRATCH_DIR}/croco_frc.nc"
cp "${CONFIG_DIR}/GRID/croco_grd.nc" "${SCRATCH_DIR}/croco_grd.nc"
cp "${CONFIG_DIR}/${COMP}/croco" "${SCRATCH_DIR}/croco"

# --- d) Generate croco.in from template ---
source "${CONFIG_DIR}/${INP}/myenv_in.sh"

NDAYS=$(awk "BEGIN {print ${HDAYS} + ${FDAYS}}")
NUMTIMES=$(awk "BEGIN {print int(${NDAYS} * 24 * 3600 / ${DT})}")
NUMAVG=$((NH_AVG * 3600 / DT))
NUMHIS=$((NH_HIS * 3600 / DT))
NUMAVGSURF=$((NH_AVGSURF * 3600 / DT))
NUMHISSURF=$((NH_HISSURF * 3600 / DT))
NUMRST=$((NH_RST * 3600 / DT))

# DATA_DIR in the template points to where the reformatted GFS bulk files are
DATA_DIR_BLK="${DOWNLOAD_DIR}/${BLK}/for_croco/"

# Order matters: NUMHISSURF/NUMAVGSURF before NUMHIS/NUMAVG to avoid partial matches
sed -e 's|DTNUM|'"${DT}"'|' \
    -e 's|DTFAST|'"${DTFAST}"'|' \
    -e 's|NUMTIMES|'"${NUMTIMES}"'|g' \
    -e 's|NUMHISSURF|'"${NUMHISSURF}"'|g' \
    -e 's|NUMAVGSURF|'"${NUMAVGSURF}"'|g' \
    -e 's|NUMHIS|'"${NUMHIS}"'|g' \
    -e 's|NUMAVG|'"${NUMAVG}"'|g' \
    -e 's|RST_STEP|'"${RST_STEP}"'|' \
    -e 's|NUMRST|'"${NUMRST}"'|' \
    -e 's|DATA_DIR|'"${DATA_DIR_BLK}"'|' \
    < "${CONFIG_DIR}/${INP}/croco_fcst.in" \
    > "${SCRATCH_DIR}/croco.in"

echo "Generated croco.in with:"
echo "  DT=${DT}, DTFAST=${DTFAST}, NUMTIMES=${NUMTIMES}"
echo "  NUMHIS=${NUMHIS}, NUMAVG=${NUMAVG}"
echo "  NUMHISSURF=${NUMHISSURF}, NUMAVGSURF=${NUMAVGSURF}"
echo "  NUMRST=${NUMRST}, RST_STEP=${RST_STEP}"

# --- e) Run CROCO ---
cd "${SCRATCH_DIR}"

echo "Running CROCO with ${CROCO_MPI_NUM_PROCS} processes..."
date
mpirun -np ${CROCO_MPI_NUM_PROCS} ./croco croco.in > croco.out
date

# Test if the run finished properly
echo "Checking croco.out..."
status=$(tail -2 croco.out | grep -c DONE || true)
if [ "${status}" -eq 1 ]; then
  echo "CROCO run completed successfully"
else
  echo "Warning: run not finished properly"
  tail -20 croco.out
  exit 1
fi

# --- f) Archive output ---
#mv -f croco_his.nc "${OUTPUT_DIR}/croco_his.nc"
mv -f croco_rst.nc "${OUTPUT_DIR}/croco_rst.nc"
mv -f croco_avg.nc "${OUTPUT_DIR}/croco_avg.nc"
#mv -f croco_his_surf.nc "${OUTPUT_DIR}/croco_his_surf.nc"
mv -f croco_avg_surf.nc "${OUTPUT_DIR}/croco_avg_surf.nc"

echo "Done. Output archived to ${OUTPUT_DIR}"
