#!/bin/bash
# Downloads CMEMS operational wave data for WW3 boundary conditions.
set -e
source "$(dirname "$0")/../my_env.sh"

# --- Validate credentials ---
if [ -z "$COPERNICUS_USERNAME" ] || [ -z "$COPERNICUS_PASSWORD" ]; then
  echo "Error: COPERNICUS_USERNAME and COPERNICUS_PASSWORD must be set"
  exit 1
fi

mkdir -p "${DOWNLOAD_DIR}/CMEMS_WAV"

echo "=== Download CMEMS Wave Data ==="
echo "  RUN_DATE: ${RUN_DATE}"
echo "  DOMAIN:   ${DOMAIN_DOWNLOAD}"
echo "  HDAYS:    ${HDAYS}"
echo "  FDAYS:    ${FDAYS}"
echo "  OUT_DIR:  ${DOWNLOAD_DIR}/CMEMS_WAV"
echo "=================================="

echo "Downloading CMEMS wave data for ${RUN_DATE}..."
docker run --user $(id -u):$(id -g) --rm \
  -v "${DOWNLOAD_DIR}/CMEMS_WAV":/tmp \
  ${DOWNLOAD_IMAGE} download_cmems_ops \
    --usrname ${COPERNICUS_USERNAME} \
    --passwd ${COPERNICUS_PASSWORD} \
    --dataset cmems_mod_glo_wav_anfc_0.083deg_PT3H-i \
    --varList "VHM0,VHM0_SW1,VHM0_SW2,VHM0_WW,VMDR,VMDR_SW1,VMDR_SW2,VMDR_WW,VPED,VSDX,VSDY,VTM01_SW1,VTM01_SW2,VTM01_WW,VTM02,VTM10,VTPK" \
    --domain ${DOMAIN_DOWNLOAD} \
    --depths 0,0 \
    --run_date "${RUN_DATE_FMT}" \
    --hdays ${HDAYS} --fdays ${FDAYS} \
    --outputDir '/tmp' \
    --outputFile "CMEMS_WAV_${RUN_DATE}.nc"

echo "Done. CMEMS wave data saved to ${DOWNLOAD_DIR}/CMEMS_WAV"
