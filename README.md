# oceanmotion-models

Operational CROCO ocean forecast system for the Gulf domain.

## Prerequisites

- **Docker** — used for data downloads and Python preprocessing (somisana images)
- **gfortran + mpich** — used for compiling and running CROCO
- **ncdump** (from netCDF) — used by the restart fallback logic
- **TPXO10 atlas files** — placed in `data/TPXO10/`
- **CROCO v1.3.1 source code** — path configured in `configs/.../forecast/myenv_frcst.sh`
- **Copernicus credentials** — set `COPERNICUS_USERNAME` and `COPERNICUS_PASSWORD` in `.env`

## Repository structure

```
my_env.sh                          # Shared configuration (sourced by all scripts)
.env                               # Credentials (not committed)

download/
  download_GFS.sh                  # Download GFS atm forcing + reformat for CROCO
  download_MERCATOR.sh             # Download MERCATOR ocean data

croco_ops/
  make_tides.sh                    # Generate tidal forcing (TPXO10)
  make_bry_ini.sh                  # Generate boundary + initial conditions (MERCATOR)
  compile.sh                       # Compile CROCO executable
  run_croco.sh                     # Set up inputs, generate croco.in, run model, archive output

configs/{DOMAIN}/{MODEL}/forecast/
  GRID/croco_grd.nc                # Model grid
  TPXO10/crocotools_param.py       # Tidal preprocessing config
  MERCATOR/crocotools_param.py     # OGCM preprocessing config
  C06/cppdefs.h, param_.h          # Compilation options
  I01/croco_fcst.in                # Runtime input template
  I01/myenv_in.sh                  # Time-stepping parameters (DT, output frequencies)
  myenv_frcst.sh                   # MPI config + CROCO source path
  jobcomp_frcst.sh                 # Compilation script

data/                              # Runtime data (not committed)
  TPXO10/                          # Raw tidal atlas files
  downloads/{RUN_DATE}/            # Downloaded forcing data
  croco_ops/{RUN_DATE}/{DOMAIN}/{MODEL}/  # Preprocessed inputs + model output
```

## Configuration

All scripts source `my_env.sh`, which defines defaults using the `${VAR:-default}` pattern. Override any variable by setting it before running a script:

| Variable | Default | Description |
|---|---|---|
| `RUN_DATE` | auto (current UTC, 12h cycle) | Run date as `YYYYMMDD_HH` |
| `HDAYS` | `0` | Hindcast days |
| `FDAYS` | `7` | Forecast days |
| `YORIG` | `2000` | CROCO time origin year |
| `DOMAIN` | `gulf_01` | Domain identifier |
| `MODEL` | `croco_v1.3.1` | Model version identifier |
| `COMP` | `C06` | Compilation option set |
| `INP` | `I01` | Runtime input configuration |
| `OGCM` | `MERCATOR` | Ocean boundary data source |
| `BLK` | `GFS` | Atmospheric bulk forcing source |
| `TIDE_FRC` | `TPXO10` | Tidal forcing source |
| `DOMAIN_DOWNLOAD` | `45,60,21,33` | Download bounding box (lon_min,lon_max,lat_min,lat_max) |

All derived paths (`CONFIG_DIR`, `DOWNLOAD_DIR`, `OPS_DIR`, etc.) are also overridable.

## Running a forecast

### 1. Set credentials and run date

```bash
source .env
export RUN_DATE=20260317_00
```

### 2. Download forcing data

These can run in parallel:

```bash
bash download/download_GFS.sh
bash download/download_MERCATOR.sh
```

`download_GFS.sh` does two things: downloads raw GFS grib files, then reformats them to CROCO-compatible netCDF (saved to `data/downloads/{RUN_DATE}/GFS/for_croco/`).

`download_MERCATOR.sh` downloads the MERCATOR ocean analysis/forecast file (saved to `data/downloads/{RUN_DATE}/MERCATOR/`).

### 3. Preprocess forcing

These can run in parallel (after downloads complete):

```bash
bash croco_ops/make_tides.sh
bash croco_ops/make_bry_ini.sh
```

`make_tides.sh` generates tidal forcing from TPXO10 atlas data.

`make_bry_ini.sh` generates initial conditions and boundary conditions from the downloaded MERCATOR data.

### 4. Compile CROCO

Only needed once, or when `cppdefs.h` / `param_.h` change:

```bash
bash croco_ops/compile.sh
```

### 5. Run the model

```bash
bash croco_ops/run_croco.sh
```

This script:
1. Creates a scratch directory under `data/croco_ops/{RUN_DATE}/{DOMAIN}/{MODEL}/{RUN_NAME}/`
2. Searches for a restart file from a previous run (up to 20 x 6-hour steps back). Falls back to the MERCATOR ini file if none found.
3. Copies all input files (grid, forcing, boundary, bulk, executable) into scratch
4. Generates `croco.in` from the template by substituting time-stepping parameters
5. Runs CROCO via `mpirun`
6. Verifies completion and archives output (his, avg, rst, surface files) to the output directory

### 6. Check outputs

```bash
ls data/downloads/${RUN_DATE}/GFS/for_croco/
ls data/downloads/${RUN_DATE}/MERCATOR/
ls data/croco_ops/${RUN_DATE}/gulf_01/croco_v1.3.1/TPXO10/
ls data/croco_ops/${RUN_DATE}/gulf_01/croco_v1.3.1/MERCATOR/
ls data/croco_ops/${RUN_DATE}/gulf_01/croco_v1.3.1/C06_I01_MERCATOR_TPXO10/output/
```

## Output directory structure

```
data/
  downloads/{RUN_DATE}/
    GFS/                           # Raw .grb files
      for_croco/                   # Reformatted .nc files (online bulk forcing)
    MERCATOR/                      # MERCATOR_{RUN_DATE}.nc

  croco_ops/{RUN_DATE}/{DOMAIN}/{MODEL}/
    TPXO10/                        # croco_frc_TPXO10_{RUN_DATE}.nc
    MERCATOR/                      # croco_ini_MERCATOR_{RUN_DATE}.nc
                                   # croco_bry_MERCATOR_{RUN_DATE}.nc
    C06_I01_MERCATOR_TPXO10/
      scratch/                     # All inputs copied here for the run
      output/                      # croco_his.nc, croco_avg.nc, croco_rst.nc,
                                   # croco_his_surf.nc, croco_avg_surf.nc
```

## Running multiple configurations

The naming convention allows running different configurations side by side:

```bash
# Different domain
DOMAIN=gulf_02 bash croco_ops/make_tides.sh

# Different forcing sources
OGCM=HYCOM TIDE_FRC=FES2014 bash croco_ops/run_croco.sh

# Different compilation + input options
COMP=C07 INP=I02 bash croco_ops/run_croco.sh
```

Each combination produces a unique output path under `data/croco_ops/`.

## Architecture

Python preprocessing (tides, boundary/initial conditions, GFS reformatting) runs inside Docker containers using the [somisana-croco](https://github.com/SAEON/somisana-croco) CLI image. This avoids managing Python dependencies on the host.

Compilation and model execution run directly on the host using the local `gfortran`/`mpich` toolchain, as CROCO requires HPC-grade MPI for production runs.
