#!/bin/bash

# with the wavespectra environment activated!

python /home/$USER/code/somisana-ww3/cli.py make_bry_cmems_monthy \
	--input_dir /home/gfearon/code/somisana-croco/DATASETS_CROCOTOOLS/CMEMS_WAV/gulf/ \
	--lon_file ../GRID/lon.dat \
	--lat_file ../GRID/lat.dat \
	--mask_file ../GRID/mask.dat \
	--output_dir $PWD \
	--month_start 2017-01 \
	--month_end 2025-12 

