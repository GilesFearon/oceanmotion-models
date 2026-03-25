"""
Compute summary statistics of CROCO non-tidal residuals vs observations
at all locations defined in configs/gulf_01/locations.yaml.

Requires:
  - croco_tidal_{name}.nc from tidal_analysis.py
  - observation residuals referenced in locations.yaml

Output: croco_residual_stats.nc (RMSD and correlation per location)
"""

import numpy as np
import xarray as xr
import yaml
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
config_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
locations_file = os.path.join(config_dir, 'locations.yaml')

with open(locations_file) as f:
    locations = yaml.safe_load(f)['locations']

names = []
rmsd_vals = []
corr_vals = []

for loc in locations:
    name = loc['name']
    lat = loc['lat']
    lon = loc['lon']
    obs_file = os.path.expanduser(loc['obs_file'])
    print(f'\n--- {name} ---')

    # load CROCO tidal analysis output
    ds_croco = xr.open_dataset(os.path.join(script_dir, f'croco_tidal_{name}.nc'))

    # load observation residuals
    ds_obs = xr.open_dataset(obs_file)

    # interpolate CROCO residuals onto observation time axis
    croco_interp = ds_croco['residuals'].interp(time=ds_obs.time)
    mod = croco_interp.values
    obs = ds_obs['residuals'].values

    # compute stats over common valid window
    valid = ~np.isnan(obs) & ~np.isnan(mod)
    rmsd = np.sqrt(np.mean((mod[valid] - obs[valid])**2))
    corr = np.corrcoef(mod[valid], obs[valid])[0, 1]

    print(f'  Valid points: {valid.sum()}')
    print(f'  RMSD: {rmsd:.4f} m')
    print(f'  Correlation: {corr:.4f}')

    names.append(name)
    rmsd_vals.append(rmsd)
    corr_vals.append(corr)

# save summary statistics
ds_out = xr.Dataset(
    {
        'rmsd': (['location'], rmsd_vals),
        'correlation': (['location'], corr_vals),
    },
    coords={'location': names},
    attrs={
        'description': 'CROCO non-tidal residual statistics vs observations',
        'locations_file': locations_file,
        'croco_tidal_dir': script_dir,
        'obs_files': str({loc['name']: os.path.expanduser(loc['obs_file']) for loc in locations}),
    }
)

out_path = os.path.join(script_dir, 'croco_residual_stats.nc')
ds_out.to_netcdf(out_path)
print(f'\nSaved: {out_path}')
