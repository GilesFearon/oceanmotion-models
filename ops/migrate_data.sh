#!/bin/bash
# One-time migration: move data/ → ops/data/ with flattened model-version paths.
# Safe to re-run: all moves are guarded by existence checks.
# Does NOT delete the old data/ tree — remove it manually after verifying ops/data/.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_DIR}"

DOMAIN=gulf_01
MODEL=croco_v1.3.1
WW3_MODEL=ww3_v6.07.1
TURB_MODEL=turbidity_v1
TURB_RUN_NAME=calib_01

echo "Migrating data/ → ops/data/ ..."

# --- Per-cycle directories ---
for cycle_dir in data/[0-9]*/; do
  [ -d "$cycle_dir" ] || continue
  RUN_DATE=$(basename "$cycle_dir")
  DEST="ops/data/${RUN_DATE}/${DOMAIN}"
  mkdir -p "$DEST"
  echo "  ${RUN_DATE}"

  # CROCO: strip {MODEL} wrapper
  SRC="${cycle_dir}croco_ops/${DOMAIN}/${MODEL}"
  if [ -d "$SRC" ]; then
    mv "$SRC" "$DEST/croco_ops"
  fi

  # WW3: strip {WW3_MODEL} wrapper
  SRC="${cycle_dir}ww3_ops/${DOMAIN}/${WW3_MODEL}"
  if [ -d "$SRC" ]; then
    mv "$SRC" "$DEST/ww3_ops"
  fi

  # Turbidity: strip {TURB_MODEL}/{TURB_RUN_NAME} wrappers
  SRC="${cycle_dir}turbidity_ops/${DOMAIN}/${TURB_MODEL}/${TURB_RUN_NAME}"
  if [ -d "$SRC" ]; then
    mv "$SRC" "$DEST/turbidity_ops"
  fi

  # Downloads: domain was second level in new cycles, absent in old ones
  if [ -d "${cycle_dir}downloads/${DOMAIN}" ]; then
    mv "${cycle_dir}downloads/${DOMAIN}" "$DEST/downloads"
  elif [ -d "${cycle_dir}downloads" ]; then
    # Old cycles (e.g. 20260316_00) had no domain subdir
    mv "${cycle_dir}downloads" "$DEST/downloads"
  fi
done

# --- latest/ ---
echo "  latest"
LATEST_DEST="ops/data/latest/${DOMAIN}"
mkdir -p "${LATEST_DEST}/raw"

SRC="data/latest/raw/${DOMAIN}/${MODEL}"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/raw/croco_ops"

SRC="data/latest/raw/${DOMAIN}/${WW3_MODEL}"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/raw/ww3_ops"

SRC="data/latest/raw/${DOMAIN}/${TURB_MODEL}/${TURB_RUN_NAME}"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/raw/turbidity_ops"

SRC="data/latest/raw/${DOMAIN}/downloads"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/raw/downloads"

SRC="data/latest/postprocess/${DOMAIN}"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/postprocess"

SRC="data/latest/web/${DOMAIN}"
[ -d "$SRC" ] && mv "$SRC" "${LATEST_DEST}/web"

echo ""
echo "Migration complete."
echo "Verify with: find ops/data -maxdepth 5 -type d | sort"
echo "Then remove the old tree:  rm -rf data/"
