"""
Offline 3D two-class sediment transport model.

Solves the 3D advection-diffusion-settling equation for 2 sediment classes
on the CROCO sigma grid, driven by:
  - Horizontal advection: UP3 (third-order upwind) from CROCO velocity fields
  - Vertical diffusion: implicit tridiagonal using CROCO's AKs
  - Settling: implicit upwind
  - Erosion: Partheniades with Soulsby (1997) combined wave-current bed stress

Two-class system:
  - Fine (washload): slow-settling, maintains background turbidity
  - Coarse (resuspension): fast-settling, drives storm/event peaks

Usage:
    conda run -n somisana_croco python offline_3d_model.py run \\
        --croco_file <path> --ww3_file <path> --grd_file <path> --yorig 1993

References:
    Soulsby, R.L. (1997) "Dynamics of Marine Sands", Thomas Telford, London.
    Partheniades, E. (1965) "Erosion and deposition of cohesive soils", J. Hydraul. Div.
    Shchepetkin & McWilliams (2005) "The regional oceanic modeling system (ROMS)",
        Ocean Modelling, 9, 347-404.
"""

import sys
import os
import argparse
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

from crocotools_py.postprocess import (
    get_var, get_uv, get_grd_var,
    rho2u, rho2v, find_nearest_point
)

# =============================================================================
# Physical constants
# =============================================================================

RHO_W = 1025.0    # seawater density (kg/m^3)
KS = 0.001         # Nikuradse bed roughness (m)
Z0 = KS / 30.0     # hydrodynamic roughness length (m)
KAPPA = 0.4         # von Karman constant

# =============================================================================
# Sediment parameters
# =============================================================================

N_CLASSES = 2
CLASS_NAMES = ['Fine (washload)', 'Coarse (resuspension)']

DEFAULT_PARAMS = {
    'ws': np.array([1e-4, 1e-3]),       # settling velocity (m/s): 0.1 and 1.0 mm/s
    'M': np.array([0.05, 0.3]),          # erosion rate per class (NTU m/s)
    'tau_cr': np.array([0.1, 0.2]),      # critical bed shear stress per class (N/m^2)
    'C_bg': 3.0,                         # background concentration (NTU)
}

CFL_LIMIT = 0.4  # advective CFL threshold for sub-stepping
OUTPUT_INTERVAL = 6  # save snapshots every N timesteps

# =============================================================================
# Soulsby (1997) combined wave-current bed stress — vectorised 2D
# =============================================================================

def soulsby_combined_stress_2d(u_east, v_north, ubr, t0m1, wave_dir,
                                z_bot, mask, z0=Z0, rho=RHO_W):
    """
    Compute combined wave-current bed stress on the full 2D grid.

    Parameters
    ----------
    u_east, v_north : array (M, L)
        Bottom current velocity components (m/s), east and north (on rho grid).
    ubr : array (M, L)
        RMS bottom orbital velocity (m/s).
    t0m1 : array (M, L)
        Mean wave period T0M1 (s).
    wave_dir : array (M, L)
        Mean wave direction (degrees, FROM convention, nautical).
    z_bot : array (M, L)
        Height of bottom velocity point above bed (m).
    mask : array (M, L)
        Land mask (1=ocean, 0=land).
    z0 : float
        Bed roughness length (m).
    rho : float
        Water density (kg/m^3).

    Returns
    -------
    tau_max, tau_mean, tau_c, tau_w : arrays (M, L) in N/m^2
    """
    U = np.sqrt(u_east**2 + v_north**2)
    current_dir = np.degrees(np.arctan2(u_east, v_north))

    z_bot_safe = np.maximum(z_bot, 0.01)  # 1 cm minimum height of vel point above bed
    cd_bot = (KAPPA / np.log(z_bot_safe / z0))**2
    cd_bot = np.minimum(cd_bot, 0.01)     # physical ceiling (very rough bed)
    tau_c = rho * cd_bot * U**2

    A = ubr * t0m1 / (2 * np.pi)
    A_over_z0 = np.maximum(A, 1e-20) / z0
    fw = np.where(A_over_z0 > 1.57, 1.39 * A_over_z0**(-0.52), 0.3)
    no_waves = (ubr <= 0) | (t0m1 <= 0)
    fw = np.where(no_waves, 0.0, fw)

    tau_w = 0.5 * rho * fw * ubr**2

    phi = np.radians(wave_dir - current_dir - 180.0)
    tau_sum = tau_c + tau_w
    ratio = np.where(tau_sum > 0, tau_w / tau_sum, 0.0)

    tau_mean = tau_c * (1.0 + 1.2 * ratio**3.2)
    tau_max = np.sqrt((tau_mean + tau_w * np.cos(phi))**2
                      + (tau_w * np.sin(phi))**2)

    tau_max = np.where(no_waves, tau_c, tau_max)
    tau_mean = np.where(no_waves, tau_c, tau_mean)

    # Physical sanity cap — 5 N/m^2 is already storm-extreme on the shelf
    tau_max = np.minimum(tau_max, 5.0)
    tau_mean = np.minimum(tau_mean, 5.0)

    tau_max *= mask
    tau_mean *= mask
    tau_c *= mask
    tau_w *= mask

    return tau_max, tau_mean, tau_c, tau_w

