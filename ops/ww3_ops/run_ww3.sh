#!/bin/bash
# Run WW3 forecast: set up scratch dir, preprocess forcing, run model, archive output.
set -e
source "$(dirname "$0")/../my_env.sh"

SCRATCH_DIR="${WW3_OPS_DIR}/scratch"
OUTPUT_DIR="${WW3_OPS_DIR}/output"

echo "=== Run WW3 ==="
echo "  RUN_DATE:    ${RUN_DATE}"
echo "  HDAYS:       ${HDAYS}"
echo "  FDAYS:       ${FDAYS}"
echo "  SCRATCH_DIR: ${SCRATCH_DIR}"
echo "  OUTPUT_DIR:  ${OUTPUT_DIR}"
echo "================="

# --- a) Create run directories ---
mkdir -p "${SCRATCH_DIR}" "${OUTPUT_DIR}"
cd "${SCRATCH_DIR}"

# --- b) Calculate date strings for WW3 namelists ---
# WW3 expects 'YYYYMMDD HHMMSS' format
RUN_FMT="${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00"
# Note: "date -d" interprets +N/-N as timezone offsets, so use "N days ago" / "N days" syntax
YMDHMS_START=$(date -u -d "${RUN_FMT} ${HDAYS} days ago" +"%Y%m%d %H0000")
YMDHMS_STOP=$(date -u -d "${RUN_FMT} ${FDAYS} days" +"%Y%m%d %H0000")
# Last field output time: 1 hour before stop
YMDHMS_LASTFIELD=$(date -u -d "${RUN_FMT} ${FDAYS} days 1 hour ago" +"%Y%m%d %H0000")

echo "  YMDHMS_START:     ${YMDHMS_START}"
echo "  YMDHMS_STOP:      ${YMDHMS_STOP}"
echo "  YMDHMS_LASTFIELD: ${YMDHMS_LASTFIELD}"

