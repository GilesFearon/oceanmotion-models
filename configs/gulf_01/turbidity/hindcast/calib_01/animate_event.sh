#!/bin/bash
# Animate surface turbidity over the highest-mass event.
#
# Default: auto-picks a 3-day window centred on the mass-series maximum.
# Override the window via environment variables:
#   TURB_EVENT_START=2022-01-20T00 TURB_EVENT_END=2022-01-23T00 bash animate_event.sh
#
# Other overrides (all optional):
#   TURB_VMAX=60        colour scale upper limit (NTU)
#   TURB_SKIP_TIME=2    animate every Nth frame (default 1)
#   TURB_OUT_DIR=...    output directory (default from my_env.sh)
set -e
source "$(dirname "$0")/my_env.sh"

TURB_FILE="${TURB_OUT_DIR}/${TURB_OUT_FILE}"

echo "=== Turbidity Event Animation ==="
echo "  TURB_FILE:  ${TURB_FILE}"
echo "  GRD_FILE:   ${GRD_FILE}"
echo "  OUT_DIR:    ${TURB_OUT_DIR}"
echo "  OBS:        lon=${OBS_LON}  lat=${OBS_LAT}"

if [ -n "${TURB_EVENT_START:-}" ]; then
    echo "  EVENT_START: ${TURB_EVENT_START}"
    START_ARG="--event_start ${TURB_EVENT_START}"
else
    echo "  EVENT_START: auto (centred on mass peak)"
    START_ARG=""
fi

if [ -n "${TURB_EVENT_END:-}" ]; then
    echo "  EVENT_END:   ${TURB_EVENT_END}"
    END_ARG="--event_end ${TURB_EVENT_END}"
else
    END_ARG=""
fi

if [ -n "${TURB_VMAX:-}" ]; then
    VMAX_ARG="--vmax ${TURB_VMAX}"
else
    VMAX_ARG=""
fi

SKIP_TIME="${TURB_SKIP_TIME:-1}"
echo "  SKIP_TIME:  ${SKIP_TIME}"
echo "================================="

conda run -n ${TURB_ENV} python "$(dirname "$0")/animate_event.py" \
    --turb_file  "${TURB_FILE}" \
    --grd_file   "${GRD_FILE}" \
    --out_dir    "${TURB_OUT_DIR}" \
    --obs_lon    ${OBS_LON} \
    --obs_lat    ${OBS_LAT} \
    --skip_time  ${SKIP_TIME} \
    ${START_ARG} \
    ${END_ARG} \
    ${VMAX_ARG}

echo "Done."
