#!/bin/bash

# we need a way of specifying the suffix of the file 
python /home/gfearon/code/somisana-croco/cli.py make_tides_inter \
	--input_dir /home/gfearon/code/somisana-croco/DATASETS_CROCOTOOLS/TPXO10/ \
	--output_dir $PWD \
	--month_start 2015-01 \
	--month_end 2021-12 \
	--Yorig 1993

