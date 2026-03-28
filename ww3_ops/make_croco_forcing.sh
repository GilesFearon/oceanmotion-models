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

conda run -n ${CROCO_ENV} python "${CROCO_REPO}/cli.py" croco_srf_2_ww3 \
    --fname "${CROCO_OUTPUT}/croco_avg_surf.nc" \
    --grdname "${CONFIG_DIR}/GRID/croco_grd.nc" \
    --dir_out "${WW3_FORCING_DIR}" \
    --Yorig ${YORIG}

echo "Done. WW3 forcing files saved to ${WW3_FORCING_DIR}"
