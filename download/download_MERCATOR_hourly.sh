#!/bin/bash
# Downloads CMEMS MERCATOR hourly physics data (sea level, currents).
set -e
source "$(dirname "$0")/../my_env.sh"

# --- Validate credentials ---
if [ -z "$COPERNICUS_USERNAME" ] || [ -z "$COPERNICUS_PASSWORD" ]; then
  echo "Error: COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set"
  exit 1
fi

mkdir -p "${DOWNLOAD_DIR}/MERCATOR_hourly"

echo "=== Download CMEMS MERCATOR Hourly Data ==="
echo "  RUN_DATE: ${RUN_DATE}"
echo "  DOMAIN:   ${DOMAIN_DOWNLOAD}"
echo "  HDAYS:    ${HDAYS}"
echo "  FDAYS:    ${FDAYS}"
echo "  OUT_DIR:  ${DOWNLOAD_DIR}/MERCATOR_hourly"
echo "============================================="

echo "Downloading CMEMS MERCATOR hourly data for ${RUN_DATE}..."
conda run -n ${DOWNLOAD_ENV} python "${DOWNLOAD_REPO}/cli.py" download_cmems_ops \
    --usrname ${COPERNICUS_USERNAME} \
    --passwd ${COPERNICUS_PASSWORD} \
    --dataset cmems_mod_glo_phy_anfc_0.083deg_PT1H-m \
    --varList "zos,uo,vo" \
    --domain ${DOMAIN_DOWNLOAD} \
    --depths 0,0.5 \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir "${DOWNLOAD_DIR}/MERCATOR_hourly" \
    --outputFile "MERCATOR_hourly_${RUN_DATE}.nc"

echo "Done. CMEMS MERCATOR hourly data saved to ${DOWNLOAD_DIR}/MERCATOR_hourly"