# =============================================================================
# Grid loading
# =============================================================================

def load_grid(grd_file):
    """
    Load static grid fields and derive masks and metrics.

    Returns dict with: h, pm, pn, angle, mask_rho, mask_u, mask_v,
                       on_u, om_v, area
    """
    h = get_grd_var(grd_file, 'h').values
    pm = get_grd_var(grd_file, 'pm').values
    pn = get_grd_var(grd_file, 'pn').values
    angle = get_grd_var(grd_file, 'angle').values
    mask_rho = get_grd_var(grd_file, 'mask_rho').values
    lon_rho = get_grd_var(grd_file, 'lon_rho').values
    lat_rho = get_grd_var(grd_file, 'lat_rho').values

    # Derive staggered masks: both adjacent rho cells must be ocean
    mask_u = mask_rho[:, :-1] * mask_rho[:, 1:]
    mask_v = mask_rho[:-1, :] * mask_rho[1:, :]

    # Grid metrics at u and v points
    # on_u = dy at u-points, om_v = dx at v-points
    on_u = rho2u(1.0 / pn)  # (M, L-1)
    om_v = rho2v(1.0 / pm)  # (M-1, L)
    area = 1.0 / (pm * pn)  # cell area on rho grid (M, L)

    return {
        'h': h, 'pm': pm, 'pn': pn, 'angle': angle,
        'mask_rho': mask_rho, 'mask_u': mask_u, 'mask_v': mask_v,
        'on_u': on_u, 'om_v': om_v, 'area': area,
        'lon_rho': lon_rho, 'lat_rho': lat_rho,
    }


def zr_to_zw_Hz(z_r):
    """
    Derive z_w and Hz from z_r for a single timestep.

    Parameters
    ----------
    z_r : array (N, M, L) — depths at rho levels (m, relative to MSL)

    Returns
    -------
    z_w : array (N+1, M, L) — depths at w levels
    Hz : array (N, M, L) — layer thicknesses (m, positive)
    """
    N, M, L = z_r.shape
    z_w = np.zeros((N + 1, M, L))
    z_w[0] = 2 * z_r[0] - z_r[1]           # below bottom rho
    z_w[-1] = 2 * z_r[-1] - z_r[-2]         # above top rho
    for k in range(1, N):
        z_w[k] = 0.5 * (z_r[k-1] + z_r[k])

    Hz = np.maximum(np.diff(z_w, axis=0), 1e-10)  # (N, M, L), positive
    return z_w, Hz

# =============================================================================
# WW3 time interpolation
# =============================================================================

def interpolate_ww3_to_croco_times(ds_ww3, croco_times):
    """
    Interpolate WW3 fields onto CROCO times.

    Returns dict with ubr, t0m1, wave_dir — all (nt, M, L).
    """
    ww3_times = ds_ww3['time'].values
    t_ref = min(croco_times[0], ww3_times[0])
    croco_sec = (croco_times - t_ref) / np.timedelta64(1, 's')
    ww3_sec = (ww3_times - t_ref) / np.timedelta64(1, 's')

    # Check if times align exactly (skip interpolation if so)
    if len(croco_sec) == len(ww3_sec) and np.allclose(croco_sec, ww3_sec, atol=1.0):
        print("  WW3 and CROCO times align — no interpolation needed")
        uubr = ds_ww3['uubr'].values
        vubr = ds_ww3['vubr'].values
        ubr = np.sqrt(uubr**2 + vubr**2)
        t0m1 = ds_ww3['t0m1'].values
        wave_dir = ds_ww3['dir'].values
    else:
        print(f"  Interpolating WW3 ({len(ww3_sec)} steps) onto CROCO ({len(croco_sec)} steps)...")
        nt = len(croco_sec)
        M, L = ds_ww3['uubr'].shape[1], ds_ww3['uubr'].shape[2]

        # Load WW3 arrays
        uubr_ww3 = ds_ww3['uubr'].values
        vubr_ww3 = ds_ww3['vubr'].values
        t0m1_ww3 = ds_ww3['t0m1'].values
        dir_ww3 = ds_ww3['dir'].values

        # Replace NaN with 0 for interpolation
        uubr_ww3 = np.nan_to_num(uubr_ww3, nan=0.0)
        vubr_ww3 = np.nan_to_num(vubr_ww3, nan=0.0)
        t0m1_ww3 = np.nan_to_num(t0m1_ww3, nan=0.0)

        ubr_ww3 = np.sqrt(uubr_ww3**2 + vubr_ww3**2)

        # Interpolate scalars along time axis
        from scipy.interpolate import interp1d
        ubr_interp = interp1d(ww3_sec, ubr_ww3, axis=0, fill_value='extrapolate')
        t0m1_interp = interp1d(ww3_sec, t0m1_ww3, axis=0, fill_value='extrapolate')

        ubr = ubr_interp(croco_sec)
        t0m1 = t0m1_interp(croco_sec)

        # Direction: interpolate via sin/cos to avoid wrapping
        dir_rad = np.deg2rad(np.nan_to_num(dir_ww3, nan=0.0))
        sin_interp = interp1d(ww3_sec, np.sin(dir_rad), axis=0, fill_value='extrapolate')
        cos_interp = interp1d(ww3_sec, np.cos(dir_rad), axis=0, fill_value='extrapolate')
        wave_dir = np.rad2deg(np.arctan2(sin_interp(croco_sec),
                                          cos_interp(croco_sec))) % 360.0

    # Replace any remaining NaN with 0
    ubr = np.nan_to_num(ubr, nan=0.0)
    t0m1 = np.nan_to_num(t0m1, nan=0.0)
    wave_dir = np.nan_to_num(wave_dir, nan=0.0)

    return {'ubr': ubr, 't0m1': t0m1, 'wave_dir': wave_dir}

