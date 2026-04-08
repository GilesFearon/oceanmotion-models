"""
Operational water level forecast postprocessing.

Extracts CROCO and MERCATOR forecasts at observation locations, reconstructs
tidal predictions from observation-based utide coefficients, computes non-tidal
residuals, and produces a mixture-distribution confidence interval combining
both model forecasts.

Output per location: water_level_{name}.nc containing predicted tide, model
residuals, combined water level, and 68%/95% confidence intervals.

Usage (inside Docker container):
    python postprocess_wl.py --run_date 20260324_00 \
        --locations_file /config/locations.yaml \
        --croco_file /data/croco_output/croco_avg_surf.nc \
        --croco_grd /config/GRID/croco_grd.nc \
        --mercator_file /data/mercator/MERCATOR_hourly_20260324_00.nc \
        --obs_coef_dir /data/obs \
        --croco_coef_dir /data/tidal_analysis \
        --croco_stats_file /data/tidal_analysis/croco_residual_stats.nc \
        --mercator_stats_file /data/mercator_stats/mercator_residual_stats.nc \
        --mdt_file /data/mercator_stats/clim.nc \
        --output_dir /output \
        --yorig 2000
"""

import argparse
import pickle
import numpy as np
import pandas as pd
import xarray as xr
import yaml
import utide
from scipy.stats import norm
from scipy.optimize import brentq
import crocotools_py.postprocess as post


def parse_args():
    parser = argparse.ArgumentParser(description='Postprocess water level forecasts')
    parser.add_argument('--run_date', required=True, help='Run date YYYYMMDD_HH')
    parser.add_argument('--locations_file', required=True)
    parser.add_argument('--croco_file', required=True, help='CROCO avg_surf output')
    parser.add_argument('--croco_grd', required=True, help='CROCO grid file')
    parser.add_argument('--mercator_file', required=True, help='MERCATOR hourly file')
    parser.add_argument('--obs_coef_dir', required=True, help='Dir with obs utide pkl files')
    parser.add_argument('--croco_coef_dir', required=True, help='Dir with CROCO utide pkl files')
    parser.add_argument('--croco_stats_file', required=True, help='CROCO residual stats netCDF')
    parser.add_argument('--mercator_stats_file', required=True, help='MERCATOR residual stats netCDF')
    parser.add_argument('--mdt_file', required=True, help='CMEMS MDT climatology netCDF')
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--yorig', type=int, default=2000)
    parser.add_argument('--location', default=None, help='Process single location (default: all)')
    return parser.parse_args()


def mixture_cdf(x, mu1, mu2, s1, s2):
    """CDF of equal-weight Gaussian mixture."""
    return 0.5 * norm.cdf(x, mu1, s1) + 0.5 * norm.cdf(x, mu2, s2)


def mixture_quantile(q, mu1, mu2, s1, s2):
    """Find quantile of the mixture distribution via root-finding."""
    lo = min(mu1, mu2) - 6 * max(s1, s2)
    hi = max(mu1, mu2) + 6 * max(s1, s2)
    return brentq(lambda x: mixture_cdf(x, mu1, mu2, s1, s2) - q, lo, hi)


