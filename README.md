SEAS5 Resolution

This project tests whether spatial smoothing of SEAS5 sea-surface height
forecasts improves skill. The core scientific question is now framed as:

Does smoothing the forecast improve agreement with a fixed observed target?

The primary verification design therefore holds observations fixed on the
altimetry `0.25°` grid and compares:

- native SEAS5 regridded to regular `0.25°`
- `1°` SEAS5 forecast remapped onto the `0.25°` observation grid
- `3°` SEAS5 forecast remapped onto the `0.25°` observation grid

Matched-resolution verification is still supported, but it should be treated as
secondary/contextual analysis.

Data

- Native SEAS5: `/home/ahu/archive/MMforecast/SEAS5_OCEAN025`
- Legacy archived `1x1` SEAS5: `/home/ahu/archive/MMforecast/SEAS5-ECMWF`
- Yearly all-starts `1x1` SEAS5: `/home/aniau/yuxinw/SEAS5_hindcast`
- Monthly altimetry anomalies: `/home/aniau/archive/Altimetry/processed/cmems_20260407.nc`

Observed archive structure

- Native SEAS5 SSH files are on a curvilinear ocean grid with `nav_lat`,
  `nav_lon`, and `time_counter`
- Native SEAS5 exposes `ensmean` products directly
- The legacy archived `1x1` SEAS5 data are stored by member under `ens0` to
  `ens24`; the code computes the ensemble mean on load
- The yearly all-starts `1x1` SEAS5 archive is stored under `1993` to `2016`
  with flat filenames containing both start date and member id; the code also
  computes the ensemble mean on load
- The altimetry product is on a regular `0.25°` grid covering
  `lat=-65.5..65.5`, `lon=0..359.75`
- The yearly all-starts archive spans `1993010100` through `2016120100`, with
  twelve starts per year and `25` ensemble members per start
- The native/legacy shared archive still spans quarterly starts only

Current workflow

The implemented analysis pipeline can:

- discover hindcast starts from both regular-grid archive layouts
- load native and archived `1°` SEAS5 SSH
- load monthly altimetry anomalies
- remove linear trends gridpoint-by-gridpoint
- generate `2°` and `3°` forecast products from `1°` SEAS5 using boxcar averaging
- compute `ACC` and `RMSE` across hindcast starts for each lead month
- verify forecasts either:
  - at matched resolution
  - against fixed `0.25°` altimetry observations
  - against fixed `1°` altimetry observations
- subset runs to a regional domain for fast testing
- produce publication-style skill maps
- produce experiment-minus-baseline difference maps

Archive-selection rule

- Regular-grid runs use exactly one archive source at a time:
  `yearly_allstarts` or `legacy_4starts`
- The code does not merge starts across those two regular-grid archives within a
  single run
- Native-grid runs remain separate and only use the native archive

Verification design

Primary analysis:

- Native forecast on regular `0.25°` grid vs altimetry at `0.25°`
- `1°` forecast remapped to `0.25°` vs altimetry at `0.25°`
- `1°` forecast vs fixed `1°` altimetry
- `2°` forecast remapped to fixed `1°` altimetry
- `3°` forecast remapped to fixed `1°` altimetry
- `3°` forecast remapped to `0.25°` vs altimetry at `0.25°`

Secondary analysis:

- Matched-resolution verification at `1°` and `3°`

Important decisions already adopted

- Native-to-regular regridding uses bilinear interpolation
- `xESMF` is run with `ignore_degenerate=True` because the native ocean grid
  contains degenerate coastal cells
- Regridded native forecasts are masked to the altimetry valid domain before
  scoring
- `3°` is generated from `1°`
- Coarse forecasts are not "upsampled to recover detail"; they are only remapped
  onto the `0.25°` observation grid for verification

Repository layout