# --- c) Grid preprocessing ---
echo "Preprocessing grid..."
cp "${WW3_EXE_DIR}/ww3_grid" .
cp "${WW3_CONFIG_DIR}/GRID"/*.dat .
cp "${WW3_CONFIG_DIR}/ww3_grid.nml" .
cp "${WW3_CONFIG_DIR}/namelists_config.nml" .
./ww3_grid | tee ww3_grid.out

# --- d) Boundary condition preprocessing ---
echo "Preprocessing boundary conditions..."
cp "${WW3_EXE_DIR}/ww3_bounc" .

# Create spec.list with absolute paths from the boundary spec files
BRY_SPEC_DIR="${WW3_OPS_DIR}/SPEC_CMEMS"
if [ ! -d "${BRY_SPEC_DIR}" ] || [ -z "$(ls ${BRY_SPEC_DIR}/spec.list 2>/dev/null)" ]; then
  echo "Error: Boundary spec files not found in ${BRY_SPEC_DIR}"
  echo "Run ops/ww3_ops/make_bry.sh first"
  exit 1
fi
sed 's|^|'"${BRY_SPEC_DIR}"'/|' "${BRY_SPEC_DIR}/spec.list" > spec.list

sed -e 's|YMDHMS_START|'"${YMDHMS_START}"'|g' \
    -e 's|YMDHMS_STOP|'"${YMDHMS_STOP}"'|g' \
    -e 's|YMDHMS_LASTFIELD|'"${YMDHMS_LASTFIELD}"'|g' \
    < "${WW3_CONFIG_DIR}/ww3_shel.nml" > ww3_shel.nml

cp ww3_shel.nml ww3_bounc_shel.nml
cp "${WW3_CONFIG_DIR}/ww3_bounc.nml" ww3_bounc.nml
./ww3_bounc | tee ww3_bounc.out

# --- e) Wind forcing (GFS) ---
echo "Preprocessing wind forcing..."
cp "${WW3_EXE_DIR}/ww3_prnc" .

GFS_DIR="${DOWNLOAD_DIR}/${BLK}/for_croco"
UFILE="${GFS_DIR}/U-component_of_wind_Y9999M1.nc"
VFILE="${GFS_DIR}/V-component_of_wind_Y9999M1.nc"

if [ ! -f "${UFILE}" ] || [ ! -f "${VFILE}" ]; then
  echo "Error: GFS wind files not found in ${GFS_DIR}"
  exit 1
fi

rm -f wind*
echo "Combining U and V wind components into wind.nc"
cp "${UFILE}" wind.nc
ncks -A "${VFILE}" wind.nc
echo "Fixing time attributes for ww3_prnc (ISO8601 required)"
ncatted -O -a units,time,o,c,"days since ${YORIG}-01-01 00:00:00" \
        -a calendar,time,c,c,"standard" wind.nc

cp "${WW3_CONFIG_DIR}/ww3_prnc_wind.nml" ww3_prnc.nml
./ww3_prnc | tee ww3_prnc_wind.out

# --- f) Current forcing (from CROCO via croco_srf_2_ww3) ---
echo "Preprocessing current forcing..."
CROCO_WW3_DIR="${WW3_OPS_DIR}/CROCO_WW3"
CURRENT_FILE=$(ls "${CROCO_WW3_DIR}"/*_current.nc 2>/dev/null | head -1)
if [ -z "${CURRENT_FILE}" ]; then
  echo "Error: CROCO WW3 current file not found in ${CROCO_WW3_DIR}"
  echo "Run ops/ww3_ops/make_croco_forcing.sh first"
  exit 1
fi
cp "${CURRENT_FILE}" current.nc

cp "${WW3_CONFIG_DIR}/ww3_prnc_current.nml" ww3_prnc.nml
./ww3_prnc | tee ww3_prnc_current.out

# --- g) Water level forcing (from CROCO via croco_srf_2_ww3) ---
echo "Preprocessing water level forcing..."
LEVEL_FILE=$(ls "${CROCO_WW3_DIR}"/*_level.nc 2>/dev/null | head -1)
if [ -z "${LEVEL_FILE}" ]; then
  echo "Error: CROCO WW3 level file not found in ${CROCO_WW3_DIR}"
  echo "Run ops/ww3_ops/make_croco_forcing.sh first"
  exit 1
fi
cp "${LEVEL_FILE}" level.nc

cp "${WW3_CONFIG_DIR}/ww3_prnc_level.nml" ww3_prnc.nml
./ww3_prnc | tee ww3_prnc_level.out

# --- h) Restart fallback logic ---
echo "Searching for restart file..."
RUN_EPOCH=$(date -u -d "${RUN_FMT}" +%s)
RST_FOUND=0
for i in $(seq 1 20); do
  prev_epoch=$((RUN_EPOCH - i * 6 * 3600))
  prev_date=$(date -u -d "@${prev_epoch}" +"%Y%m%d_%H")
  prev_output="${REPO_DIR}/data/ww3_ops/${prev_date}/${DOMAIN}/${WW3_MODEL}/output"
  if [ -d "${prev_output}" ]; then
    rst_num=$(printf '%03d' ${i})
    rst_file="${prev_output}/restart${rst_num}.ww3"
    if [ -f "${rst_file}" ]; then
      echo "Found restart: ${rst_file} (${i} x 6h back)"
      cp "${rst_file}" restart.ww3
      RST_FOUND=1
      break
    fi
  fi
done
if [ ${RST_FOUND} -eq 0 ]; then
  echo "No restart file found, starting from cold"
fi

# --- i) Run WW3 model ---
echo "Copying WW3 executable..."
cp "${WW3_EXE_DIR}/ww3_shel" .

echo "Running WW3 with ${WW3_MPI_NUM_PROCS} processes..."
date
mpirun -np ${WW3_MPI_NUM_PROCS} ./ww3_shel >& ww3_shel.out || {
  echo "Warning: WW3 run may not have finished properly"
  tail -20 ww3_shel.out
  exit 1
}
date
echo "WW3 run completed"

# --- j) Post-process: create netCDF output ---
echo "Post-processing output to netCDF..."
cp "${WW3_EXE_DIR}/ww3_ounf" .
sed -e 's|YMDHMS_START|'"${YMDHMS_START}"'|g' \
    < "${WW3_CONFIG_DIR}/ww3_ounf.nml" > ww3_ounf.nml
./ww3_ounf | tee ww3_ounf.out

# --- k) Archive output ---
echo "Archiving output..."
# Move netCDF output (TIMESPLIT=0 produces a single file named ww3.YYYY.nc)
# Rename to generic ww3_ounf.nc to avoid clashes with other post-processing
OUNF_FILE="ww3.${RUN_DATE:0:4}.nc"
if [ ! -f "${OUNF_FILE}" ]; then
  echo "Error: expected ww3_ounf output ${OUNF_FILE} not found"
  exit 1
fi
mv -f "${OUNF_FILE}" "${OUTPUT_DIR}/ww3_ounf.nc"

# Archive all restart files
for f in restart*.ww3; do
  [ -f "$f" ] && mv -f "$f" "${OUTPUT_DIR}/"
done

echo "Done. Output archived to ${OUTPUT_DIR}"
