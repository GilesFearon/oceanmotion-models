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
docker run --user $(id -u):$(id -g) --rm \
  -v "${DOWNLOAD_DIR}/GFS":/tmp \
  ${DOWNLOAD_IMAGE} download_gfs_atm \
    --domain ${DOMAIN_DOWNLOAD} \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir '/tmp'

# --- Reformat grib to CROCO netcdf ---
echo "Reformatting GFS for CROCO..."
mkdir -p "${DOWNLOAD_DIR}/GFS/for_croco"
docker run --user $(id -u):$(id -g) --rm \
  -v "${DOWNLOAD_DIR}/GFS":/data/gfs \
  -v "${DOWNLOAD_DIR}/GFS/for_croco":/output \
  ${CLI_IMAGE} reformat_gfs_atm \
    --gfsDir /data/gfs \
    --outputDir /output \
    --Yorig ${YORIG}

echo "Done. GFS data saved to ${DOWNLOAD_DIR}/GFS"