# =============================================================================
# UP3 horizontal advection
# =============================================================================

def up3_xi_flux(C, Huon, mask_u):
    """
    UP3 (third-order upwind) flux in xi-direction for one sigma level.

    Following CROCO compute_horiz_tracer_fluxes.h.

    Parameters
    ----------
    C : array (M, L) — tracer on rho grid
    Huon : array (M, L-1) — volume flux at u-points
    mask_u : array (M, L-1) — mask at u-points

    Returns
    -------
    flux : array (M, L-1) — advective flux at u-points
    """
    M, L = C.shape

    # Step 1: Differences at u-points (masked)
    FX = (C[:, 1:] - C[:, :-1]) * mask_u  # (M, L-1)

    # Extend FX for boundary curvature calculation
    FX_ext = np.zeros((M, L + 1))
    FX_ext[:, 1:L] = FX
    FX_ext[:, 0] = FX[:, 0]      # western boundary: ghost = first interior
    FX_ext[:, L] = FX[:, -1]     # eastern boundary: ghost = last interior

    # Step 2: Curvature at rho-points
    curv = FX_ext[:, 1:L+1] - FX_ext[:, 0:L]  # (M, L)

    # Step 3: UP3 flux at u-points — upwind curvature selection
    # u-point iu is between rho iu (left) and rho iu+1 (right)
    cff = np.where(Huon > 0, curv[:, :L-1], curv[:, 1:L])

    C_avg = 0.5 * (C[:, 1:] + C[:, :-1])
    flux = (C_avg - cff / 3.0) * Huon * mask_u

    return flux


def up3_eta_flux(C, Hvom, mask_v):
    """
    UP3 flux in eta-direction for one sigma level.

    Parameters
    ----------
    C : array (M, L)
    Hvom : array (M-1, L) — volume flux at v-points
    mask_v : array (M-1, L)

    Returns
    -------
    flux : array (M-1, L)
    """
    M, L = C.shape

    FE = (C[1:, :] - C[:-1, :]) * mask_v  # (M-1, L)

    FE_ext = np.zeros((M + 1, L))
    FE_ext[1:M, :] = FE
    FE_ext[0, :] = FE[0, :]
    FE_ext[M, :] = FE[-1, :]

    curv = FE_ext[1:M+1, :] - FE_ext[0:M, :]  # (M, L)

    cff = np.where(Hvom > 0, curv[:M-1, :], curv[1:M, :])

    C_avg = 0.5 * (C[1:, :] + C[:-1, :])
    flux = (C_avg - cff / 3.0) * Hvom * mask_v

    return flux


def flux_divergence(flux_xi, flux_eta, M, L):
    """
    Compute flux divergence on the rho grid.

    Zero flux at domain boundaries.

    Parameters
    ----------
    flux_xi : array (M, L-1)
    flux_eta : array (M-1, L)

    Returns
    -------
    div : array (M, L)
    """
    div = np.zeros((M, L))

    # Xi divergence
    div[:, 1:-1] += flux_xi[:, 1:] - flux_xi[:, :-1]
    div[:, 0] += flux_xi[:, 0]
    div[:, -1] -= flux_xi[:, -1]

    # Eta divergence
    div[1:-1, :] += flux_eta[1:, :] - flux_eta[:-1, :]
    div[0, :] += flux_eta[0, :]
    div[-1, :] -= flux_eta[-1, :]

    return div

# =============================================================================
# Implicit vertical diffusion + settling
# =============================================================================

