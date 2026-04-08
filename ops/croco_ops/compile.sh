#!/bin/bash
# Compile CROCO executable (runs outside Docker, uses local gfortran/mpich).
# Only needs to run once, or when cppdefs.h changes.
set -e
source "$(dirname "$0")/../my_env.sh"

echo "=== Compile CROCO ==="
echo "  CONFIG_DIR: ${CONFIG_DIR}"
echo "  COMP:       ${COMP}"
echo "======================"

cd "${CONFIG_DIR}" && ./jobcomp_frcst.sh ${COMP}

echo "Done. Executable at ${CONFIG_DIR}/${COMP}/croco"
