#!/bin/bash
# Downloads MERCATOR ocean data.
set -e
source "$(dirname "$0")/../my_env.sh"

# --- Validate credentials ---
if [ -z "$COPERNICUS_USERNAME" ] || [ -z "$COPERNICUS_PASSWORD" ]; then
  echo "Error: COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set"
  exit 1
fi

mkdir -p "${DOWNLOAD_DIR}/MERCATOR"

echo "=== Download MERCATOR ==="
echo "  RUN_DATE: ${RUN_DATE}"
echo "  DOMAIN:   ${DOMAIN_DOWNLOAD}"
echo "  HDAYS:    ${HDAYS}"
echo "  FDAYS:    ${FDAYS}"
echo "  OUT_DIR:  ${DOWNLOAD_DIR}/MERCATOR"
echo "=========================="

echo "Downloading MERCATOR for ${RUN_DATE}..."
conda run -n ${DOWNLOAD_ENV} python "${DOWNLOAD_REPO}/cli.py" download_mercator_ops \
    --usrname ${COPERNICUS_USERNAME} \
    --passwd ${COPERNICUS_PASSWORD} \
    --domain ${DOMAIN_DOWNLOAD} \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir "${DOWNLOAD_DIR}/MERCATOR"

echo "Done. MERCATOR data saved to ${DOWNLOAD_DIR}/MERCATOR"
