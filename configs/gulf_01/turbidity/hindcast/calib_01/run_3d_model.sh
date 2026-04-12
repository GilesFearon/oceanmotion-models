#!/bin/bash
# Run the offline 3D turbidity model.
set -e
source "$(dirname "$0")/my_env.sh"

echo "=== Run 3D Turbidity Model ==="
echo "  CROCO_FILE: ${CROCO_FILE}"
echo "  WW3_FILE:   ${WW3_FILE}"
echo "  GRD_FILE:   ${GRD_FILE}"
echo "  YORIG:      ${YORIG}"
echo "  OUT_DIR:    ${TURB_OUT_DIR}"
echo "  OUT_FILE:   ${TURB_OUT_FILE}"
echo "  Params: ws=[${WS_FINE},${WS_COARSE}] M=[${M_FINE},${M_COARSE}]"
echo "          tau_cr=[${TAU_CR_FINE},${TAU_CR_COARSE}] C_bg=${C_BG}"
if [ -n "${TURB_INI_FILE:-}" ]; then
    echo "  INI_FILE:   ${TURB_INI_FILE}"
    echo "  INI_TIME_IDX: ${TURB_INI_TIME_INDEX:--1}"
    INI_ARGS="--ini_file ${TURB_INI_FILE} --ini_time_index ${TURB_INI_TIME_INDEX:--1}"
else
    echo "  INI:        cold start (C_bg)"
    INI_ARGS=""
fi
echo "==============================="

mkdir -p "${TURB_OUT_DIR}"

conda run -n ${TURB_ENV} python "${TURB_CODE_DIR}/offline_3d_model.py" run \
    --croco_file "${CROCO_FILE}" \
    --ww3_file "${WW3_FILE}" \
    --grd_file "${GRD_FILE}" \
    --yorig ${YORIG} \
    --out_dir "${TURB_OUT_DIR}" \
    --out_file "${TURB_OUT_FILE}" \
    --ws_fine ${WS_FINE} \
    --ws_coarse ${WS_COARSE} \
    --M_fine ${M_FINE} \
    --M_coarse ${M_COARSE} \
    --tau_cr_fine ${TAU_CR_FINE} \
    --tau_cr_coarse ${TAU_CR_COARSE} \
    --C_bg ${C_BG} \
    ${INI_ARGS}

echo "Done. Output saved to ${TURB_OUT_DIR}"
