# Turbidity model — baseline calibration session

Date: 2026-04-10
Configuration: Gulf domain, CROCO hindcast C04_I02_GLORYS_ERA5, January 2022
Validation point: (54.0723°E, 24.3689°N)
Observation data: `NTU_obs.csv`, 1-month record

## Session goal

Build a physically defensible baseline for the offline 3D two-class sediment
transport model and calibrate against a single NTU observation record, without
over-fitting.

## Physics fixes (not tuning)

Three genuine bugs were producing unbounded concentrations (~10^13 NTU)
before any calibration could begin:

1. **`cd_bot` singularity in `soulsby_combined_stress_2d`**.
   Original floor of `z0 * 2.0` (~7e-5 m) let `log(z_bot/z0)` approach zero,
   giving `cd_bot` values up to ~0.33 in shallow cells and unphysical
   `tau_c` of hundreds of N/m². Fixed with 1 cm floor and `cd_bot ≤ 0.01`.

2. **`z_bot` passed to stress routine was wrong.**
   The call site used the full bottom-cell thickness `z_w[1] - z_w[0]`
   instead of the height of the velocity point (cell centre) above the bed.
   Fixed to `0.5 * (z_w[1] - z_w[0])`.

3. **No sanity cap on total bed stress.**
   Added `tau_max, tau_mean ≤ 5 N/m²` as a physical guard. 5 N/m² is
   already storm-extreme on the shelf.

## Diagnostic observation

The "10^13" values that first prompted investigation were in the domain-integrated
**mass diagnostic** (units NTU·m³), not concentration. After the physics fixes, the
actual NTU values at the observation point were already in the right order of
magnitude (tens of NTU during storms).

A single persistent hotspot at grid cell (j=98, i=290) continues to drift upward
throughout the run — this is a *distinct* problem (lack of bed-mass supply
limit) and does not affect the obs-point time series.

## Calibration philosophy

Stayed within a strict principle of minimum knobs:

- **`ws` fixed by grain size** via Stokes / settling tube. Not tuned.
  - Fine (washload): 0.1 mm/s — fine silt
  - Coarse (resuspension): 1.0 mm/s — coarse silt / very fine sand
- **`tau_cr` anchored to Shields diagram** for the assumed grain sizes.
  Only small adjustments within the physical envelope allowed.
- **`M_fine` and `M_coarse` treated as the calibration knobs** — these are
  inherently empirical (bed erodibility) and site-dependent.
- **`C_bg` set directly from the observed calm baseline**, not tuned.

Mathematical reason for this discipline: steady-state concentration scales as
`M / ws`, so tuning `M` and `ws` independently is a degenerate two-for-one
calibration. Fixing `ws` leaves one meaningful knob per class.

## Final parameter values

| Parameter       | Value    | Physical source |
|-----------------|----------|-----------------|
| `WS_FINE`       | 1e-4 m/s | Stokes, fine silt ~10 μm |
| `WS_COARSE`     | 1e-3 m/s | Stokes, coarse silt ~60-80 μm |
| `TAU_CR_FINE`   | 0.1 N/m² | Shields, fine silt |
| `TAU_CR_COARSE` | 0.25 N/m²| Shields, upper fine-sand range |
| `M_FINE`        | 3e-4 NTU·m/s | Calibrated |
| `M_COARSE`      | 3e-3 NTU·m/s | Calibrated |
| `C_BG`          | 3.0 NTU  | Observed calm baseline |

## Model-obs agreement (eyeballed)

| Feature                  | Obs       | Model    | Status |
|--------------------------|-----------|----------|--------|
| Calm baseline            | 2–5 NTU   | ~3 NTU   | ✓ Good |
| 5 Jan event peak         | 8–15 NTU  | ~15 NTU  | ✓ Good |
| 21 Jan event peak        | 15–40 NTU | ~30 NTU  | ~ Under on outliers |
| 29 Jan event peak        | 8–12 NTU  | ~12 NTU  | ✓ Good |
| Event timing             | —         | —        | ✓ Tracks correctly |
| Inter-event decay        | Rapid     | Slightly slower | ~ Fine class settles slowly |

## Known limitations

1. **21 Jan peak under-predicted for outlier samples.**
   A few obs reach 40+ NTU for 1-2 samples. Could be instrument spikes,
   short-duration sand-mode resuspension, or bed stress underestimate.
   A 2-class Partheniades model cannot resolve single-sample spikes without
   using non-physical parameters.

2. **No bed-mass supply limit.**
   Erosion is unbounded per cell. Safe for this 1-month run at the obs
   point, but a single hotspot at (j=98, i=290) drifts upward
   monotonically. Must be fixed before month+ runs or spatial analysis of
   the hotspot region.

3. **Single-point calibration.**
   One observation station, one month, one hydrodynamic/wave scenario.
   Calibration is statistically under-constrained — the parameter values
   here should be treated as a first-cut baseline, not a regional
   calibration.

4. **Uniform sediment properties.**
   No spatial variation in `M`, `tau_cr`, or grain size. Real beds are
   patchy (sand pockets, mud flats, biofilms). Best available given data.

5. **Inter-event tail slightly too thick.**
   The fine class settles at ws=0.1 mm/s → column clearing time of order
   days. Real fine sediment may be flocculated (faster effective ws) during
   settling, which the model doesn't capture.

6. **Bed stress errors not quantified.**
   Reliant on WW3 wave fields and CROCO bottom currents. Errors in either
   propagate linearly into erosion forcing.

## What NOT to do next

- **Do not raise `tau_cr_coarse` beyond ~0.25** to match the 21 Jan peak.
  That would leave the Shields envelope for `ws=1 mm/s` and over-fit a
  single event.
- **Do not tune `ws`**. It is a grain-size property, not a free parameter.
- **Do not add more sediment classes** until a second observation site
  is available. Cannot constrain extra degrees of freedom from one record.
- **Do not chase sub-NTU residuals.** Obs scatter is ±5 NTU within events;
  further tuning chases instrument noise.

## Suggested next steps (in priority order)

1. **Implement per-class bed-mass supply limit** (`m_bed[ic, j, i]`,
   decremented by erosion, replenished by deposition). This is the only
   way month+ runs and domain-wide analysis become safe.
2. **Compute objective metrics** on the current baseline: median calm NTU,
   mean event peak, hourly-averaged RMSE, bias. Record them alongside the
   parameter values as the "baseline score" for future regression.
3. **Apply the calibrated parameters unchanged at any other validation
   site** if / when additional data becomes available. Do not recalibrate
   per station — that defeats the purpose of having physically-anchored
   parameters.
4. **Spatial sanity plots** of surface NTU at representative times (calm,
   event peaks) — useful for identifying problem regions (like the
   (98,290) hotspot) and communicating results.
