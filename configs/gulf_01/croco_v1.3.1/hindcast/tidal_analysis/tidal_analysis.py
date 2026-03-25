"""
Tidal analysis of CROCO hindcast (2016-2024) at all locations defined
in configs/gulf_01/locations.yaml.

Uses the full hindcast to robustly resolve all constituents including SA/SSA.

Outputs per location:
  - utide_coef_{name}.pkl  : tidal coefficients for use with utide.reconstruct()
  - croco_tidal_{name}.nc  : time series of raw zeta, predicted tide, and residuals
"""

import crocotools_py.postprocess as post
from datetime import datetime
import numpy as np
import xarray as xr
import pickle
import yaml
import os
import utide

# paths
script_dir = os.path.dirname(os.path.abspath(__file__))
config_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
locations_file = os.path.join(config_dir, 'locations.yaml')
fname = os.path.join(script_dir, '..', 'C04_I01_GLORYS_ERA5', 'output', 'croco_avg_surf*')
grdname = os.path.join(script_dir, '..', 'GRID', 'croco_grd.nc')

with open(locations_file) as f:
    locations = yaml.safe_load(f)['locations']

for loc in locations:
    name = loc['name']
    lat = loc['lat']
    lon = loc['lon']
    print(f'\n--- {name} (lat={lat}, lon={lon}) ---')

    # extract zeta time series at this location over the hindcast period
    ds_zeta = post.get_ts(fname, 'zeta', lon, lat, Yorig=1993, grdname=grdname,
                          time=slice('2016-01-01', '2024-12-31'))
    zeta = ds_zeta.zeta.values
    time = ds_zeta.time.values
    time_dt = time.astype('datetime64[s]').astype(datetime)

    print(f'  Time range: {time_dt[0]} to {time_dt[-1]}')
    print(f'  Number of time steps: {len(time_dt)}')

    # run utide solve
    coef = utide.solve(time_dt, zeta, lat=lat)

    print(f'  Constituents resolved: {len(coef.name)}')
    print(f'  Z0 (mean): {coef.mean:.6f} m')

    # save tidal coefficients with metadata
    coef_bundle = {
        'coef': coef,
        'source_pattern': fname,
        'grid_file': grdname,
        'time_range': ('2016-01-01', '2024-12-31'),
        'location': loc,
    }
    coef_path = os.path.join(script_dir, f'utide_coef_{name}.pkl')
    with open(coef_path, 'wb') as f:
        pickle.dump(coef_bundle, f)
    print(f'  Saved: {coef_path}')

    # reconstruct tide and compute residuals over full time series
    tide = utide.reconstruct(time_dt, coef)
    predicted = tide.h
    residuals = zeta - predicted

    # save time series
    ds_out = xr.Dataset(
        {
            'zeta': (['time'], zeta),
            'predicted_tide': (['time'], predicted),
            'residuals': (['time'], residuals),
        },
        coords={'time': time},
        attrs={
            'location': name,
            'latitude': lat,
            'longitude': lon,
            'description': 'CROCO hindcast tidal analysis (2016-2024)',
        }
    )
    ts_path = os.path.join(script_dir, f'croco_tidal_{name}.nc')
    ds_out.to_netcdf(ts_path)
    print(f'  Saved: {ts_path}')

print('\nDone.')
