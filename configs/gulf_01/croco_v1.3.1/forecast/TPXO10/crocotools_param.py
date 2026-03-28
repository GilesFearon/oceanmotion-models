'''
Namelist file for generating tidal forcing files
'''
import os

inputdata = 'tpxo10' # Input data dictionnary as defined in the Readers/tides_reader.py
input_dir = os.path.expanduser('~/code/somisana-croco/DATASETS_CROCOTOOLS/TPXO10/')
input_file = '' # Leave empty if you have multiple files
input_type = 'Re_Im' # Format of the input data 'Amp_phase'or 'Re_Im'
multi_files  = True # Set to True if several input files
if multi_files:
    waves_separated = True # Set to True if input files waves are separated
    elev_file = 'h_<tides>_tpxo10_atlas_30_v2.nc' # elevation file names. if wave_separated put <tides> where wave name is found
    u_file = 'u_<tides>_tpxo10_atlas_30_v2.nc' # eastward currents file names. if wave_separated put <tides> where wave name is found
    v_file = 'u_<tides>_tpxo10_atlas_30_v2.nc' # northward currents file names. if wave_separated put <tides> where wave name is found

# absolute path to the CROCO grid (resolved via ~ so it works across users)
croco_grd = os.path.expanduser('~/code/oceanmotion-models/configs/gulf_01/croco_v1.3.1/forecast/GRID/croco_grd.nc')

# Tide file informations
croco_prefix = 'croco_frc_TPXO10'
croco_suffix = ''
tides = ['M2','S2','N2','K2','K1','O1','P1','Q1','Mf','Mm']

cur = True # Set to True if you to compute currents
pot = False # Set to True if you to compute potiential tides

# Nodal correction
Correction_ssh = True
Correction_uv = True
