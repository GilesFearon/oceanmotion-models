"""
Regridding utilities for turbidity ensemble output.

Mirrors the API and conventions of crocotools_py.regridding and
ww3_tools.regridding so the turbidity zarr lands on the same regular
lat/lon grid as CROCO and WW3 tier-3 output.

Top-level entry point: regrid_ensemble_median(ensemble_dir, ...). It
picks the ensemble-median member and regrids that single member to a
zarr store. Per-cell percentiles produce physically inconsistent
fields; selecting a real member preserves spatial coherence.
"""

import glob
import os
import shutil
import subprocess
from datetime import datetime

import dask
import dask.array as da
import matplotlib.path as mplPath
import numpy as np
import xarray as xr
from dask import delayed
from scipy.interpolate import griddata


VARS = ['C_surface', 'C_bottom', 'tau_max']


def _zarr_compressor_encoding():
    import zarr
    major = int(zarr.__version__.split('.')[0])
    if major >= 3:
        from zarr.codecs import BloscCodec
        return ('compressors', BloscCodec(cname='zstd', clevel=3, shuffle='shuffle'))
    from numcodecs import Blosc
    return ('compressor', Blosc(cname='zstd', clevel=3, shuffle=Blosc.SHUFFLE))


def _select_median_member(member_files):
    """Return (path, score) of the member whose time- and domain-averaged
    surface turbidity ranks at the median position."""
    scores = []
    for mf in member_files:
        with xr.open_dataset(mf) as ds:
            scores.append(float(np.nanmean(ds['C_surface'].values)))
    order = np.argsort(scores)
    median_idx = order[len(order) // 2]
    return member_files[median_idx], scores[median_idx]


def _regrid_member(member_path, grd_path, dir_out, spacing):
    print(f'Regridding {os.path.basename(member_path)}')
    grd = xr.open_dataset(grd_path)
    lon_2d = grd['lon_rho'].values
    lat_2d = grd['lat_rho'].values
    mask_2d = grd['mask_rho'].values.astype(bool) if 'mask_rho' in grd else np.ones_like(lon_2d, dtype=bool)
    grd.close()

    ds = xr.open_dataset(member_path)

    # Boundary polygon and target grid
    lon_b = np.hstack(
        (lon_2d[:, 0], lon_2d[-1, 1:], lon_2d[-1::-1, -1], lon_2d[0, -2::-1])
    )
    lat_b = np.hstack(
        (lat_2d[:, 0], lat_2d[-1, 1:], lat_2d[-1::-1, -1], lat_2d[0, -2::-1])
    )
    lon_min = np.floor(np.min(lon_b) / spacing) * spacing
    lon_max = np.ceil(np.max(lon_b) / spacing) * spacing
    lat_min = np.floor(np.min(lat_b) / spacing) * spacing
    lat_max = np.ceil(np.max(lat_b) / spacing) * spacing
    Nlon = int(np.rint((lon_max - lon_min) / spacing)) + 1
    Nlat = int(np.rint((lat_max - lat_min) / spacing)) + 1
    lon_out = np.linspace(lon_min, lon_max, Nlon, endpoint=True)
    lat_out = np.linspace(lat_min, lat_max, Nlat, endpoint=True)
    lon_grd, lat_grd = np.meshgrid(lon_out, lat_out)

    poly = mplPath.Path(np.column_stack([lon_b, lat_b]))
    mask_out = np.zeros((Nlat, Nlon))
    for y in range(Nlat):
        for x in range(Nlon):
            if poly.contains_point((lon_grd[y, x], lat_grd[y, x])):
                mask_out[y, x] = 1.0

    wet_flat = mask_2d.ravel()
    lonlat_input = np.column_stack(
        [lon_2d.ravel()[wet_flat], lat_2d.ravel()[wet_flat]]
    )

    @delayed
    def chunk(t, variable):
        vals = np.asarray(variable[t]).ravel()[wet_flat]
        return griddata(lonlat_input, vals, (lon_grd, lat_grd), 'nearest') * mask_out / mask_out

    Nt = ds.time.size
    out = {}
    for v in VARS:
        if v not in ds:
            continue
        slabs = [
            da.from_delayed(chunk(t, ds[v].values),
                            shape=(Nlat, Nlon), dtype=float)
            for t in range(Nt)
        ]
        out[v] = da.stack(slabs, axis=0)

    data_vars = {
        v: xr.Variable(['time', 'latitude', 'longitude'], arr, ds[v].attrs)
        for v, arr in out.items()
    }
    coords = {
        'longitude': xr.Variable(['longitude'], lon_out,
                                 {'units': 'degrees_east', 'standard_name': 'longitude'}),
        'latitude':  xr.Variable(['latitude'], lat_out,
                                 {'units': 'degrees_north', 'standard_name': 'latitude'}),
        'time':      xr.Variable(['time'], ds.time.values, ds.time.attrs),
    }
    data_out = xr.Dataset(data_vars=data_vars, coords=coords)
    data_out.attrs['title'] = 'Regridded turbidity (ensemble-median member) — tier 3'
    data_out.attrs['source'] = member_path
    data_out.attrs['source_member'] = os.path.basename(member_path)
    data_out.attrs['history'] = 'Created on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data_out.attrs['conventions'] = 'CF-1.8'

    chunksizes = {'time': 1}
    default_chunksizes = {d: data_out.sizes[d] for d in data_out.sizes}
    comp_key, comp_val = _zarr_compressor_encoding()
    encoding = {
        var: {
            'dtype': 'float32',
            'chunks': [chunksizes.get(d, default_chunksizes[d]) for d in data_out[var].dims],
            comp_key: comp_val,
        }
        for var in data_out.data_vars
    }
    encoding['latitude'] = {'dtype': 'float32'}
    encoding['longitude'] = {'dtype': 'float32'}

    # Stable output name. Which member was picked this cycle is recorded
    # inside the zarr as attrs['source_member'] — no need to encode it in
    # the filename and pretend the symlink is the stable artefact.
    fname_out = os.path.abspath(os.path.join(dir_out, 'turbidity_t3.zarr'))
    # Earlier versions wrote turbidity_t3.zarr as a symlink to a
    # turbidity_t3_memNN.zarr sibling — handle that legacy here.
    if os.path.islink(fname_out):
        os.unlink(fname_out)
    elif os.path.exists(fname_out):
        shutil.rmtree(fname_out)

    os.makedirs(dir_out, exist_ok=True)
    write_op = data_out.to_zarr(fname_out, encoding=encoding, mode='w', compute=False)
    dask.compute(write_op)
    subprocess.call(['chmod', '-R', '775', fname_out])
    print(f'Created: {fname_out}')

    ds.close()


def regrid_ensemble_median(ensemble_dir, member_pattern, grd_file, dir_out, spacing):
    """Pick the ensemble-median member from
    <ensemble_dir>/<member_pattern> and regrid it to a tier-3 zarr at
    <dir_out>/turbidity_t3_memNN.zarr, plus a stable
    <dir_out>/turbidity_t3.zarr symlink."""
    member_files = sorted(glob.glob(os.path.join(ensemble_dir, member_pattern)))
    if len(member_files) < 3:
        raise RuntimeError(
            f'Need at least 3 members under {ensemble_dir} matching '
            f'{member_pattern}, found {len(member_files)}')
    print(f'Found {len(member_files)} members')

    median_path, score = _select_median_member(member_files)
    print(f'Median member: {os.path.basename(median_path)} '
          f'(domain+time mean C_surface = {score:.3f})')

    _regrid_member(median_path, grd_file, dir_out, spacing)
