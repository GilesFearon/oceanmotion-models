#!/bin/bash
# Generate initial and boundary condition files using the somisana-croco CLI Docker image.
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
docker run --user $(id -u):$(id -g) --rm \
  -v "${CONFIG_DIR}":/config \
  -v "${DOWNLOAD_DIR}/${OGCM}":/data/mercator \
  -v "${OPS_DIR}/${OGCM}":/output \
  ${CLI_IMAGE} make_ini_fcst \
    --input_file /data/mercator/${OGCM}_${RUN_DATE}.nc \
    --output_dir /output \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --Yorig ${YORIG}

# --- Step 2: Boundary conditions ---
echo "Making boundary conditions..."
docker run --user $(id -u):$(id -g) --rm \
  -v "${CONFIG_DIR}":/config \
  -v "${DOWNLOAD_DIR}/${OGCM}":/data/mercator \
  -v "${OPS_DIR}/${OGCM}":/output \
  ${CLI_IMAGE} make_bry_fcst \
    --input_file /data/mercator/${OGCM}_${RUN_DATE}.nc \
    --output_dir /output \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} \
    --fdays ${FDAYS} \
    --Yorig ${YORIG}

echo "Done. INI + BRY saved to ${OPS_DIR}/${OGCM}"