def solve_vertical_implicit_3d(C, AKs, ws, Hz, z_r, dt, erosion, mask):
    """
    Implicit vertical diffusion + settling for all columns simultaneously.

    Following CROCO t3dmix_tridiagonal.h (Hz-multiplied formulation).

    Parameters
    ----------
    C : array (N, M, L) — concentration at rho levels
    AKs : array (N+1, M, L) — diffusivity at w levels (m^2/s)
    ws : float — settling velocity (m/s, positive downward)
    Hz : array (N, M, L) — layer thicknesses (m)
    z_r : array (N, M, L) — depths at rho levels (m)
    dt : float — timestep (s)
    erosion : array (M, L) — erosion flux at bed (NTU m/s)
    mask : array (M, L) — land mask

    Returns
    -------
    C_new : array (N, M, L)
    """
    N, M, L = C.shape

    # Diffusion coefficients at w-levels: FC(k) = dt * AKs(k) / dz(k)
    # dz(k) = z_r(k) - z_r(k-1) = distance between adjacent rho levels
    # FC(0) = FC(N) = 0 (no-flux BCs)
    FC = np.zeros((N + 1, M, L))
    for k in range(1, N):
        dz = z_r[k] - z_r[k-1]
        FC[k] = dt * AKs[k] / np.maximum(dz, 1e-10)

    # Build tridiagonal coefficients (CROCO Hz-multiplied form)
    a = np.zeros((N, M, L))  # sub-diagonal
    b = np.zeros((N, M, L))  # diagonal
    c = np.zeros((N, M, L))  # super-diagonal
    d = np.zeros((N, M, L))  # RHS

    ws_dt = dt * ws

    for k in range(N):
        b[k] = Hz[k] + FC[k] + FC[k+1] if k < N-1 else Hz[k] + FC[k]
        if k > 0:
            a[k] = -FC[k]
            b[k] = Hz[k] + FC[k] + (FC[k+1] if k < N-1 else 0.0)
        else:
            b[k] = Hz[k] + (FC[k+1] if k < N-1 else 0.0)

        if k < N - 1:
            c[k] = -FC[k+1]

        # Settling (implicit upwind downward)
        b[k] += ws_dt
        if k < N - 1:
            c[k] -= ws_dt

        # RHS
        d[k] = Hz[k] * C[k]

    # Erosion into bottom cell
    d[0] += dt * erosion

    # Vectorised Thomas solve
    C_new = thomas_solve_3d(a, b, c, d, N)

    # Positivity and masking
    C_new = np.maximum(C_new, 0.0) * mask[np.newaxis, :, :]
    return C_new


def thomas_solve_3d(a, b, c, d, N):
    """
    Vectorised Thomas algorithm for (N, M, L) tridiagonal systems.

    All operations vectorised over (M, L) — loop only over k (15 levels).
    """
    M, L = b.shape[1], b.shape[2]
    cp = np.zeros_like(b)
    dp = np.zeros_like(d)

    # Forward sweep
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for k in range(1, N):
        denom = b[k] - a[k] * cp[k-1]
        cp[k] = c[k] / denom
        dp[k] = (d[k] - a[k] * dp[k-1]) / denom

    # Back substitution
    x = np.zeros_like(d)
    x[N-1] = dp[N-1]
    for k in range(N-2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k+1]

    return x

# =============================================================================
# Erosion
# =============================================================================

def compute_erosion(tau_max, tau_cr, M_rate, mask):
    """Partheniades erosion for one sediment class, vectorised 2D."""
    excess = np.maximum(tau_max / tau_cr - 1.0, 0.0)
    return M_rate * excess * mask

# =============================================================================
# Main model
# =============================================================================

