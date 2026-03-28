#!/bin/bash
# Postprocess CROCO output: regrid tiers 1, 2 and 3
set -e
source "$(dirname "$0")/../my_env.sh"

OUTPUT_DIR="${OPS_DIR}/${RUN_NAME}/output"
POSTPROCESS_DIR="${OPS_DIR}/${RUN_NAME}/postprocess"

echo "=== Postprocess Regridding ==="
echo "  RUN_DATE:       ${RUN_DATE}"
echo "  RUN_NAME:       ${RUN_NAME}"
echo "  CROCO OUTPUT:   ${OUTPUT_DIR}"
echo "  OUTPUT:         ${POSTPROCESS_DIR}"
echo "=================================="

mkdir -p "${POSTPROCESS_DIR}"

conda run -n ${CROCO_ENV} python -c "
from crocotools_py.regridding import regrid_tier1, regrid_tier2, regrid_tier3

grdname = '${CONFIG_DIR}/GRID/croco_grd.nc'
Yorig = ${YORIG}

regrid_tier1(
    '${OUTPUT_DIR}/croco_avg.nc',
    '${POSTPROCESS_DIR}',
    grdname=grdname,
    Yorig=Yorig,
)

regrid_tier2(
    '${OUTPUT_DIR}/croco_avg.nc',
    '${POSTPROCESS_DIR}',
    grdname=grdname,
    Yorig=Yorig,
)

regrid_tier3(
    '${POSTPROCESS_DIR}/croco_avg_t2.nc',
    '${POSTPROCESS_DIR}',
    Yorig=Yorig,
    spacing=0.01,
)
"

echo "Done. Regridded output saved to ${POSTPROCESS_DIR}"
