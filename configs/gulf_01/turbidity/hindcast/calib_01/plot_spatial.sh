#!/bin/bash
# Three spatial snapshots of surface turbidity.
# Default: auto-selects calmest time and two biggest events from the mass series.
# Override with e.g.:
#   TURB_TIMES="2022-01-03T12 2022-01-05T18 2022-01-22T00" bash plot_spatial.sh
set -e
source "$(dirname "$0")/my_env.sh"

TURB_FILE="${TURB_OUT_DIR}/${TURB_OUT_FILE}"

echo "=== Spatial Surface Turbidity ==="
echo "  TURB_FILE: ${TURB_FILE}"
echo "  GRD_FILE:  ${GRD_FILE}"
echo "  OUT_DIR:   ${TURB_OUT_DIR}"
if [ -n "${TURB_TIMES:-}" ]; then
    echo "  TIMES:     ${TURB_TIMES}"
    TIMES_ARG="--times ${TURB_TIMES}"
else
    echo "  TIMES:     auto (calm + two peaks)"
    TIMES_ARG=""
fi
echo "================================="

conda run -n ${TURB_ENV} python "${TURB_CODE_DIR}/offline_3d_model.py" spatial \
    --turb_file "${TURB_FILE}" \
    --grd_file "${GRD_FILE}" \
    --out_dir "${TURB_OUT_DIR}" \
    --obs_lon ${OBS_LON} \
    --obs_lat ${OBS_LAT} \
    ${TIMES_ARG}

echo "Done."