- `src/seas5_resolution/`: analysis package
- `scripts/run_skill_analysis.py`: main skill-calculation CLI
- `scripts/plot_skill_maps.py`: publication-style skill map plotting
- `scripts/plot_skill_differences.py`: experiment-minus-baseline difference plots
- `docs/WORK_PLAN.md`: planning notes
- `results/`: output NetCDFs and figures

Environments

Two local environments are useful:

1. `.venv`
   Use this for regular-grid work, plotting, and general development.

2. `.mamba/envs/esmpy-891`
   Use this for native-grid `0.25°` regridding with `ESMF/esmpy/xESMF`.

Setup

Regular Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Native-grid regridding environment:

```bash
curl -L https://micro.mamba.pm/api/micromamba/linux-64/latest -o /tmp/micromamba.tar.bz2
mkdir -p .tools/micromamba
tar -xjf /tmp/micromamba.tar.bz2 -C .tools/micromamba

.tools/micromamba/bin/micromamba create -y \
  -r /home/kaimoku/mwidlans/python_code/projects/SEAS5_resolution/.mamba \
  -n esmpy-891 \
  -c conda-forge \
  python=3.11 esmpy=8.9.1 xesmf xarray pandas scipy netcdf4 matplotlib
```

Verify the regridding environment:

```bash
.mamba/envs/esmpy-891/bin/python - <<'PY'
import esmpy
import xesmf
print(esmpy.__version__)
print(xesmf.__version__)
PY
```

CLI overview

Inspect available starts:

```bash
python3 scripts/run_skill_analysis.py inspect
```

Core run options:

- `--resolution {0.25,1,2,3}`
- `--verification {matched,fixed,fixed_025,fixed_1}`
- `--fixed-obs-resolution {0.25,1}`
- `--regular-archive-source {yearly_allstarts,legacy_4starts}`
- `--max-starts N`
- `--start-month {1..12}`
- `--lon-min --lon-max --lat-min --lat-max`
- `--output PATH`

Notes:

- `--verification fixed_025` matters for `1°`, `2°`, and `3°` runs
- `--verification fixed_1` runs the new all-starts skill design against fixed
  `1°` altimetry
- `--regular-archive-source yearly_allstarts` is the default for regular-grid
  `1°`, `2°`, and `3°` runs
- `--regular-archive-source legacy_4starts` preserves the older quarterly
  regular-grid workflow without mixing it with the yearly all-starts archive
- the native `0.25°` route always verifies against the `0.25°` altimetry grid
- `0.25°` native runs should use `.mamba/envs/esmpy-891/bin/python`
- `1°`, `2°`, and `3°` regular-grid runs can use `.venv/bin/python`

Recommended fast test domain

For fast debugging and iteration, use the central Pacific box:

- `lon = 180 to 195`
- `lat = -7.5 to 7.5`

Example central-Pacific smoke tests

Native forecast vs fixed `0.25°` altimetry:

```bash
.mamba/envs/esmpy-891/bin/python scripts/run_skill_analysis.py run \
  --resolution 0.25 \
  --max-starts 4 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_025deg_central_pacific_4starts.nc
```

`1°` forecast vs fixed `0.25°` altimetry:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 1 \
  --verification fixed_025 \
  --max-starts 4 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_1deg_on025_central_pacific_4starts.nc
```

`3°` forecast vs fixed `0.25°` altimetry:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 3 \
  --verification fixed_025 \
  --max-starts 4 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_3deg_on025_central_pacific_4starts.nc
```

All-starts central-Pacific runs

`1°` forecast on fixed `1°` observations:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 1 \
  --verification fixed_1 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_1deg_on1_central_pacific_allstarts.nc
```

`2°` forecast on fixed `1°` observations:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 2 \
  --verification fixed_1 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_2deg_on1_central_pacific_allstarts.nc
```

`3°` forecast on fixed `1°` observations:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 3 \
  --verification fixed_1 \
  --lon-min 180 --lon-max 195 \
  --lat-min -7.5 --lat-max 7.5 \
  --output results/skill_3deg_on1_central_pacific_allstarts.nc
