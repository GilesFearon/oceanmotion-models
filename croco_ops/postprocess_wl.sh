#!/bin/bash
# Postprocess water level forecasts: extract CROCO + MERCATOR at observation locations,
# compute tidal prediction, non-tidal residuals, and mixture-distribution confidence intervals.
set -e
source "$(dirname "$0")/../my_env.sh"

POSTPROCESS_DIR="${OPS_DIR}/${RUN_NAME}/postprocess"

echo "=== Postprocess Water Levels ==="
echo "  RUN_DATE:       ${RUN_DATE}"
echo "  RUN_NAME:       ${RUN_NAME}"
echo "  CROCO OUTPUT:   ${OPS_DIR}/${RUN_NAME}/output"
echo "  MERCATOR:       ${DOWNLOAD_DIR}/MERCATOR_hourly"
echo "  OUTPUT:         ${POSTPROCESS_DIR}"
echo "=================================="

mkdir -p "${POSTPROCESS_DIR}"

conda run -n ${CROCO_ENV} python "$(dirname "$0")/postprocess_wl.py" \
    --run_date "${RUN_DATE}" \
    --locations_file "${REPO_DIR}/configs/${DOMAIN}/locations.yaml" \
    --croco_file "${OPS_DIR}/${RUN_NAME}/output/croco_avg_surf.nc" \
    --croco_grd "${CONFIG_DIR}/GRID/croco_grd.nc" \
    --mercator_file "${DOWNLOAD_DIR}/MERCATOR_hourly/MERCATOR_hourly_${RUN_DATE}.nc" \
    --obs_coef_dir "${OBS_COEF_DIR}" \
    --croco_coef_dir "${TIDAL_ANALYSIS_DIR}" \
    --croco_stats_file "${TIDAL_ANALYSIS_DIR}/croco_residual_stats.nc" \
    --mercator_stats_file "${MERCATOR_ANALYSIS_DIR}/mercator_residual_stats.nc" \
    --mdt_file "${MERCATOR_ANALYSIS_DIR}/clim.nc" \
    --output_dir "${POSTPROCESS_DIR}" \
    --yorig ${YORIG}

echo "Done. Water level forecasts saved to ${POSTPROCESS_DIR}"
