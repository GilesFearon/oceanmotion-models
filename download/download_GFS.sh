#!/bin/bash
# Downloads GFS atmospheric forcing and reformats for CROCO.
set -e
source "$(dirname "$0")/../my_env.sh"

mkdir -p "${DOWNLOAD_DIR}/GFS"

echo "=== Download GFS ==="
echo "  RUN_DATE: ${RUN_DATE}"
echo "  DOMAIN:   ${DOMAIN_DOWNLOAD}"
echo "  HDAYS:    ${HDAYS}"
echo "  FDAYS:    ${FDAYS}"
echo "  OUT_DIR:  ${DOWNLOAD_DIR}/GFS"
echo "====================="

# --- Download raw GFS grib files ---
echo "Downloading GFS for ${RUN_DATE}..."
conda run -n ${DOWNLOAD_ENV} python "${DOWNLOAD_REPO}/cli.py" download_gfs_atm \
    --domain ${DOMAIN_DOWNLOAD} \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir "${DOWNLOAD_DIR}/GFS"

# --- Reformat grib to CROCO netcdf ---
echo "Reformatting GFS for CROCO..."
mkdir -p "${DOWNLOAD_DIR}/GFS/for_croco"
conda run -n ${CROCO_ENV} python "${CROCO_REPO}/cli.py" reformat_gfs_atm \
    --gfsDir "${DOWNLOAD_DIR}/GFS" \
    --outputDir "${DOWNLOAD_DIR}/GFS/for_croco" \
    --Yorig ${YORIG}

echo "Done. GFS data saved to ${DOWNLOAD_DIR}/GFS"
