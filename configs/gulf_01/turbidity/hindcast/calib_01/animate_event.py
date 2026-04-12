"""
Animate surface turbidity over the highest-mass event in the turbidity model output.

Default: auto-picks a 3-day window centred on the maximum of the domain mass
time series.  Override the window by setting TURB_EVENT_START (and optionally
TURB_EVENT_END) as environment variables with ISO-format strings, e.g.
  TURB_EVENT_START=2022-01-20T00 TURB_EVENT_END=2022-01-23T00

Output: mp4 saved to the same directory as the turbidity netCDF.

Usage:
    conda run -n somisana_croco python animate_event.py \
        --turb_file <path/to/turbidity.nc> \
        --grd_file  <path/to/croco_grd.nc> \
        --out_dir   <output directory> \
        [--obs_lon 54.072347 --obs_lat 24.368937] \
        [--event_start 2022-01-20T00] \
        [--event_end   2022-01-23T00] \
        [--vmax 50] \
        [--skip_time 1]
"""

import os
import sys
import argparse
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mplc
import matplotlib.animation as manim
from datetime import datetime

from crocotools_py.postprocess import get_grd_var


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_data(turb_file, grd_file):
    """Load surface turbidity, coordinates, and mass from the turbidity netCDF."""
    ds = xr.open_dataset(turb_file)
    C_surface = ds['C_surface'].values       # (nt, eta, xi)
    times     = ds['time'].values            # datetime64[ns]
    lon       = ds['lon_rho'].values         # (eta, xi)
    lat       = ds['lat_rho'].values         # (eta, xi)
    mass      = ds['mass'].values            # (nt,)
    ds.close()

    mask_rho = get_grd_var(grd_file, 'mask_rho').values   # (eta, xi), 1=ocean
    ocean = mask_rho > 0.5

    # Apply land mask: NaN over land
    C_plot = np.where(ocean[np.newaxis, :, :], C_surface, np.nan)

    return C_plot, times, lon, lat, mass, ocean


def find_window(times, mass, event_start=None, event_end=None):
    """
    Return (i_start, i_end) index range for the animation window.

    If event_start/event_end are None, auto-picks a 3-day window centred on
    the mass maximum.
    """
    if event_start is not None:
        t0 = np.datetime64(event_start)
        i_start = int(np.argmin(np.abs(times - t0)))
    else:
        i_peak = int(np.argmax(mass))
        # time-step in hours
        dt_hrs = (times[1] - times[0]).astype('timedelta64[m]').astype(float) / 60
        half = int(1.5 * 24 / dt_hrs)   # 1.5 days each side
        i_start = max(0, i_peak - half)

    if event_end is not None:
        t1 = np.datetime64(event_end)
        i_end = int(np.argmin(np.abs(times - t1)))
    else:
        i_peak = int(np.argmax(mass))
        dt_hrs = (times[1] - times[0]).astype('timedelta64[m]').astype(float) / 60
        half = int(1.5 * 24 / dt_hrs)
        i_end = min(len(times) - 1, i_peak + half)

    return i_start, i_end


# ---------------------------------------------------------------------------
# Main plotting / animation
# ---------------------------------------------------------------------------

