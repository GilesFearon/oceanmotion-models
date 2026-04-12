"""
1DV two-class vertical sediment transport model.

Solves the vertical advection-diffusion-settling equation for 2 sediment classes
on the CROCO sigma grid, with Soulsby (1997) combined wave-current bed stress
driving erosion at the bed.

Two-class system (motivated by 5-class calibration that collapsed to 2 active classes):
  - Fine (washload): slow-settling, maintains background turbidity between events
  - Coarse (resuspension): fast-settling, drives storm/event peaks

Usage:
    # Step 1: Extract CROCO full profile (requires somisana_croco conda env)
    conda run -n somisana_croco python dev_1dv_model.py extract_croco

    # Step 2: Extract WW3 data (requires wavespectra conda env)
    conda run -n wavespectra python dev_1dv_model.py extract_ww3

    # Step 3: Run 1DV model (no special env needed)
    python dev_1dv_model.py run

References:
    Soulsby, R.L. (1997) "Dynamics of Marine Sands", Thomas Telford, London.
    Partheniades, E. (1965) "Erosion and deposition of cohesive soils", J. Hydraul. Div.
    Winterwerp, J.C. & van Kesteren, W.G.M. (2004) "Introduction to the physics of
        cohesive sediment in the marine environment", Elsevier.
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# =============================================================================
# Physical constants
# =============================================================================

RHO_W = 1025.0    # seawater density (kg/m^3)
KS = 0.001         # Nikuradse bed roughness (m) - fine sand/silt
Z0 = KS / 30.0     # hydrodynamic roughness length (m)
KAPPA = 0.4         # von Karman constant


# =============================================================================
# Soulsby (1997) bed stress
# =============================================================================

def dispersion(omega, d, g=9.81, tol=1e-8, max_iter=50):
    """Solve the linear wave dispersion relation omega^2 = g*k*tanh(k*d)."""
    k = omega**2 / (g * np.sqrt(np.tanh(omega**2 * d / g)))
    for _ in range(max_iter):
        f = omega**2 - g * k * np.tanh(k * d)
        dfdk = -g * (np.tanh(k * d) + k * d * (1 - np.tanh(k * d)**2))
        dk = -f / dfdk
        k += dk
        if abs(dk) < tol:
            break
    return k


def correct_ubr_for_depth(ubr, t0m1, d_model, d_obs, g=9.81, max_factor=3.0):
    """Scale WW3 bottom orbital velocity from model grid depth to observed depth."""
    ubr_corrected = np.copy(ubr)
    for i in range(len(ubr)):
        if ubr[i] <= 0 or t0m1[i] <= 0:
            continue
        omega = 2 * np.pi / t0m1[i]
        k = dispersion(omega, d_model, g)
        sinh_model = np.sinh(k * d_model)
        sinh_obs = np.sinh(k * d_obs)
        if sinh_obs > 1e-10:
            factor = min(sinh_model / sinh_obs, max_factor)
            ubr_corrected[i] = ubr[i] * factor
    return ubr_corrected


def soulsby_combined_stress(u_bot, v_bot, ubr, t0m1, wave_dir,
                            z_bot, z0=Z0, rho=RHO_W):
    """
    Compute combined wave-current bed stress using Soulsby (1997) DATA2 method.

    Parameters
    ----------
    u_bot, v_bot : array
        Near-bed current velocity components (m/s), east and north.
    ubr : array
        RMS bottom orbital velocity from WW3 (m/s).
    t0m1 : array
        Mean wave period T0M1 from WW3 (s).
    wave_dir : array
        Mean wave direction (degrees, FROM convention, nautical).
    z_bot : float or array
        Height of the bottom velocity point above the bed (m).
    z0 : float
        Bed roughness length (m).
    rho : float
        Water density (kg/m^3).

    Returns
    -------
    tau_max, tau_mean, tau_c, tau_w : arrays (N/m^2)
    """
    nt = len(u_bot)
    tau_max = np.zeros(nt)
    tau_mean = np.zeros(nt)
    tau_c = np.zeros(nt)
    tau_w = np.zeros(nt)

    U = np.sqrt(u_bot**2 + v_bot**2)
    current_dir = np.degrees(np.arctan2(u_bot, v_bot))

    z_bot = np.maximum(z_bot, z0 * 2.0)
    cd_bot = (KAPPA / np.log(z_bot / z0))**2
    tau_c[:] = rho * cd_bot * U**2

    for i in range(nt):
        if ubr[i] <= 0 or t0m1[i] <= 0:
            tau_max[i] = tau_c[i]
            tau_mean[i] = tau_c[i]
            continue

        A = ubr[i] * t0m1[i] / (2 * np.pi)

        if A > 0:
            A_over_z0 = A / z0
            fw = 1.39 * A_over_z0**(-0.52) if A_over_z0 > 1.57 else 0.3
        else:
            fw = 0.0

        tau_w[i] = 0.5 * rho * fw * ubr[i]**2

        phi = np.radians(wave_dir[i] - current_dir[i] - 180.0)
        tau_c_i = tau_c[i]
        tau_w_i = tau_w[i]

        if tau_c_i + tau_w_i > 0:
            tau_mean[i] = tau_c_i * (
                1.0 + 1.2 * (tau_w_i / (tau_c_i + tau_w_i))**3.2
            )
            tau_max[i] = np.sqrt(
                (tau_mean[i] + tau_w_i * np.cos(phi))**2
                + (tau_w_i * np.sin(phi))**2
            )

    return tau_max, tau_mean, tau_c, tau_w


# =============================================================================
# Configuration
# =============================================================================

OBS_LAT = 24.368937
OBS_LON = 54.072347
OBS_DEPTH = 4.0       # observed depth from surface (m), only used to select comparison level

CROCO_FILE = (
    "/home/gfearon/code/oceanmotion-models/configs/gulf_01/croco_v1.3.1/"
    "hindcast/C04_I02_GLORYS_ERA5/output/croco_avg_Y2022M01.nc"
)
CROCO_GRD = (
    "/home/gfearon/code/oceanmotion-models/configs/gulf_01/croco_v1.3.1/"
    "hindcast/GRID/croco_grd.nc"
)
WW3_FILE = (
    "/home/gfearon/code/oceanmotion-models/configs/gulf_01/ww3_v6.07.1/"
    "hindcast/RUN_02/output/ww3.202201.nc"
)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CROCO_PROFILE = os.path.join(DATA_DIR, 'croco_profile.nc')
WW3_EXTRACTED = os.path.join(DATA_DIR, 'ww3_waves.nc')

OBS_FILE = "/home/gfearon/projects/ocean-motion/data/ntu_obs/NTU_obs.csv"

# =============================================================================
# Two-class sediment system
# =============================================================================
#
# Physically realistic parameter ranges for shallow Gulf environment
# (fine carbonate/terrigenous sediment, ~4-6 m depth):
#
# Settling velocity (ws) [m/s]:
#   Fine (flocculated clay/fine silt): 0.01-0.5 mm/s  (1e-5 to 5e-4 m/s)
#   Coarse (medium silt):              0.5-5 mm/s     (5e-4 to 5e-3 m/s)
#   Ref: Winterwerp & van Kesteren (2004), Soulsby (1997) Table 4.1
#
# Critical bed shear stress (tau_cr) [N/m^2]:
#   Freshly deposited mud:  0.05-0.2
#   Consolidated mud:       0.2-1.0
#   Mixed sand/mud:         0.1-0.5
#   Ref: Soulsby (1997) eq. 107, Whitehouse et al. (2000)
#
# Erosion rate (M) [NTU m/s]:
#   Cohesive sediments: equivalent to ~1e-5 to 1e-3 kg/m^2/s
#   In NTU units (assuming ~1 NTU per ~1 mg/L): 0.01-1.0 NTU m/s
#   Ref: Partheniades (1965), Sanford & Maa (2001)
#
# Background concentration (C_bg) [NTU]:
#   Gulf waters in calm conditions: 1-5 NTU
#
# Power-law exponent (alpha) for tau_cr scaling with ws:
#   tau_cr_i = tau_cr_ref * (ws_i / ws_ref)^alpha
#   Typical range: 0.3-0.7
#   Ref: Soulsby (1997), Whitehouse et al. (2000)
#

N_CLASSES = 2
CLASS_NAMES = ['Fine (washload)', 'Coarse (resuspension)']

# Default parameters — physically realistic values
DEFAULT_PARAMS = {
    'ws': np.array([1e-4, 1e-3]),       # settling velocity (m/s): 0.1 and 1.0 mm/s
    'M': np.array([0.05, 0.3]),          # erosion rate per class (NTU m/s)
    'tau_cr': np.array([0.1, 0.2]),      # critical bed shear stress per class (N/m^2)
    'C_bg': 3.0,                         # background concentration (NTU)
}


# =============================================================================
# Step 1: Extract CROCO full profile (run in somisana_croco env)
# =============================================================================

def extract_croco():
    """Extract full vertical profile at obs location."""
    sys.path.insert(0, '/home/gfearon/code/somisana-croco')
    from crocotools_py.postprocess import get_ts, get_ts_uv

    print(f"Extracting CROCO profile at ({OBS_LAT}N, {OBS_LON}E)...")

    # Full velocity profile (all sigma levels, rotated to east/north)
    print("  Extracting u, v (all levels)...")
    ds_out = get_ts_uv(CROCO_FILE, OBS_LON, OBS_LAT,
                       Yorig=1993, grdname=CROCO_GRD,
                       level=slice(None))

    # AKs — vertical diffusivity (on s_w grid)
    print("  Extracting AKs (all levels)...")
    ds_aks = get_ts(CROCO_FILE, 'AKs', OBS_LON, OBS_LAT,
                    Yorig=1993, grdname=CROCO_GRD,
                    level=slice(None))

    # Add AKs
    ds_out['AKs'] = ds_aks['AKs']

    # Save updated file
    ds_out.to_netcdf(CROCO_PROFILE + '.tmp')
    ds_out.close()
    os.replace(CROCO_PROFILE + '.tmp', CROCO_PROFILE)

    print(f"  Saved to: {CROCO_PROFILE}")

# =============================================================================
# Step 2: Extract WW3 data (run in wavespectra env)
# =============================================================================

def extract_ww3():
    """Extract wave parameters at obs location."""
    sys.path.insert(0, '/home/gfearon/code/somisana-ww3')
    from ww3_tools.postprocess import get_ts as ww3_get_ts

    print(f"Extracting WW3 wave parameters at ({OBS_LAT}N, {OBS_LON}E)...")
    ds = ww3_get_ts(WW3_FILE, OBS_LON, OBS_LAT, nc_out=WW3_EXTRACTED)
    print(f"  Saved to: {WW3_EXTRACTED}")

# =============================================================================
# 1DV solver
# =============================================================================

def solve_1dv_implicit(C, Kz_w, ws, Hz, dt, erosion_flux):
    """
    One timestep of implicit vertical diffusion + upwind settling.

    Solves on the sigma grid with:
    - C on rho levels (cell centres), shape (N_rho,)
    - Kz on w levels (cell interfaces), shape (N_w,) = (N_rho+1,)
    - Hz = layer thicknesses at rho levels, shape (N_rho,)

    Index convention: k=0 is bottom, k=N_rho-1 is surface.
    Kz_w[0] = bed interface, Kz_w[N_rho] = surface interface.

    Boundary conditions:
    - Bed (k=0 lower face): erosion flux = E (NTU m/s)
    - Surface (k=N_rho upper face): zero flux

    Parameters
    ----------
    C : array (N_rho,)
        Concentration at current timestep.
    Kz_w : array (N_w,)
        Vertical diffusivity at w levels (m^2/s).
    ws : float
        Settling velocity for this class (m/s, positive downward).
    Hz : array (N_rho,)
        Layer thicknesses (m).
    dt : float
        Timestep (s).
    erosion_flux : float
        Erosion flux at the bed (NTU m/s).

    Returns
    -------
    C_new : array (N_rho,)
        Concentration at next timestep.
    """
    N = len(C)
    a = np.zeros(N)  # sub-diagonal
    b = np.zeros(N)  # diagonal
    c = np.zeros(N)  # super-diagonal
    d = np.zeros(N)  # RHS

    for k in range(N):
        b[k] = 1.0

        # Diffusion: implicit at interfaces bounding cell k
        if k > 0:
            dz_lower = 0.5 * (Hz[k-1] + Hz[k])
            diff_lower = Kz_w[k] / dz_lower
            a[k] = -dt * diff_lower / Hz[k]
            b[k] += dt * diff_lower / Hz[k]
        if k < N - 1:
            dz_upper = 0.5 * (Hz[k] + Hz[k+1])
            diff_upper = Kz_w[k+1] / dz_upper
            c[k] = -dt * diff_upper / Hz[k]
            b[k] += dt * diff_upper / Hz[k]

        # Settling: implicit upwind (sediment falls from k+1 to k)
        b[k] += dt * ws / Hz[k]  # loss through lower face
        if k < N - 1:
            c[k] -= dt * ws / Hz[k]  # gain from cell above

        d[k] = C[k]

    # Bed boundary: erosion flux into bottom cell
    d[0] += dt * erosion_flux / Hz[0]

    C_new = thomas_solve(a, b, c, d)
    return np.maximum(C_new, 0.0)


def thomas_solve(a, b, c, d):
    """Solve tridiagonal system using Thomas algorithm."""
    n = len(d)
    c_ = np.zeros(n)
    d_ = np.zeros(n)

    c_[0] = c[0] / b[0]
    d_[0] = d[0] / b[0]

    for i in range(1, n):
        m = a[i] / (b[i] - a[i] * c_[i-1])
        c_[i] = c[i] / (b[i] - a[i] * c_[i-1])
        d_[i] = (d[i] - a[i] * d_[i-1]) / (b[i] - a[i] * c_[i-1])

    x = np.zeros(n)
    x[-1] = d_[-1]
    for i in range(n-2, -1, -1):
        x[i] = d_[i] - c_[i] * x[i+1]

    return x


def run_1dv_model(times_sec, tau_max, Kz_profiles, Hz_profiles,
                  z_r_profiles, params, dt=3600.0):
    """
    Run the two-class 1DV model.

    Parameters
    ----------
    times_sec : array (nt,)
        Time in seconds from start.
    tau_max : array (nt,)
        Maximum combined bed stress (N/m^2).
    Kz_profiles : array (nt, N_w)
        Vertical diffusivity at w levels for each timestep.
    Hz_profiles : array (nt, N_rho)
        Layer thicknesses for each timestep.
    z_r_profiles : array (nt, N_rho)
        Heights at rho levels (m, relative to MSL) for each timestep.
    params : dict
        Model parameters: ws, M, tau_cr, C_bg.

    Returns
    -------
    C_total : array (nt, N_rho)
        Total concentration at all levels and times (NTU), including C_bg.
    C_classes : array (nt, N_classes, N_rho)
        Per-class resuspension concentration (excludes C_bg).
    """
    nt = len(times_sec)
    N_rho = Hz_profiles.shape[1]

    ws = params['ws']
    M = params['M']
    tau_cr = params['tau_cr']
    C_bg = params['C_bg']

    # Initialise: zero resuspension concentration (C_bg added at end)
    C = np.zeros((N_CLASSES, N_rho))

    C_total = np.zeros((nt, N_rho))
    C_classes = np.zeros((nt, N_CLASSES, N_rho))
    C_total[0, :] = C_bg

    for t in range(1, nt):
        actual_dt = times_sec[t] - times_sec[t-1]
        Kz_w = Kz_profiles[t, :]
        Hz = Hz_profiles[t, :]
        tau = tau_max[t]

        for ic in range(N_CLASSES):
            # Partheniades erosion: E = M * max(tau/tau_cr - 1, 0)
            excess = max(tau / tau_cr[ic] - 1.0, 0.0)
            E_i = M[ic] * excess

            C[ic, :] = solve_1dv_implicit(
                C[ic, :], Kz_w, ws[ic], Hz, actual_dt, E_i
            )

        C_classes[t, :, :] = C.copy()
        C_total[t, :] = C.sum(axis=0) + C_bg

    return C_total, C_classes


# =============================================================================
# Plotting
# =============================================================================

def plot_diagnostics(times, tau_max, tau_c, tau_w, C_total, C_classes,
                     z_r, obs_k, obs_times=None, obs_ntu=None, params=None):
    """4-panel diagnostics: bed stress, NTU at obs depth, class contributions, profiles."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 14), sharex=False)

    times_dt = times.astype('datetime64[s]').astype(datetime)

    # Panel 1: Bed stress with critical thresholds
    ax = axes[0]
    ax.plot(times_dt, tau_c, label=r'$\tau_c$', alpha=0.8)
    ax.plot(times_dt, tau_w, label=r'$\tau_w$', alpha=0.8)
    ax.plot(times_dt, tau_max, label=r'$\tau_{max}$', color='k', lw=1.5)
    if params is not None:
        for ic in range(N_CLASSES):
            ax.axhline(params['tau_cr'][ic], ls='--', alpha=0.5,
                        label=rf'$\tau_{{cr}}$ {CLASS_NAMES[ic]}={params["tau_cr"][ic]:.3f}')
    ax.set_ylabel('Bed stress (N/m²)')
    ax.legend(loc='upper right', fontsize=8)
    ax.set_title('Soulsby (1997) combined wave-current bed stress')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    # Panel 2: Total NTU at obs depth vs observations
    ax = axes[1]
    ax.plot(times_dt, C_total[:, obs_k], label='1DV model', color='C2', lw=1.5)
    if obs_times is not None and obs_ntu is not None:
        obs_dt = obs_times.astype('datetime64[s]').astype(datetime)
        ax.plot(obs_dt, obs_ntu, 'o', color='k', ms=3, label='Obs', alpha=0.7)
    ax.set_ylabel('Turbidity (NTU)')
    ax.legend(loc='upper right')
    ax.set_title(f'Total NTU at observation depth (level {obs_k})')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    # Panel 3: Per-class contribution at obs depth
    ax = axes[2]
    C_bg = params['C_bg'] if params else 0
    bottom = np.full(len(times_dt), C_bg)
    for ic in range(N_CLASSES):
        top = bottom + C_classes[:, ic, obs_k]
        ax.fill_between(times_dt, bottom, top, alpha=0.7, label=CLASS_NAMES[ic])
        bottom = top
    ax.set_ylabel('Turbidity (NTU)')
    ax.legend(loc='upper right', fontsize=8)
    ax.set_title('Per-class contribution at observation depth')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    # Panel 4: Vertical profiles at peak stress time
    ax = axes[3]
    t_peak = np.argmax(tau_max)
    z_profile = z_r[t_peak, :]
    for ic in range(N_CLASSES):
        ax.plot(C_classes[t_peak, ic, :], z_profile, label=CLASS_NAMES[ic])
    ax.plot(C_total[t_peak, :], z_profile, 'k-', lw=2, label='Total')
    ax.set_xlabel('Concentration (NTU)')
    ax.set_ylabel('Depth (m, relative to MSL)')
    ax.legend(loc='best', fontsize=8)
    ax.set_title(f'Vertical profiles at peak stress '
                 f'({times[t_peak].astype("datetime64[h]")})')

    plt.tight_layout()
    out_path = os.path.join(DATA_DIR, 'turbidity_1dv_diagnostics.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    #plt.show()
    print(f"Saved: {out_path}")


# =============================================================================
# Step 3: Run
# =============================================================================

def get_obs_level_idx(z_r, obs_depth_below_surface):
    """Find sigma level nearest to observation depth below surface."""
    mean_z = z_r.mean(axis=0)
    surface = mean_z[-1]
    target = surface - obs_depth_below_surface
    return np.argmin(np.abs(mean_z - target))


def run():
    """Load data, compute bed stress, and run 1DV model."""
    import xarray as xr

    # --- Load CROCO profile ---
    print(f"Loading CROCO profile from {CROCO_PROFILE}...")
    ds = xr.open_dataset(CROCO_PROFILE)
    print(f"  Variables: {list(ds.data_vars)}")
    print(f"  Dimensions: {dict(ds.dims)}")

    u_all = ds['u'].values
    v_all = ds['v'].values
    z_r = ds['depth'].values
    Kz_profiles = ds['AKs'].values
    croco_times = ds['time'].values
    ds.close()

    nt = len(croco_times)
    N_rho = z_r.shape[1]
    N_w = N_rho + 1

    u_bot = u_all[:, 0]
    v_bot = v_all[:, 0]

    # Reconstruct w levels and layer thicknesses from rho-level depths
    z_w = np.zeros((nt, N_w))
    z_w[:, 0] = 2 * z_r[:, 0] - z_r[:, 1]
    z_w[:, -1] = 2 * z_r[:, -1] - z_r[:, -2]
    for k in range(1, N_rho):
        z_w[:, k] = 0.5 * (z_r[:, k-1] + z_r[:, k])
    Hz = np.diff(z_w, axis=1)

    Kz_profiles = np.maximum(Kz_profiles, 1e-6)

    print(f"  Grid: {N_rho} rho levels, {N_w} w levels")
    print(f"  Hz range: [{Hz.min():.4f}, {Hz.max():.4f}] m")
    print(f"  Kz range: [{Kz_profiles.min():.2e}, {Kz_profiles.max():.2e}] m²/s")

    # --- Load WW3 data and interpolate onto CROCO times ---
    print(f"\nLoading WW3 data from {WW3_EXTRACTED}...")
    ds_ww3 = xr.open_dataset(WW3_EXTRACTED)
    ww3_times = ds_ww3['time'].values

    # Convert to seconds for interpolation
    t_ref = min(croco_times[0], ww3_times[0])
    croco_sec = (croco_times - t_ref) / np.timedelta64(1, 's')
    ww3_sec = (ww3_times - t_ref) / np.timedelta64(1, 's')

    uubr = np.interp(croco_sec, ww3_sec, ds_ww3['uubr'].values)
    vubr = np.interp(croco_sec, ww3_sec, ds_ww3['vubr'].values)
    ubr = np.sqrt(uubr**2 + vubr**2)
    t0m1 = np.interp(croco_sec, ww3_sec, ds_ww3['t0m1'].values)
    # Interpolate direction components to avoid wrapping issues
    wave_dir_rad = np.deg2rad(ds_ww3['dir'].values)
    dir_sin = np.interp(croco_sec, ww3_sec, np.sin(wave_dir_rad))
    dir_cos = np.interp(croco_sec, ww3_sec, np.cos(wave_dir_rad))
    wave_dir = np.rad2deg(np.arctan2(dir_sin, dir_cos)) % 360.0
    ds_ww3.close()

    times = croco_times
    print(f"  Interpolated WW3 ({len(ww3_sec)} steps) onto CROCO ({len(croco_sec)} steps)")

    # --- Compute bed stress ---
    z_bot = z_w[:, 1] - z_w[:, 0]
    print(f"\nComputing Soulsby (1997) bed stress (z_bot mean={z_bot.mean():.4f} m)...")
    tau_max, tau_mean, tau_c, tau_w = soulsby_combined_stress(
        u_bot, v_bot, ubr, t0m1, wave_dir,
        z_bot=z_bot, z0=Z0
    )
    print(f"  tau_max range: [{tau_max.min():.4f}, {tau_max.max():.4f}] N/m²")

    # --- Load observations ---
    print(f"\nLoading observations from {OBS_FILE}...")
    obs_df = pd.read_csv(OBS_FILE, header=None, usecols=[0, 1],
                         names=['time', 'ntu'])
    obs_df['time'] = pd.to_datetime(obs_df['time'])
    obs_df = obs_df.dropna(subset=['ntu'])
    obs_times_dt64 = obs_df['time'].values.astype('datetime64[ns]')
    obs_ntu = obs_df['ntu'].values
    print(f"  {len(obs_ntu)} observations, NTU range: [{obs_ntu.min():.1f}, {obs_ntu.max():.1f}]")

    # Convert times to seconds
    times_sec = (times - times[0]) / np.timedelta64(1, 's')
    times_sec = times_sec.astype(float)

    # --- Find observation level ---
    obs_k = get_obs_level_idx(z_r, OBS_DEPTH)
    print(f"\n  Observation level index: {obs_k} "
          f"(z_r ~ {z_r.mean(axis=0)[obs_k]:.2f} m)")

    # --- Run model ---
    params = DEFAULT_PARAMS
    print("\nRunning 1DV model with parameters:")
    for ic in range(N_CLASSES):
        print(f"  {CLASS_NAMES[ic]}: ws={params['ws'][ic]*1000:.2f} mm/s, "
              f"M={params['M'][ic]:.3f} NTU·m/s, "
              f"tau_cr={params['tau_cr'][ic]:.3f} N/m²")
    print(f"  C_bg={params['C_bg']:.1f} NTU")

    C_total, C_classes = run_1dv_model(
        times_sec, tau_max, Kz_profiles, Hz, z_r, params
    )
    print(f"  C_total at obs level: [{C_total[:, obs_k].min():.2f}, "
          f"{C_total[:, obs_k].max():.2f}] NTU")

    # --- Plot ---
    plot_diagnostics(
        times, tau_max, tau_c, tau_w, C_total, C_classes,
        z_r, obs_k,
        obs_times=obs_times_dt64, obs_ntu=obs_ntu, params=params
    )


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  conda run -n somisana_croco python dev_1dv_model.py extract_croco")
        print("  conda run -n wavespectra python dev_1dv_model.py extract_ww3")
        print("  python dev_1dv_model.py run")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'extract_croco':
        extract_croco()
    elif cmd == 'extract_ww3':
        extract_ww3()
    elif cmd == 'run':
        run()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
