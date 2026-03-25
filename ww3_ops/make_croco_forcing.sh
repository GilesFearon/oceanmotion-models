#!/bin/bash
# Convert CROCO forecast surface output to WW3-compatible current and level files.
# Uses croco_srf_2_ww3 from the somisana-croco CLI to handle grid interpolation
# and variable/dimension renaming for ww3_prnc ASIS mode.
set -e
source "$(dirname "$0")/../my_env.sh"

CROCO_OUTPUT="${OPS_DIR}/${RUN_NAME}/output"
WW3_FORCING_DIR="${WW3_OPS_DIR}/CROCO_WW3"
mkdir -p "${WW3_FORCING_DIR}"

echo "=== Make WW3 CROCO Forcing ==="
echo "  RUN_DATE:     ${RUN_DATE}"
echo "  CROCO_OUTPUT: ${CROCO_OUTPUT}"
echo "  OUTPUT_DIR:   ${WW3_FORCING_DIR}"
echo "================================"

if [ ! -f "${CROCO_OUTPUT}/croco_avg_surf.nc" ]; then
  echo "Error: CROCO surface output not found: ${CROCO_OUTPUT}/croco_avg_surf.nc"
  echo "Ensure the CROCO forecast has completed for RUN_DATE=${RUN_DATE}"
  exit 1
fi

docker run --user $(id -u):$(id -g) --rm \
  -v "${CROCO_OUTPUT}":/data/croco \
  -v "${CONFIG_DIR}/GRID":/data/grid \
  -v "${WW3_FORCING_DIR}":/output \
  ${CLI_IMAGE} croco_srf_2_ww3 \
    --fname /data/croco/croco_avg_surf.nc \
    --grdname /data/grid/croco_grd.nc \
    --dir_out /output \
    --Yorig ${YORIG}

echo "Done. WW3 forcing files saved to ${WW3_FORCING_DIR}"
