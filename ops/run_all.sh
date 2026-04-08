#!/bin/bash
# Run the full operational forecast workflow end-to-end.
#
# Stages:
#   1. Download forcing (GFS, MERCATOR, MERCATOR_hourly, CMEMS_WAV) — in parallel
#   2. CROCO preprocessing (tides, boundary/initial conditions) — in parallel
#   3. CROCO run
#   4. CROCO postprocessing (regridding, water levels) — in parallel
#   5. WW3 preprocessing (boundary spectra, CROCO-derived forcing) — in parallel
#   6. WW3 run
#
# Compilation (ops/croco_ops/compile.sh) is NOT run here — it only needs to
# happen once, or when cppdefs.h / param_.h change. Run it manually when needed.
#
# Usage:
#   bash ops/run_all.sh                      # defaults (current UTC cycle)
#   RUN_DATE=20260317_00 bash ops/run_all.sh # override run date
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Load Copernicus credentials ---
if [ -f "${SCRIPT_DIR}/.env" ]; then
  set -a
  source "${SCRIPT_DIR}/.env"
  set +a
fi

# --- Load shared environment (for echoing run parameters) ---
source "${SCRIPT_DIR}/my_env.sh"

echo "=============================================="
echo " Operational forecast: run_all.sh"
echo "   RUN_DATE: ${RUN_DATE}"
echo "   DOMAIN:   ${DOMAIN}"
echo "   MODEL:    ${MODEL}"
echo "   HDAYS:    ${HDAYS}"
echo "   FDAYS:    ${FDAYS}"
echo "=============================================="

# --- 1. Downloads (parallel) ---
echo ""
echo ">>> Stage 1: Downloading forcing data"
bash "${SCRIPT_DIR}/download/download_GFS.sh"            &
bash "${SCRIPT_DIR}/download/download_MERCATOR.sh"       &
bash "${SCRIPT_DIR}/download/download_MERCATOR_hourly.sh" &
bash "${SCRIPT_DIR}/download/download_CMEMS_WAV.sh"      &
wait
echo ">>> Stage 1: Downloads complete"

# --- 2. CROCO preprocessing (parallel) ---
echo ""
echo ">>> Stage 2: CROCO preprocessing"
bash "${SCRIPT_DIR}/croco_ops/make_tides.sh"   &
bash "${SCRIPT_DIR}/croco_ops/make_bry_ini.sh" &
wait
echo ">>> Stage 2: CROCO preprocessing complete"

# --- 3. CROCO run ---
echo ""
echo ">>> Stage 3: Running CROCO"
bash "${SCRIPT_DIR}/croco_ops/run_croco.sh"
echo ">>> Stage 3: CROCO run complete"

# --- 4. CROCO postprocessing (parallel) ---
echo ""
echo ">>> Stage 4: CROCO postprocessing"
bash "${SCRIPT_DIR}/croco_ops/postprocess_regridding.sh" &
bash "${SCRIPT_DIR}/croco_ops/postprocess_wl.sh"         &
wait
echo ">>> Stage 4: CROCO postprocessing complete"

# --- 5. WW3 preprocessing (parallel) ---
echo ""
echo ">>> Stage 5: WW3 preprocessing"
bash "${SCRIPT_DIR}/ww3_ops/make_bry.sh"           &
bash "${SCRIPT_DIR}/ww3_ops/make_croco_forcing.sh" &
wait
echo ">>> Stage 5: WW3 preprocessing complete"

# --- 6. WW3 run ---
echo ""
echo ">>> Stage 6: Running WW3"
bash "${SCRIPT_DIR}/ww3_ops/run_ww3.sh"
echo ">>> Stage 6: WW3 run complete"

echo ""
echo "=============================================="
echo " Operational forecast complete for ${RUN_DATE}"
echo "=============================================="
