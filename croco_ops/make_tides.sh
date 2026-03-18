#!/bin/bash
# Generate tidal forcing file using the somisana-croco CLI Docker image.
set -e
source "$(dirname "$0")/../my_env.sh"

mkdir -p "${OPS_DIR}/${TIDE_FRC}"
cp "${CONFIG_DIR}/${TIDE_FRC}/crocotools_param.py" "${OPS_DIR}/${TIDE_FRC}/"

echo "=== Make Tides ==="
echo "  RUN_DATE:  ${RUN_DATE}"
echo "  TIDE_FRC:  ${TIDE_FRC}"
echo "  CONFIG:    ${CONFIG_DIR}"
echo "  OUTPUT:    ${OPS_DIR}/${TIDE_FRC}"
echo "==================="

docker run --user $(id -u):$(id -g) --rm \
  -v "${CONFIG_DIR}":/config \
  -v "${TPXO_DATA_DIR}":/data/TPXO10 \
  -v "${OPS_DIR}/${TIDE_FRC}":/output \
  ${CLI_IMAGE} make_tides_fcst \
    --input_dir /data/TPXO10/ \
    --output_dir /output \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --Yorig ${YORIG}

echo "Done. Tidal forcing saved to ${OPS_DIR}/${TIDE_FRC}"
