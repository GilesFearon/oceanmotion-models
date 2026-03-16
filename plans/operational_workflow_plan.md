# Operational Workflow Plan

## Overview

Two-server architecture for running operational ocean forecasts (CROCO, WW3) and serving results via a dashboard. GitHub Actions orchestrates ephemeral compute; a persistent server hosts data and the UI.

## Architecture

```
GitHub Actions (orchestrator, ~4 min/day)
    │
    ├── launch.yml: Provision ephemeral VM, SSH in, start run in background, exit
    └── cleanup.yml: Triggered by callback from Hetzner server on completion
                     → destroy VM, check logs, notify on failure

Persistent Server (always-on, Hetzner CX22)
    ├── Downloads forcing data (GFS, MERCATOR) via cron
    ├── Stores model outputs + run logs
    └── Serves dashboard

Ephemeral Compute Server (Hetzner CCX, created per run from snapshot)
    ├── Pulls forcing from persistent server (private network)
    ├── Runs CROCO + WW3
    ├── Pushes outputs + logs to persistent server (private network)
    └── Triggers cleanup.yml via GitHub API, then gets destroyed
```

### Why Hetzner over AWS
- ~10x cheaper than AWS on-demand for equivalent compute (CCX33 ~€0.06/hr vs c5.4xlarge ~$0.68/hr)
- No data transfer costs (internal traffic free, 20TB/mo outbound included)
- Simpler API, no IAM/VPC/security group overhead, predictable billing
- No spot interruption risk (AWS spot is similarly priced but can terminate mid-run)
- AWS advantage: global presence (Cape Town AZ), larger instance sizes (64+ vCPU), ecosystem
- Hetzner Cloud maxes out at 48 vCPUs (CCX63). If 64+ cores needed later, migrate to AWS — the GitHub Actions orchestration layer stays the same

### Scaling (single-node is the sweet spot)
- Single-node MPI: communication via shared memory, ~95-100% of HPC performance
- Multi-node MPI: cloud interconnect (10-25 Gbps, ~50-100μs) is 10-20x worse than InfiniBand — avoid
- Hetzner CCX line: 2-48 vCPU (€0.02-0.33/hr). Start at 16-32, scale up within single node
- A ~500x500 CROCO grid with 40 levels typically runs ~10-15 min/forecast-day on 32 cores

## Phase A: Persistent Server + Data Downloads + Dashboard (START HERE)

Get the data pipeline and UI working before adding compute.

### Server

- Hetzner CX22 (2 vCPU, 4GB RAM, 40GB disk), ~€4/mo
- Expand disk with Hetzner volume if needed (€0.044/GB/mo)
- Location: `fsn1` (same datacenter as future compute server)

### Data Downloads

**GFS** (atmospheric — wind, pressure, fluxes):
- Source: NOAA NOMADS via HTTP or AWS Open Data (S3, free)
- 0.25° resolution, 4x daily, forecast out to 16 days
- Subset to gulf region on download

**MERCATOR** (ocean — SST, SSH, currents, salinity):
- Source: Copernicus Marine Service (CMEMS) API — free with registration
- Global ocean physics analysis+forecast
- 1/12° resolution, daily analysis + 10-day forecast
- Python toolbox: `copernicusmarine` CLI/API handles auth + subsetting

Both are small once subsetted to the gulf — ~50-200 MB/day total.

### Dashboard

- Start with **Panel + hvPlot/GeoViews** (pure Python, plots xarray directly on interactive maps)
- Later migrate to custom frontend (FastAPI + Leaflet) if needed for public-facing use
- Dashboard auto-refreshes when new data arrives

### Directory Structure on Persistent Server

```
/opt/oceanmotion/
├── download/
│   ├── download_gfs.py        # subset & save GFS for gulf
│   ├── download_mercator.py   # subset & save MERCATOR for gulf
│   └── cron_download.sh       # daily cron entry point
├── data/
│   ├── gfs/
│   │   └── YYYYMMDD_HH/      # one dir per forecast cycle
│   ├── mercator/
│   │   └── YYYYMMDD/          # one dir per day
│   └── model_outputs/         # empty for now, future CROCO/WW3
├── dashboard/
│   ├── app.py                 # Panel/Bokeh app
│   ├── pages/                 # one module per dashboard page
│   └── static/
└── docker-compose.yml         # dashboard + nginx reverse proxy
```

### Deployment

- Dashboard code and download scripts live in the repo
- GitHub Actions deploys on push: SSH into persistent server, pull latest code, restart services
- No manual editing of files on the server

### Schedule (cron on persistent server)

```
02:00 UTC  download_gfs.py        (latest GFS cycle)
02:30 UTC  download_mercator.py   (latest CMEMS data)
03:00 UTC  Dashboard auto-refreshes (reads latest files)
```

## Phase B: Ephemeral Compute Server

Add once the dashboard is working and models are ready.

### Server

- Hetzner CCX33 (16 vCPU, 64GB RAM), ~€0.06/hr
- Created from **snapshot** (pre-compiled CROCO + WW3, no Docker)
- Same datacenter (`fsn1`) as persistent server for private network transfer
- Provisioned and destroyed per run via Hetzner API from GitHub Actions

