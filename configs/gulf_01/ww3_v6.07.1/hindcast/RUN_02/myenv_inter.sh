#!/bin/bash

# Set the environment variables for an inter-annual run
# just putting in the variables which we may want to make configurable
# we can always add more here if we want

# source code
export WW3_EXE_DIR=/home/$USER/WW3/model/exe_Ifremer1/

# directories corresponding to this configuration
CONFIG_DIR=/home/gfearon/lustre/oceanmotion-models/configs/gulf_01/ww3_v6.07.1/hindcast
export RUN_DIR=$CONFIG_DIR/RUN_02
export GRID_DIR=$CONFIG_DIR/GRID/
export BRY_DIR=$CONFIG_DIR/SPEC_CMEMS/
export SRF_DIR=/home/gfearon/lustre/DATA/ERA5/gulf_for_croco
export CROCO_WW3_DIR=/home/gfearon/lustre/oceanmotion-models/configs/gulf_01/croco_v1.3.1/hindcast/C04_I01_GLORYS_ERA5/output/for_ww3

# MPI settings
export MPI_NUM_PROCS=24

# time period for interannual run
MONTH_START="2016-01"
MONTH_END="2016-12"

# restart from previous run?
RSTFLAG=1
