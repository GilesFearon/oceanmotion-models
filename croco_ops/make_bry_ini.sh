#!/bin/bash
# Generate initial and boundary condition files using the somisana-croco CLI.
set -e
source "$(dirname "$0")/../my_env.sh"

mkdir -p "${OPS_DIR}/${OGCM}"
cp "${CONFIG_DIR}/${OGCM}/crocotools_param.py" "${OPS_DIR}/${OGCM}/"

echo "=== Make BRY + INI ==="
echo "  RUN_DATE:  ${RUN_DATE}"
echo "  OGCM:      ${OGCM}"
echo "  CONFIG:    ${CONFIG_DIR}"
echo "  INPUT:     ${DOWNLOAD_DIR}/${OGCM}/${OGCM}_${RUN_DATE}.nc"
echo "  OUTPUT:    ${OPS_DIR}/${OGCM}"
echo "========================"

# --- Step 1: Initial conditions ---
echo "Making initial conditions..."
conda run -n ${CROCO_ENV} python "${CROCO_REPO}/cli.py" make_ini_fcst \
    --input_file "${DOWNLOAD_DIR}/${OGCM}/${OGCM}_${RUN_DATE}.nc" \
    --output_dir "${OPS_DIR}/${OGCM}" \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --Yorig ${YORIG}

# --- Step 2: Boundary conditions ---
echo "Making boundary conditions..."
conda run -n ${CROCO_ENV} python "${CROCO_REPO}/cli.py" make_bry_fcst \
    --input_file "${DOWNLOAD_DIR}/${OGCM}/${OGCM}_${RUN_DATE}.nc" \
    --output_dir "${OPS_DIR}/${OGCM}" \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --fdays ${FDAYS} \
    --Yorig ${YORIG}

echo "Done. INI + BRY saved to ${OPS_DIR}/${OGCM}"
