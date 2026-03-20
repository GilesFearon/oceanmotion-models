# WW3 Hindcast Configurations — Persian Gulf (gulf_01)

WW3 v6.07.1 hindcast simulations on a curvilinear grid (291x131) derived from the CROCO gulf_01 rho grid.

## Directories

- **GRID/** — WW3 grid files (lon.dat, lat.dat, depth.dat, mask.dat) generated from the CROCO grid using `croco_grd_2_ww3()`.

- **SPEC_CMEMS/** — Spectral boundary condition files reconstructed from CMEMS wave partition data, used by `ww3_bounc` to force the open boundaries.

- **RUN_01/** — Wind-only forcing (ERA5). Covers May 2016 onwards. This is the baseline configuration with no ocean current or water level input.

- **RUN_02/** — Wind (ERA5) + ocean current + water level forcing from CROCO (C04_I01_GLORYS_ERA5). Covers Jan–Dec 2016. Currents are east/north components preprocessed from CROCO surface output using `croco_srf_2_ww3()`. DTKTH reduced from 120s to 60s for current forcing stability.