def run(croco_file, ww3_file, grd_file, yorig, params=None, out_dir=None,
        out_file_name='turbidity_3d_output.nc',
        ini_file=None, ini_time_index=-1):
    """Run the offline 3D sediment transport model.

    Parameters
    ----------
    ini_file : str or None
        Optional path to a previous turbidity output file containing a
        ``C_3d`` variable (dims: time, sed_class, s_rho, eta_rho, xi_rho).
        If provided, the 3D concentration field is loaded from it as the
        initial condition. If None, the run starts from zero (background
        ``C_bg`` is added to the output at every step).
    ini_time_index : int
        Time index within ``ini_file`` to use as the initial state.
        Default -1 (last snapshot in the file).
    """

    if params is None:
        params = DEFAULT_PARAMS
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Load grid ---
    print("Loading grid...")
    grid = load_grid(grd_file)
    M, L = grid['mask_rho'].shape
    print(f"  Grid: ({M}, {L}), ocean cells: {int(grid['mask_rho'].sum())}")

    # --- Load AKs and depth via get_var ---
    print("\nLoading AKs via get_var...")
    ds_aks = get_var(croco_file, 'AKs', grdname=grd_file, Yorig=yorig)
    AKs_all = np.nan_to_num(ds_aks['AKs'].values, nan=0.0)   # (nt, N+1, M, L)
    z_r_all = np.nan_to_num(ds_aks['depth'].values, nan=0.0)  # (nt, N, M, L)
    croco_times = ds_aks['time'].values
    nt = len(croco_times)
    N = z_r_all.shape[1]
    print(f"  N={N}, {nt} timesteps: {croco_times[0]} to {croco_times[-1]}")
    ds_aks.close()

    # --- Open raw dataset for staggered u, v ---
    ds_croco = xr.open_dataset(croco_file)

    # --- Load bottom velocity (east/north on rho grid) ---
    print("\nLoading bottom velocity via get_uv...")
    ds_bot = get_uv(croco_file, grdname=grd_file, level=0, Yorig=yorig)
    u_bot_all = np.nan_to_num(ds_bot['u'].values, nan=0.0)  # (nt, M, L)
    v_bot_all = np.nan_to_num(ds_bot['v'].values, nan=0.0)  # (nt, M, L)
    print(f"  {nt} timesteps loaded")

    # --- Load WW3 and interpolate ---
    print("\nLoading WW3 data...")
    ds_ww3 = xr.open_dataset(ww3_file)
    ww3 = interpolate_ww3_to_croco_times(ds_ww3, croco_times)
    ds_ww3.close()

    # --- Initialise concentration ---
    C = np.zeros((N_CLASSES, N, M, L))
    if ini_file is not None:
        print(f"\nLoading initial condition from: {ini_file}")
        print(f"  time index: {ini_time_index}")
        ds_ini = xr.open_dataset(ini_file)
        if 'C_3d' not in ds_ini.variables:
            raise ValueError(
                f"Initial condition file has no 'C_3d' variable: {ini_file}")
        C_ini = ds_ini['C_3d'].isel(restart_time=ini_time_index).values  # (sed_class, N, M, L)
        if C_ini.shape != C.shape:
            raise ValueError(
                f"C_3d shape {C_ini.shape} in ini_file does not match "
                f"model shape {C.shape}")
        ini_t = ds_ini['restart_time'].isel(restart_time=ini_time_index).values
        print(f"  snapshot time: {ini_t}")
        C[:] = np.nan_to_num(C_ini, nan=0.0)
        ds_ini.close()

    # --- Pre-allocate output ---
    # Save surface and bottom concentration + tau_max at every timestep
    C_surface_all = np.zeros((nt, M, L))
    C_bottom_all = np.zeros((nt, M, L))
    C_bottom_per_class = np.zeros((N_CLASSES, nt, M, L))
    tau_max_all = np.zeros((nt, M, L))
    mass_history = np.zeros(nt)

    print(f"\nRunning 3D model: {N_CLASSES} classes, {nt} timesteps")
    for ic in range(N_CLASSES):
        print(f"  {CLASS_NAMES[ic]}: ws={params['ws'][ic]*1000:.2f} mm/s, "
              f"M={params['M'][ic]:.3f} NTU·m/s, tau_cr={params['tau_cr'][ic]:.3f} N/m²")
    print(f"  C_bg={params['C_bg']:.1f} NTU")

    # --- Seed t=0 output from initial state ---
    C_total0 = C.sum(axis=0) + params['C_bg']
    C_surface_all[0] = C_total0[-1]
    C_bottom_all[0] = C_total0[0]
    C_bottom_per_class[:, 0] = C[:, 0]

    # --- Main timestep loop ---
    for t in range(1, nt):
        dt = (croco_times[t] - croco_times[t-1]) / np.timedelta64(1, 's')

        # (a) Read native u, v for advection (grid-aligned, staggered)
        u_native = ds_croco['u'].isel(time=t).values   # (N, M, L-1)
        v_native = ds_croco['v'].isel(time=t).values   # (N, M-1, L)

        # (b) AKs and vertical grid from pre-loaded arrays
        AKs = np.maximum(AKs_all[t], 1e-6)             # (N+1, M, L)
        z_r = z_r_all[t]                                # (N, M, L)
        z_w, Hz = zr_to_zw_Hz(z_r)

        # (c) Volume fluxes on staggered grids
        Hz_u = rho2u(Hz)  # (N, M, L-1)
        Hz_v = rho2v(Hz)  # (N, M-1, L)
        Huon = u_native * Hz_u * grid['on_u'][np.newaxis, :, :]
        Hvom = v_native * Hz_v * grid['om_v'][np.newaxis, :, :]

        # (d) CFL check and sub-stepping
        cfl_xi = np.abs(u_native) * dt * rho2u(grid['pm'])[np.newaxis, :, :]
        cfl_eta = np.abs(v_native) * dt * rho2v(grid['pn'])[np.newaxis, :, :]
        cfl_max = max(np.nanmax(cfl_xi), np.nanmax(cfl_eta))
        n_sub = max(1, int(np.ceil(cfl_max / CFL_LIMIT)))
        dt_adv = dt / n_sub

        # (e) Bed stress
        # Height of bottom rho-level (cell centre) above the bed
        z_bot = 0.5 * (z_w[1] - z_w[0])  # (M, L)
        tau_max_2d, _, tau_c_2d, tau_w_2d = soulsby_combined_stress_2d(
            u_bot_all[t], v_bot_all[t],
            ww3['ubr'][t], ww3['t0m1'][t], ww3['wave_dir'][t],
            z_bot, grid['mask_rho']
        )

        # (f) Advection + vertical solve for each class
        for ic in range(N_CLASSES):
            # Explicit UP3 horizontal advection (with sub-stepping)
            C_adv = C[ic].copy()
            for _ in range(n_sub):
                for k in range(N):
                    flux_xi = up3_xi_flux(C_adv[k], Huon[k], grid['mask_u'])
                    flux_eta = up3_eta_flux(C_adv[k], Hvom[k], grid['mask_v'])
                    div = flux_divergence(flux_xi, flux_eta, M, L)
                    C_adv[k] -= dt_adv * div / (Hz[k] * grid['area'])
                C_adv = np.maximum(C_adv, 0.0) * grid['mask_rho'][np.newaxis, :, :]

            # Erosion
            erosion = compute_erosion(tau_max_2d, params['tau_cr'][ic],
                                      params['M'][ic], grid['mask_rho'])

            # Implicit vertical (diffusion + settling + erosion)
            C[ic] = solve_vertical_implicit_3d(
                C_adv, AKs, params['ws'][ic], Hz, z_r, dt, erosion,
                grid['mask_rho']
            )

        # (g) Store output fields
        C_total = C.sum(axis=0) + params['C_bg']
        C_surface_all[t] = C_total[-1]
        C_bottom_all[t] = C_total[0]
        C_bottom_per_class[:, t] = C[:, 0]
        tau_max_all[t] = tau_max_2d
        total_mass = np.sum(C.sum(axis=0) * Hz * grid['area'] * grid['mask_rho'])
        mass_history[t] = total_mass

        # Progress
        if t % 24 == 0 or t == nt - 1:
            c_max = float(np.nanmax(C))
            jk = np.unravel_index(np.nanargmax(C_total[0]), C_total[0].shape)
            c_bot_max = float(C_total[0, jk[0], jk[1]])
            tau_max_max = float(np.nanmax(tau_max_2d))
            print(f"  t={t:4d}/{nt-1}  CFL={cfl_max:.3f} (n_sub={n_sub})  "
                  f"mass={total_mass:.2e}  C_max={c_max:.2e}  "
                  f"C_bot_max={c_bot_max:.2e} @({jk[0]},{jk[1]})  "
                  f"tau_max={tau_max_max:.2f}")

    ds_croco.close()

    # --- Write output ---
    print("\nWriting output...")
    out_file = os.path.join(out_dir, out_file_name)
    # Final 3D state as a restart snapshot (single time slice).
    # Stored with a leading time dim of size 1 so ini_time_index is
    # future-proof for multi-snapshot restart files.
    C_3d_snapshot = C[np.newaxis, ...].astype(np.float32)      # (1, sed_class, N, M, L)
    restart_times = croco_times[-1:]                            # (1,)
    write_output(out_file, croco_times, C_surface_all, C_bottom_all,
                 C_bottom_per_class, tau_max_all, mass_history, grid, params,
                 C_3d=C_3d_snapshot, restart_times=restart_times)

    return out_file


