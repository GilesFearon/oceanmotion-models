#!/bin/bash
# Extract time-series at observation point and plot diagnostics.
set -e
source "$(dirname "$0")/my_env.sh"

TURB_FILE="${TURB_OUT_DIR}/${TURB_OUT_FILE}"

echo "=== Compare 3D Turbidity Model ==="
echo "  TURB_FILE: ${TURB_FILE}"
echo "  GRD_FILE:  ${GRD_FILE}"
echo "  OBS:       (${OBS_LON}, ${OBS_LAT})"
echo "  OBS_FILE:  ${OBS_FILE}"
echo "  OUT_DIR:   ${TURB_OUT_DIR}"
echo "===================================="

conda run -n ${TURB_ENV} python "${TURB_CODE_DIR}/offline_3d_model.py" compare \
    --turb_file "${TURB_FILE}" \
    --grd_file "${GRD_FILE}" \
    --obs_lon ${OBS_LON} \
    --obs_lat ${OBS_LAT} \
    --out_dir "${TURB_OUT_DIR}" \
    --obs_file "${OBS_FILE}"

echo "Done. Diagnostics saved to ${TURB_OUT_DIR}"