### Snapshot Pattern

1. Manually provision a Hetzner server, install all deps, compile CROCO and WW3
2. Save as a snapshot (~€0.01/GB/mo storage)
3. Each run: create server from snapshot, run models, destroy
4. Update snapshot when model code changes

### Data Transfer (private network)

Both servers on a Hetzner private network (~10 Gbps, zero cost, <1ms latency):
- Persistent → Ephemeral: forcing data (rsync over private IP)
- Ephemeral → Persistent: model outputs (rsync over private IP)
- Transfer times negligible (seconds for GB-scale data)

### GitHub Actions Workflows

**launch.yml** — triggered daily via cron or manually:

```yaml
name: Launch forecast
on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:
    inputs:
      run_date:
        description: 'YYYYMMDD_HH'
        required: false

jobs:
  launch:
    runs-on: ubuntu-latest
    steps:
      - name: Create Hetzner server from snapshot
        id: server
        run: |
          response=$(curl -s -X POST https://api.hetzner.cloud/v1/servers \
            -H "Authorization: Bearer ${{ secrets.HETZNER_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "name": "forecast-runner",
              "server_type": "ccx33",
              "image": "${{ vars.SNAPSHOT_ID }}",
              "ssh_keys": ["${{ vars.SSH_KEY_ID }}"],
              "location": "fsn1",
              "networks": [${{ vars.NETWORK_ID }}]
            }')
          ip=$(echo $response | jq -r '.server.public_net.ipv4.ip')
          id=$(echo $response | jq -r '.server.id')
          echo "ip=$ip" >> $GITHUB_OUTPUT
          echo "id=$id" >> $GITHUB_OUTPUT

      - name: Wait for server ready
        run: |
          for i in $(seq 1 60); do
            ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
              root@${{ steps.server.outputs.ip }} "echo ready" && break
            sleep 10
          done

      - name: Start forecast in background
        run: |
          ssh root@${{ steps.server.outputs.ip }} \
            "nohup /opt/forecast/run_forecast.sh \
              ${{ inputs.run_date || 'auto' }} \
              ${{ steps.server.outputs.id }} \
              > /tmp/run.log 2>&1 &"
```

**cleanup.yml** — triggered by callback from the Hetzner server:

```yaml
name: Cleanup forecast
on:
  workflow_dispatch:
    inputs:
      server_id:
        required: true
      status:
        required: true
      run_date:
        required: true

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - name: Destroy Hetzner server
        if: always()
        run: |
          curl -s -X DELETE \
            "https://api.hetzner.cloud/v1/servers/${{ inputs.server_id }}" \
            -H "Authorization: Bearer ${{ secrets.HETZNER_TOKEN }}"

      - name: Check logs
        run: |
          ssh user@persistent-server \
            "tail -50 /opt/oceanmotion/data/logs/${{ inputs.run_date }}/run.log"

      - name: Fail if run failed
        if: inputs.status != 'success'
        run: |
          echo "Forecast run failed. Logs:"
          ssh user@persistent-server \
            "tail -100 /opt/oceanmotion/data/logs/${{ inputs.run_date }}/run.log"
          exit 1  # Fails the job → GitHub sends email notification
```

GitHub automatically emails the repo owner on workflow failure (configure in Settings → Notifications).

### Run Script on Ephemeral Server

```bash
#!/bin/bash
# /opt/forecast/run_forecast.sh (baked into snapshot)
RUN_DATE=${1:-$(date +%Y%m%d)}
SERVER_ID=$2
STATUS="success"
LOG_DIR="/opt/forecast/logs/${RUN_DATE}"
mkdir -p "$LOG_DIR"

{
  # Pull forcing from persistent server via private network
  rsync -az 10.0.0.2:/opt/oceanmotion/data/ /opt/forecast/input/
  # Run models
  ./run_croco.sh && ./run_ww3.sh
  # Push outputs back
  rsync -az /opt/forecast/output/ 10.0.0.2:/opt/oceanmotion/data/model_outputs/
} > "$LOG_DIR/run.log" 2>&1 || STATUS="failure"

# Always sync logs and trigger cleanup (even on failure)
rsync -az "$LOG_DIR/" 10.0.0.2:/opt/oceanmotion/data/logs/${RUN_DATE}/

curl -X POST \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/ORG/REPO/actions/workflows/cleanup.yml/dispatches \
  -d "{\"ref\":\"main\",\"inputs\":{\"server_id\":\"$SERVER_ID\",\"status\":\"$STATUS\",\"run_date\":\"$RUN_DATE\"}}"
```

Total GitHub Actions usage: ~4 minutes/day (well within 2,000 min/mo free tier for private repos).

## Cost Summary

| Component | Monthly cost |
|-----------|-------------|
| Persistent server (CX22) | ~€4 |
| Ephemeral compute (3 hrs/day) | ~€5.50 |
| Snapshot storage (~20GB) | ~€0.20 |
| Data transfer (internal) | €0 |
| **Total** | **~€10/mo** |

Phase A only (no compute server): **~€4/mo**.

## Open Questions

- Gulf region lat/lon bounds for data subsetting
- CMEMS credentials setup
- Whether this lives in `oceanmotion-satellite` or a separate ops repo