def write_output(out_file, times, C_surface, C_bottom, C_bottom_per_class,
                 tau_max, mass, grid, params,
                 C_3d=None, restart_times=None):
    """Write model output to NetCDF."""
    ds = xr.Dataset()

    ds['C_surface'] = xr.DataArray(C_surface, dims=['time', 'eta_rho', 'xi_rho'],
                                   attrs={'long_name': 'Surface turbidity (total + background)',
                                          'units': 'NTU'})
    ds['C_bottom'] = xr.DataArray(C_bottom, dims=['time', 'eta_rho', 'xi_rho'],
                                  attrs={'long_name': 'Bottom turbidity (total + background)',
                                         'units': 'NTU'})
    ds['C_bottom_per_class'] = xr.DataArray(
        C_bottom_per_class, dims=['sed_class', 'time', 'eta_rho', 'xi_rho'],
        attrs={'long_name': 'Bottom turbidity per sediment class (no background)',
               'units': 'NTU'})
    ds.coords['sed_class'] = np.arange(C_bottom_per_class.shape[0])
    ds['tau_max'] = xr.DataArray(tau_max, dims=['time', 'eta_rho', 'xi_rho'],
                                 attrs={'long_name': 'Combined wave-current bed stress',
                                        'units': 'N/m^2'})
    ds['mass'] = xr.DataArray(mass, dims=['time'],
                              attrs={'long_name': 'Total suspended mass',
                                     'units': 'NTU m^3'})
    ds.coords['time'] = times
    ds.coords['lon_rho'] = xr.DataArray(grid['lon_rho'], dims=['eta_rho', 'xi_rho'])
    ds.coords['lat_rho'] = xr.DataArray(grid['lat_rho'], dims=['eta_rho', 'xi_rho'])

    ds.attrs['C_bg'] = params['C_bg']
    for ic in range(N_CLASSES):
        ds.attrs[f'ws_{ic}'] = params['ws'][ic]
        ds.attrs[f'M_{ic}'] = params['M'][ic]
        ds.attrs[f'tau_cr_{ic}'] = params['tau_cr'][ic]

    encoding = {}
    if C_3d is not None and restart_times is not None:
        ds['C_3d'] = xr.DataArray(
            C_3d, dims=['restart_time', 'sed_class', 's_rho', 'eta_rho', 'xi_rho'],
            attrs={'long_name': 'Full 3D concentration per class (restart snapshot, no background)',
                   'units': 'NTU'})
        ds.coords['restart_time'] = restart_times
        encoding['C_3d'] = {'zlib': True, 'complevel': 4, 'dtype': 'float32'}

    ds.to_netcdf(out_file, encoding=encoding if encoding else None)
    print(f"  Saved: {out_file}")


