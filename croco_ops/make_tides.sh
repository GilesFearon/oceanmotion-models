#!/bin/bash
# Generate tidal forcing file using the somisana-croco CLI.
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

conda run -n ${CROCO_ENV} python "${CROCO_REPO}/cli.py" make_tides_fcst \
    --input_dir "${TPXO_DATA_DIR}" \
    --output_dir "${OPS_DIR}/${TIDE_FRC}" \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --Yorig ${YORIG}

echo "Done. Tidal forcing saved to ${OPS_DIR}/${TIDE_FRC}"