def animate(turb_file, grd_file, out_dir=None,
            obs_lon=None, obs_lat=None,
            event_start=None, event_end=None,
            vmax=None, skip_time=1):
    """
    Build and save an mp4 animation of surface turbidity.

    Parameters
    ----------
    turb_file : str
    grd_file  : str
    out_dir   : str  (defaults to directory containing turb_file)
    obs_lon, obs_lat : float  (optional observation point overlay)
    event_start, event_end : str  ISO datetime strings, e.g. '2022-01-20T00'
    vmax      : float  (colour scale upper limit, NTU; auto if None)
    skip_time : int   (animate every nth frame; 1 = all frames)
    """
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(turb_file))

    print("Loading data …")
    C_plot, times, lon, lat, mass, ocean = load_data(turb_file, grd_file)

    # Window
    i_start, i_end = find_window(times, mass,
                                  event_start=event_start,
                                  event_end=event_end)
    frames = list(range(i_start, i_end + 1, skip_time))
    print(f"  Event window: {times[i_start]} → {times[i_end]}")
    print(f"  Frames: {len(frames)}  (skip_time={skip_time})")

    # Colour scale: 98th percentile of the windowed data
    if vmax is None:
        sample = C_plot[i_start:i_end + 1]
        vmax = float(np.nanpercentile(sample, 98))
        vmax = max(vmax, 10.0)
    print(f"  vmax = {vmax:.1f} NTU")

    # Colour map / norm — use BoundaryNorm for perceptually even steps
    n_levels = 20
    ticks = np.linspace(0, vmax, n_levels + 1)
    cmap = plt.cm.turbo
    norm = mplc.BoundaryNorm(boundaries=ticks, ncolors=256)

    # Land patch (static grey)
    land_patch = np.where(ocean, np.nan, 1.0)

    # -----------------------------------------------------------------------
    # Build figure
    # -----------------------------------------------------------------------
    # Compute aspect ratio from lon/lat extents for a reasonable figure size
    lon_min, lon_max = np.nanmin(lon), np.nanmax(lon)
    lat_min, lat_max = np.nanmin(lat), np.nanmax(lat)
    aspect = (lon_max - lon_min) / (lat_max - lat_min)

    fig_height = 7.0
    fig_width  = fig_height * aspect + 1.8   # +1.8 for colorbar space
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor('white')

    # First frame
    pcm = ax.pcolormesh(lon, lat, C_plot[frames[0]],
                        cmap=cmap, norm=norm, shading='auto')
    ax.pcolormesh(lon, lat, land_patch,
                  cmap='Greys', vmin=0, vmax=1, shading='auto', zorder=2)

    if obs_lon is not None and obs_lat is not None:
        ax.plot(obs_lon, obs_lat, 'w*', ms=14, mec='k', mew=1.2,
                label='obs', zorder=5)
        ax.legend(loc='upper left', fontsize=10)

    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    ax.set_aspect('equal', adjustable='box')

    cbar = fig.colorbar(pcm, ax=ax, orientation='vertical',
                        shrink=0.85, pad=0.02, aspect=30, ticks=ticks[::2])
    cbar.set_label('Surface turbidity (NTU)', fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    # Time label — positioned in axes coordinates so it stays fixed
    time_str = str(times[frames[0]].astype('datetime64[s]')).replace('T', ' ')
    title_txt = ax.set_title(time_str, fontsize=13, pad=8)

    plt.tight_layout()

    # -----------------------------------------------------------------------
    # Animation update function
    # -----------------------------------------------------------------------
    def update(frame_idx):
        i = frames[frame_idx]
        pcm.set_array(C_plot[i].ravel())
        ts = str(times[i].astype('datetime64[s]')).replace('T', ' ')
        title_txt.set_text(ts)
        return pcm, title_txt

    print("Building animation …")
    anim = manim.FuncAnimation(
        fig, update,
        frames=range(len(frames)),
        interval=200,   # ms between frames in display; ffmpeg fps overrides this
        blit=False
    )

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    # Derive output filename from event window dates
    t0_str = str(times[i_start].astype('datetime64[s]'))[:10].replace('-', '')
    t1_str = str(times[i_end  ].astype('datetime64[s]'))[:10].replace('-', '')
    out_name = f"turbidity_event_{t0_str}_{t1_str}.mp4"
    out_path = os.path.join(out_dir, out_name)

    fps = 8   # frames per second — gives ~9 s video for a 73-frame window
    writer = manim.FFMpegWriter(fps=fps, bitrate=1800,
                                 extra_args=['-pix_fmt', 'yuv420p'])
    print(f"Writing mp4: {out_path}")
    anim.save(out_path, writer=writer, dpi=120)
    plt.close(fig)
    print(f"Done. Saved to: {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--turb_file',    required=True, help='Turbidity netCDF file')
    parser.add_argument('--grd_file',     required=True, help='CROCO grid file')
    parser.add_argument('--out_dir',      default=None,  help='Output directory')
    parser.add_argument('--obs_lon',      type=float, default=None)
    parser.add_argument('--obs_lat',      type=float, default=None)
    parser.add_argument('--event_start',  default=None,
                        help='ISO start of animation window, e.g. 2022-01-20T00')
    parser.add_argument('--event_end',    default=None,
                        help='ISO end of animation window, e.g. 2022-01-23T00')
    parser.add_argument('--vmax',         type=float, default=None,
                        help='Colour scale upper limit (NTU)')
    parser.add_argument('--skip_time',    type=int, default=1,
                        help='Animate every Nth time-step (default 1)')
    args = parser.parse_args()

    # Allow env-var overrides for event window (documented in module docstring)
    event_start = os.environ.get('TURB_EVENT_START', args.event_start)
    event_end   = os.environ.get('TURB_EVENT_END',   args.event_end)

    animate(
        turb_file    = args.turb_file,
        grd_file     = args.grd_file,
        out_dir      = args.out_dir,
        obs_lon      = args.obs_lon,
        obs_lat      = args.obs_lat,
        event_start  = event_start,
        event_end    = event_end,
        vmax         = args.vmax,
        skip_time    = args.skip_time,
    )


if __name__ == '__main__':
    main()