def plot_spatial(turb_file, grd_file, times=None, out_dir=None,
                 obs_lon=None, obs_lat=None, vmax=None):
    """
    Three-panel map of surface turbidity at selected times.

    Parameters
    ----------
    turb_file : str
        Model output netCDF from run().
    grd_file : str
        CROCO grid file (for coast line via mask).
    times : list of 3 str or None
        Times as 'YYYY-MM-DDTHH' strings. If None, auto-picks:
        the calmest time, and the two highest-mass peaks.
    out_dir : str
        Where to save the figure.
    obs_lon, obs_lat : float
        If provided, overlay a marker at the obs location.
    vmax : float
        Colour scale upper limit (NTU). If None, auto-picked from 98th pctl.
    """
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(turb_file))

    ds = xr.open_dataset(turb_file)
    C_surface = ds['C_surface'].values        # (nt, M, L)
    ds_times = ds['time'].values
    lon = ds['lon_rho'].values
    lat = ds['lat_rho'].values
    mass = ds['mass'].values
    ds.close()

    mask_rho = get_grd_var(grd_file, 'mask_rho').values
    ocean = mask_rho > 0.5

    C_plot = np.where(ocean[np.newaxis, :, :], C_surface, np.nan)

    # --- Select three times ---
    if times is None:
        # Auto-pick: calmest and two biggest events
        i_calm = int(np.argmin(mass[1:]) + 1)   # skip t=0 which is zero mass
        # Simple local-max detection on mass
        m = mass.copy()
        m[0] = 0
        i_peak1 = int(np.argmax(m))
        # Mask out a window around peak1 and find the next highest
        w = max(24, len(m) // 10)
        m[max(0, i_peak1 - w):i_peak1 + w] = 0
        i_peak2 = int(np.argmax(m))
        idx = sorted([i_calm, i_peak1, i_peak2])
    else:
        idx = []
        for tstr in times:
            t = np.datetime64(tstr)
            k = int(np.argmin(np.abs(ds_times - t)))
            idx.append(k)

    titles = [str(ds_times[k].astype('datetime64[s]')) for k in idx]

    # --- Colour scale ---
    if vmax is None:
        sample = C_plot[idx]
        vmax = float(np.nanpercentile(sample, 98))
        vmax = max(vmax, 10.0)   # don't let the scale collapse on a calm panel

    # --- Plot ---
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=True,
                             constrained_layout=True)

    cmap = plt.cm.turbo
    for ax, k, title in zip(axes, idx, titles):
        pcm = ax.pcolormesh(lon, lat, C_plot[k],
                            cmap=cmap, vmin=0, vmax=vmax, shading='auto')
        # land mask shading
        ax.pcolormesh(lon, lat, np.where(ocean, np.nan, 1.0),
                      cmap='Greys', vmin=0, vmax=1, shading='auto')
        if obs_lon is not None and obs_lat is not None:
            ax.plot(obs_lon, obs_lat, 'w*', ms=14, mec='k', mew=1.2,
                    label='obs')
        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Longitude')
        ax.set_aspect('equal', adjustable='box')

    axes[0].set_ylabel('Latitude')
    cbar = fig.colorbar(pcm, ax=axes, orientation='horizontal',
                        shrink=0.6, pad=0.08, aspect=40)
    cbar.set_label('Surface turbidity (NTU)')

    fig.suptitle('Surface turbidity — spatial snapshots', fontsize=13)

    out_path = os.path.join(out_dir, 'turbidity_3d_spatial.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {out_path}")


def compare(turb_file, grd_file, obs_lon, obs_lat, out_dir=None, obs_file=None):
    """Extract time-series at an observation point and plot diagnostics."""

    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(turb_file))

    # --- Load observations (optional) ---
    obs_times_dt = None
    obs_ntu = None
    if obs_file is not None and os.path.exists(obs_file):
        import pandas as pd
        print(f"Loading observations from {obs_file}...")
        obs_df = pd.read_csv(obs_file, header=None, usecols=[0, 1],
                             names=['time', 'ntu'])
        obs_df['time'] = pd.to_datetime(obs_df['time'])
        obs_df = obs_df.dropna(subset=['ntu'])
        obs_times_dt = obs_df['time'].values.astype('datetime64[s]').astype(datetime)
        obs_ntu = obs_df['ntu'].values
        print(f"  {len(obs_ntu)} obs, NTU range: [{obs_ntu.min():.1f}, {obs_ntu.max():.1f}]")

    ds = xr.open_dataset(turb_file)
    j_obs, i_obs = find_nearest_point(grd_file, obs_lon, obs_lat)
    print(f"Obs column: j={j_obs}, i={i_obs}")

    times = ds['time'].values
    C_bg = ds.attrs['C_bg']
    C_surf = ds['C_surface'].values[:, j_obs, i_obs]
    C_bot = ds['C_bottom'].values[:, j_obs, i_obs]
    C_bot_pc = ds['C_bottom_per_class'].values[:, :, j_obs, i_obs]  # (n_class, nt)
    tau = ds['tau_max'].values[:, j_obs, i_obs]
    mass = ds['mass'].values

    # Reconstruct tau_cr from attrs for plotting
    tau_cr = []
    ic = 0
    while f'tau_cr_{ic}' in ds.attrs:
        tau_cr.append(ds.attrs[f'tau_cr_{ic}'])
        ic += 1

    ds.close()

    # --- Plot ---
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    times_dt = times.astype('datetime64[s]').astype(datetime)

    ax = axes[0]
    ax.plot(times_dt, tau, 'k-', lw=1)
    for ic, tc in enumerate(tau_cr):
        ax.axhline(tc, ls='--', alpha=0.5,
                    label=f"tau_cr {CLASS_NAMES[ic]}={tc:.3f}")
    ax.set_ylabel('Bed stress (N/m²)')
    ax.legend(fontsize=8)
    ax.set_title('Bed stress at observation point')

    ax = axes[1]
    ax.plot(times_dt, C_surf, label='Model surface', lw=1.5, color='C0')
    ax.plot(times_dt, C_bot, label='Model bottom', lw=1.5, color='C1')
    if obs_times_dt is not None:
        ax.plot(obs_times_dt, obs_ntu, 'o', color='k', ms=3,
                label='Obs', alpha=0.7)
    ax.set_ylabel('Turbidity (NTU)')
    ax.legend(fontsize=8)
    ax.set_title('Turbidity at observation point')

    # Panel 3: per-class contribution at bottom (stacked)
    ax = axes[2]
    n_class = C_bot_pc.shape[0]
    class_colors = ['#4c78a8', '#f58518']  # fine, coarse
    bottom = np.full_like(C_bot_pc[0], C_bg, dtype=float)
    ax.fill_between(times_dt, 0.0, bottom, color='lightgrey',
                    label=f'Background ({C_bg:.1f})', alpha=0.8)
    for ic in range(n_class):
        top = bottom + C_bot_pc[ic]
        ax.fill_between(times_dt, bottom, top,
                        color=class_colors[ic % len(class_colors)],
                        alpha=0.75, label=CLASS_NAMES[ic])
        bottom = top
    if obs_times_dt is not None:
        ax.plot(obs_times_dt, obs_ntu, 'o', color='k', ms=3,
                label='Obs', alpha=0.7)
    ax.set_ylabel('Turbidity (NTU)')
    ax.legend(fontsize=8, loc='upper right')
    ax.set_title('Bottom-layer turbidity — per-class contribution')

    ax = axes[3]
    ax.plot(times_dt, mass, 'k-', lw=1)
    ax.set_ylabel('Total mass (NTU·m³)')
    ax.set_title('Total suspended mass (conservation check)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    plt.tight_layout()
    out_path = os.path.join(out_dir, 'turbidity_3d_diagnostics.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {out_path}")


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Offline 3D sediment transport model')
    subparsers = parser.add_subparsers(dest='command')

    # --- run command ---
    run_parser = subparsers.add_parser('run', help='Run the 3D turbidity model')
    run_parser.add_argument('--croco_file', required=True)
    run_parser.add_argument('--ww3_file', required=True)
    run_parser.add_argument('--grd_file', required=True)
    run_parser.add_argument('--yorig', type=int, required=True)
    run_parser.add_argument('--out_dir', default=None)
    run_parser.add_argument('--out_file', default='turbidity_3d_output.nc',
                            help='Output filename (basename, joined with out_dir)')
    run_parser.add_argument('--ws_fine', type=float, default=1e-4)
    run_parser.add_argument('--ws_coarse', type=float, default=1e-3)
    run_parser.add_argument('--M_fine', type=float, default=0.05)
    run_parser.add_argument('--M_coarse', type=float, default=0.3)
    run_parser.add_argument('--tau_cr_fine', type=float, default=0.1)
    run_parser.add_argument('--tau_cr_coarse', type=float, default=0.2)
    run_parser.add_argument('--C_bg', type=float, default=3.0)
    run_parser.add_argument('--ini_file', default=None,
        help='Optional restart file (previous turbidity output with C_3d variable)')
    run_parser.add_argument('--ini_time_index', type=int, default=-1,
        help='Time index within --ini_file to load as initial state (default -1, last)')

    # --- compare command ---
    cmp_parser = subparsers.add_parser('compare', help='Extract time-series at a point and plot diagnostics')
    cmp_parser.add_argument('--turb_file', required=True, help='Turbidity output file from run')
    cmp_parser.add_argument('--grd_file', required=True)
    cmp_parser.add_argument('--obs_lon', type=float, required=True)
    cmp_parser.add_argument('--obs_lat', type=float, required=True)
    cmp_parser.add_argument('--out_dir', default=None)
    cmp_parser.add_argument('--obs_file', default=None,
                            help='Optional CSV of observations (time,ntu)')

    # --- spatial command ---
    sp_parser = subparsers.add_parser('spatial',
        help='Three spatial snapshots of surface turbidity')
    sp_parser.add_argument('--turb_file', required=True)
    sp_parser.add_argument('--grd_file', required=True)
    sp_parser.add_argument('--out_dir', default=None)
    sp_parser.add_argument('--times', nargs=3, default=None,
        help="Three times as 'YYYY-MM-DDTHH' (optional — auto if omitted)")
    sp_parser.add_argument('--obs_lon', type=float, default=None)
    sp_parser.add_argument('--obs_lat', type=float, default=None)
    sp_parser.add_argument('--vmax', type=float, default=None)

    args = parser.parse_args()

    if args.command == 'run':
        params = {
            'ws': np.array([args.ws_fine, args.ws_coarse]),
            'M': np.array([args.M_fine, args.M_coarse]),
            'tau_cr': np.array([args.tau_cr_fine, args.tau_cr_coarse]),
            'C_bg': args.C_bg,
        }
        run(args.croco_file, args.ww3_file, args.grd_file, args.yorig,
            params=params, out_dir=args.out_dir, out_file_name=args.out_file,
            ini_file=args.ini_file, ini_time_index=args.ini_time_index)
    elif args.command == 'compare':
        compare(args.turb_file, args.grd_file, args.obs_lon, args.obs_lat,
                out_dir=args.out_dir, obs_file=args.obs_file)
    elif args.command == 'spatial':
        plot_spatial(args.turb_file, args.grd_file, times=args.times,
                     out_dir=args.out_dir,
                     obs_lon=args.obs_lon, obs_lat=args.obs_lat,
                     vmax=args.vmax)
    else:
        parser.print_help()
