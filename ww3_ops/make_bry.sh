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

conda run -n ${WW3_ENV} python "${WW3_REPO}/cli.py" make_bry_cmems_fcst \
    --input_file "${DOWNLOAD_DIR}/CMEMS_WAV/CMEMS_WAV_${RUN_DATE}.nc" \
    --lon_file "${WW3_CONFIG_DIR}/GRID/lon.dat" \
    --lat_file "${WW3_CONFIG_DIR}/GRID/lat.dat" \
    --mask_file "${WW3_CONFIG_DIR}/GRID/mask.dat" \
    --output_dir "${OUTPUT_DIR}"

echo "Done. Boundary spec files saved to ${OUTPUT_DIR}"
