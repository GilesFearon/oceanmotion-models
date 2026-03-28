'''
params required by make_ini() and make_bry()
'''
import os

# Input data information and formating
inputdata = 'mercator' # Input data dictionnary as defined in the Readers/ibc_reader.py

# default value to consider a z-level fine to be used
Nzgoodmin = 4

# multi_files
multi_files = False

# tracers
tracers = ['temp','salt']

# absolute path to the CROCO grid (resolved via ~ so it works across users)
croco_grd = os.path.expanduser('~/code/oceanmotion-models/configs/gulf_01/croco_v1.3.1/forecast/GRID/croco_grd.nc')
sigma_params = dict(theta_s=5, theta_b=7, N=15, hc=200) # Vertical streching, sig_surf/sig_bot/ nb level/critical depth

# Ini filename prefix
ini_prefix = 'croco_ini_MERCATOR'
ini_suffix = ''

# Bry filename prefinformations
bry_prefix = 'croco_bry_MERCATOR'
obc_dict = dict(south=0, west=0, east=1, north=0) # open boundaries (1=open , [S W E N])
cycle_bry=0
