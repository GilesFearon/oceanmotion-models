#!/bin/bash
# Generate WW3 spectral boundary conditions from downloaded CMEMS wave data.
set -e
source "$(dirname "$0")/../my_env.sh"

OUTPUT_DIR="${WW3_OPS_DIR}/SPEC_CMEMS"
mkdir -p "${OUTPUT_DIR}"

echo "=== Make WW3 Boundary Conditions ==="
echo "  RUN_DATE:    ${RUN_DATE}"
echo "  INPUT:       ${DOWNLOAD_DIR}/CMEMS_WAV/CMEMS_WAV_${RUN_DATE}.nc"
echo "  OUTPUT_DIR:  ${OUTPUT_DIR}"
echo "======================================"

docker run --user $(id -u):$(id -g) --rm \
  -v "${DOWNLOAD_DIR}/CMEMS_WAV":/data/cmems \
  -v "${WW3_CONFIG_DIR}/GRID":/data/grid \
  -v "${OUTPUT_DIR}":/output \
  ${WW3_CLI_IMAGE} make_bry_cmems_fcst \
    --input_file /data/cmems/CMEMS_WAV_${RUN_DATE}.nc \
    --lon_file /data/grid/lon.dat \
    --lat_file /data/grid/lat.dat \
    --mask_file /data/grid/mask.dat \
    --output_dir /output

echo "Done. Boundary spec files saved to ${OUTPUT_DIR}"