def process_location(loc, args):
    """Process a single location: extract, compute residuals, build CIs, save."""
    name = loc['name']
    lat = loc['lat']
    lon = loc['lon']
    print(f'\n=== {name} (lat={lat}, lon={lon}) ===')

    # --- 1. Extract CROCO zeta at location ---
    print('  Extracting CROCO zeta...')
    ds_croco = post.get_ts(args.croco_file, 'zeta', lon, lat,
                           Yorig=args.yorig, grdname=args.croco_grd)
    croco_time = ds_croco.time.values
    croco_zeta = ds_croco.zeta.values
    print(f'  CROCO time: {croco_time[0]} to {croco_time[-1]} ({len(croco_time)} steps)')

    # --- 2. Compute CROCO residual ---
    print('  Computing CROCO residual...')
    croco_coef_path = f'{args.croco_coef_dir}/utide_coef_{name}.pkl'
    with open(croco_coef_path, 'rb') as f:
        croco_coef = pickle.load(f)['coef']

    croco_time_dt = pd.to_datetime(croco_time).to_pydatetime()
    croco_tide = utide.reconstruct(croco_time_dt, croco_coef)
    croco_residual = croco_zeta - croco_tide.h

    # --- 3. Extract MERCATOR zos and demean ---
    print('  Extracting MERCATOR zos...')
    ds_mercator = xr.open_dataset(args.mercator_file)
    mercator_zos = ds_mercator['zos'].sel(
        depth=0.494, latitude=lat, longitude=lon, method='nearest'
    ).squeeze()

    ds_clim = xr.open_dataset(args.mdt_file)
    mdt = float(ds_clim['mdt'].sel(latitude=lat, longitude=lon, method='nearest').values)
    mercator_residual_raw = mercator_zos - mdt
    ds_clim.close()
    print(f'  MDT at location: {mdt:.4f} m')

    # --- 4. Reconstruct obs tidal prediction on CROCO time axis ---
    print('  Reconstructing obs tidal prediction...')
    obs_coef_path = f'{args.obs_coef_dir}/{name}_utide_coef.pkl'
    with open(obs_coef_path, 'rb') as f:
        obs_coef = pickle.load(f)['coef']

    obs_tide = utide.reconstruct(croco_time_dt, obs_coef)
    predicted_tide = obs_tide.h

    # --- 5. Interpolate MERCATOR onto CROCO time axis ---
    print('  Interpolating MERCATOR onto CROCO time axis...')
    mercator_residual = mercator_residual_raw.interp(time=croco_time).values

    # --- 6. Load RMSD from pre-computed stats ---
    ds_croco_stats = xr.open_dataset(args.croco_stats_file)
    rmsd_croco = float(ds_croco_stats['rmsd'].sel(location=name).values)
    ds_croco_stats.close()

    ds_mercator_stats = xr.open_dataset(args.mercator_stats_file)
    rmsd_mercator = float(ds_mercator_stats['rmsd'].sel(location=name).values)
    ds_mercator_stats.close()
    print(f'  RMSD: CROCO={rmsd_croco:.4f} m, MERCATOR={rmsd_mercator:.4f} m')

    # --- 7. Compute mixture-distribution CIs ---
    print('  Computing confidence intervals...')
    n = len(croco_time)
    ci_95_lo = np.full(n, np.nan)
    ci_95_hi = np.full(n, np.nan)
    ci_68_lo = np.full(n, np.nan)
    ci_68_hi = np.full(n, np.nan)

    for i in range(n):
        if np.isnan(croco_residual[i]) or np.isnan(mercator_residual[i]):
            continue
        m1, m2 = croco_residual[i], mercator_residual[i]
        ci_95_lo[i] = mixture_quantile(0.025, m1, m2, rmsd_croco, rmsd_mercator)
        ci_95_hi[i] = mixture_quantile(0.975, m1, m2, rmsd_croco, rmsd_mercator)
        ci_68_lo[i] = mixture_quantile(0.16, m1, m2, rmsd_croco, rmsd_mercator)
        ci_68_hi[i] = mixture_quantile(0.84, m1, m2, rmsd_croco, rmsd_mercator)

    # --- 8. Compute absolute water level ---
    mean_residual = 0.5 * (croco_residual + mercator_residual)
    water_level = predicted_tide + mean_residual
    wl_ci_95_lo = predicted_tide + ci_95_lo
    wl_ci_95_hi = predicted_tide + ci_95_hi
    wl_ci_68_lo = predicted_tide + ci_68_lo
    wl_ci_68_hi = predicted_tide + ci_68_hi

    # --- 9. Save to netCDF ---
    ds_out = xr.Dataset(
        {
            'predicted_tide': (['time'], predicted_tide),
            'croco_residual': (['time'], croco_residual),
            'mercator_residual': (['time'], mercator_residual),
            'mean_residual': (['time'], mean_residual),
            'water_level': (['time'], water_level),
            'ci_68_lo': (['time'], wl_ci_68_lo),
            'ci_68_hi': (['time'], wl_ci_68_hi),
            'ci_95_lo': (['time'], wl_ci_95_lo),
            'ci_95_hi': (['time'], wl_ci_95_hi),
        },
        coords={'time': croco_time},
        attrs={
            'location': name,
            'latitude': lat,
            'longitude': lon,
            'run_date': args.run_date,
            'rmsd_croco': rmsd_croco,
            'rmsd_mercator': rmsd_mercator,
            'mdt_at_location': mdt,
            'description': (
                'Operational water level forecast. '
                'predicted_tide from obs-based utide analysis. '
                'croco_residual and mercator_residual are non-tidal residuals. '
                'water_level = predicted_tide + mean(croco_residual, mercator_residual). '
                'CI bounds from Gaussian mixture: 0.5*N(croco_resid, rmsd_croco) + '
                '0.5*N(mercator_resid, rmsd_mercator).'
            ),
        }
    )

    out_path = f'{args.output_dir}/water_level_{name}.nc'
    ds_out.to_netcdf(out_path)
    print(f'  Saved: {out_path}')

    ds_mercator.close()
    ds_croco.close()


def main():
    args = parse_args()

    with open(args.locations_file) as f:
        locations = yaml.safe_load(f)['locations']

    if args.location:
        locations = [l for l in locations if l['name'] == args.location]
        if not locations:
            raise ValueError(f'Location "{args.location}" not found in {args.locations_file}')

    for loc in locations:
        process_location(loc, args)

    print('\nDone.')


if __name__ == '__main__':
    main()
