#!/bin/bash

python /home/gfearon/code/somisana-croco/cli.py make_tides_inter \
	--input_dir /home/gfearon/code/somisana-croco/DATASETS_CROCOTOOLS/TPXO10/ \
	--output_dir $PWD \
	--month_start 2024-01 \
	--month_end 2025-06 \
	--Yorig 1993

