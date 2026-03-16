#!/bin/bash
# Downloads GFS + MERCATOR forcing data via the somisana-download Docker image.
#
# Can be run locally:
#   source .env && bash download/download.sh [YYYYMMDD_HH]
#
# Or from a GitHub Actions workflow with env vars set:
#   DOMAIN=45,60,21,33 HDAYS=0 FDAYS=7 ... bash download/download.sh 20260316_00
set -e

# --- Configuration (overridable via env vars) ---
DOMAIN="${DOMAIN:-45,60,21,33}"
HDAYS="${HDAYS:-0}"
FDAYS="${FDAYS:-7}"
IMAGE="${IMAGE:-ghcr.io/saeon/somisana-download_main:latest}"
DATA_DIR="${DATA_DIR:-$(cd "$(dirname "$0")/.." && pwd)/data/downloads}"

# --- Run date (argument or auto-calculate) ---
if [ -n "$1" ]; then
  RUN_DATE="$1"
else
  hour=$(date -u +'%H' | awk '{print int($1 - ($1%12))}')
  RUN_DATE=$(date -u +"%Y%m%d_$(printf '%02d' $hour)")
fi

# Format for somisana-download CLI: YYYY-MM-DD HH:00:00
RUN_DATE_FMT="${RUN_DATE:0:4}-${RUN_DATE:4:2}-${RUN_DATE:6:2} ${RUN_DATE:9:2}:00:00"

# --- Validate credentials ---
if [ -z "$COPERNICUS_USERNAME" ] || [ -z "$COPERNICUS_PASSWORD" ]; then
  echo "Error: COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set"
  exit 1
fi

# --- Create output dirs ---
OUT_DIR="${DATA_DIR}/${RUN_DATE}"
mkdir -p "${OUT_DIR}/GFS" "${OUT_DIR}/MERCATOR"

echo "=== Download config ==="
echo "  RUN_DATE: ${RUN_DATE}"
echo "  DOMAIN:   ${DOMAIN}"
echo "  HDAYS:    ${HDAYS}"
echo "  FDAYS:    ${FDAYS}"
echo "  OUT_DIR:  ${OUT_DIR}"
echo "========================"

# --- Download GFS ---
echo "Downloading GFS for ${RUN_DATE}..."
docker run --user $(id -u):$(id -g) --rm \
  -v "${OUT_DIR}/GFS":/tmp \
  ${IMAGE} download_gfs_atm \
    --domain ${DOMAIN} \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir '/tmp'

# --- Download MERCATOR ---
echo "Downloading MERCATOR for ${RUN_DATE}..."
docker run --user $(id -u):$(id -g) --rm \
  -v "${OUT_DIR}/MERCATOR":/tmp \
  ${IMAGE} download_mercator_ops \
    --usrname ${COPERNICUS_USERNAME} \
    --passwd ${COPERNICUS_PASSWORD} \
    --domain ${DOMAIN} \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir '/tmp'

echo "Done. Data saved to ${OUT_DIR}"