```

How to run the full domain

Full-domain runs are the same commands without regional bounds.

Native forecast vs fixed `0.25°` altimetry:

```bash
.mamba/envs/esmpy-891/bin/python scripts/run_skill_analysis.py run \
  --resolution 0.25 \
  --output results/skill_025deg_global_allstarts.nc
```

`1°` forecast vs fixed `0.25°` altimetry:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 1 \
  --verification fixed_025 \
  --output results/skill_1deg_on025_global_allstarts.nc
```

`3°` forecast vs fixed `0.25°` altimetry:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 3 \
  --verification fixed_025 \
  --output results/skill_3deg_on025_global_allstarts.nc
```

Matched-resolution runs

`1°` matched-resolution:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 1 \
  --verification matched \
  --output results/skill_1deg_matched_global_allstarts.nc
```

`3°` matched-resolution:

```bash
.venv/bin/python scripts/run_skill_analysis.py run \
  --resolution 3 \
  --verification matched \
  --output results/skill_3deg_matched_global_allstarts.nc
```

Plotting skill maps

Skill maps:

```bash
.venv/bin/python scripts/plot_skill_maps.py \
  --input results/skill_3deg_on025_global_allstarts.nc \
  --output results/skill_3deg_on025_global_allstarts.png \
  --title "SEAS5 3° Forecast Skill vs 0.25° Altimetry"
```

Difference maps:

```bash
.venv/bin/python scripts/plot_skill_differences.py \
  --baseline results/skill_025deg_global_allstarts.nc \
  --experiment results/skill_3deg_on025_global_allstarts.nc \
  --output results/skill_diff_3deg_minus_native_global_allstarts.png \
  --title "3° Forecast Minus Native Forecast Skill vs 0.25° Altimetry"
```

Background workflow script

For routine runs, use the wrapper script:

- `scripts/run_fixed025_workflow.sh`

It launches the three fixed-`0.25°` analyses in parallel:

- native `0.25°` forecast vs fixed `0.25°` altimetry
- `1°` forecast remapped to `0.25°` vs fixed `0.25°` altimetry
- `3°` forecast remapped to `0.25°` vs fixed `0.25°` altimetry

It then generates:

- the three publication-style skill-map figures
- the two experiment-minus-native difference figures

Recommended first test:

```bash
nohup env DOMAIN=pacific_small MAX_STARTS=4 bash scripts/run_fixed025_workflow.sh > logs/workflow.out 2>&1 &
```

Full-domain production run:

```bash
nohup env DOMAIN=global bash scripts/run_fixed025_workflow.sh > logs/workflow.out 2>&1 &
```

How to monitor the run:

```bash
tail -f logs/workflow.out
```

Inspect per-step logs:

```bash
ls -ltr logs
```

Important script options:

- `DOMAIN=pacific_small` uses `lon=180..195`, `lat=-7.5..7.5`
- `DOMAIN=global` runs the full domain
- `MAX_STARTS=4` is useful for a smoke test
- omitting `MAX_STARTS` uses all available starts
- `START_MONTH=1` would restrict the workflow to January starts only

Expected full-domain outputs from the wrapper:

- `results/skill_025deg_global_fixed025.nc`
- `results/skill_1deg_on025_global.nc`
- `results/skill_3deg_on025_global.nc`
- `results/skill_025deg_global_fixed025.png`
- `results/skill_1deg_on025_global.png`
- `results/skill_3deg_on025_global.png`
- `results/skill_diff_1deg_minus_native_global.png`
- `results/skill_diff_3deg_minus_native_global.png`

Current interpretation from the regional all-starts test

In the central Pacific box, using all starts and verifying everything against
fixed `0.25°` altimetry:

- `1°` is slightly more skillful than native at all leads
- `3°` is more skillful than native at most leads and has lower regional-mean
  `RMSE` at every lead in the current regional test

That is only a regional result. The next critical output is the same analysis
and difference plotting on the full domain.
