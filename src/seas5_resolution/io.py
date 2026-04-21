from __future__ import annotations

from pathlib import Path
import re
from typing import TYPE_CHECKING
from typing import Iterable

import numpy as np

from .config import DataPaths

if TYPE_CHECKING:
    import pandas as pd
    import xarray as xr

START_PATTERN = re.compile(r"^sossheig_(\d{10})$")
YEAR_PATTERN = re.compile(r"^\d{4}$")
YEARLY_MEMBER_PATTERN = re.compile(
    r".*_S(?P<init>\d{10})_.*_r(?P<member>\d{2})i\d{2}p\d{2}\.nc$"
)
ALTIMETRY_VAR = "absolute_dynamic_topography_monthly_anomaly"
REGULAR_ARCHIVE_SOURCES = ("legacy_4starts", "yearly_allstarts")


def discover_initializations(root: Path) -> list[str]:
    if not root.exists():
        return []

    starts = set()
    for child in sorted(root.iterdir()):
        match = START_PATTERN.match(child.name)
        if match and child.is_dir():
            starts.add(match.group(1))
            continue

        if child.is_dir() and YEAR_PATTERN.match(child.name):
            for path in child.glob("*.nc"):
                file_match = YEARLY_MEMBER_PATTERN.match(path.name)
                if file_match:
                    starts.add(file_match.group("init"))
    return sorted(starts)


def available_regular_initializations(
    paths: DataPaths,
    archive_source: str = "yearly_allstarts",
) -> list[str]:
    if archive_source == "legacy_4starts":
        return discover_initializations(paths.regridded_root)
    if archive_source == "yearly_allstarts":
        return discover_initializations(paths.regridded_yearly_root)
    raise ValueError(f"Unsupported regular archive source: {archive_source}")


def available_native_initializations(paths: DataPaths) -> list[str]:
    return discover_initializations(paths.native_root)


def available_shared_initializations(
    paths: DataPaths,
    archive_source: str = "legacy_4starts",
) -> list[str]:
    native = set(available_native_initializations(paths))
    regular = set(available_regular_initializations(paths, archive_source=archive_source))
    return sorted(native & regular)


def available_initializations(paths: DataPaths) -> list[str]:
    return available_regular_initializations(paths)


def _sorted_member_dirs(init_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in init_dir.iterdir()
        if path.is_dir() and re.fullmatch(r"ens\d+", path.name)
    )


def _single_nc_file(directory: Path) -> Path:
    files = sorted(directory.glob("*.nc"))
    if len(files) != 1:
        raise FileNotFoundError(f"Expected exactly one NetCDF file in {directory}, found {len(files)}")
    return files[0]


def _select_forecast_variable(ds: "xr.Dataset") -> "xr.DataArray":
    for name in ("sossheig", "zos"):
        if name in ds.data_vars:
            return ds[name]
    raise KeyError(f"Could not find a supported forecast variable in dataset: {list(ds.data_vars)}")


def _normalize_regular_forecast(da: "xr.DataArray") -> "xr.DataArray":
    rename_map = {}
    if "time_counter" in da.dims:
        rename_map["time_counter"] = "lead"
    if "leadtime" in da.dims:
        rename_map["leadtime"] = "lead"
    if rename_map:
        da = da.rename(rename_map)

    if "lead" not in da.dims:
        raise ValueError(f"Could not identify lead dimension in {da.dims}")

    lead = np.arange(1, da.sizes["lead"] + 1, dtype=np.int16)
    da = da.assign_coords(lead=lead).rename("ssh_anom").astype(np.float32)

    if "time" in da.coords and "lead" in da["time"].dims:
        da = da.assign_coords(valid_time=("lead", da["time"].values))
    return da


def _yearly_member_files(yearly_root: Path, init: str) -> list[Path]:
    year_dir = yearly_root / init[:4]
    if not year_dir.exists():
        return []

    matched: list[tuple[str, Path]] = []
    for path in year_dir.glob(f"*S{init}*.nc"):
        match = YEARLY_MEMBER_PATTERN.match(path.name)
        if match and match.group("init") == init:
            matched.append((match.group("member"), path))
    return [path for _, path in sorted(matched)]


def open_altimetry(paths: DataPaths, chunks: dict[str, int] | None = None) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    ds = xr.open_dataset(paths.altimetry_path, chunks=chunks)
    da = ds[ALTIMETRY_VAR].where(ds[ALTIMETRY_VAR] > -3e4)
    time = pd.date_range("1993-01-01", periods=da.sizes["time_anom"], freq="MS")
    da = (
        da.rename({"time_anom": "time"})
        .assign_coords(time=time)
        .rename("ssh_anom")
        .astype(np.float32)
        / 100.0
    )
    da.attrs["units"] = "m"
    return da


def open_native_ensemble_mean(paths: DataPaths, init: str, chunks: dict[str, int] | None = None) -> "xr.DataArray":
    import xarray as xr

    init_dir = paths.native_root / f"sossheig_{init}" / "ensmean"
    ds = xr.open_dataset(_single_nc_file(init_dir), chunks=chunks)
    da = ds["sossheig"].rename({"time_counter": "lead"})
    lead = np.arange(1, da.sizes["lead"] + 1, dtype=np.int16)
    return da.assign_coords(lead=lead).rename("ssh_anom")


def open_regridded_ensemble_mean(
    paths: DataPaths,
    init: str,
    archive_source: str = "yearly_allstarts",
    chunks: dict[str, int] | None = None,
) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    member_files: list[Path] = []
    if archive_source == "yearly_allstarts":
        member_files = _yearly_member_files(paths.regridded_yearly_root, init)
    elif archive_source == "legacy_4starts":
        init_dir = paths.regridded_root / f"sossheig_{init}"
        if init_dir.exists():
            member_files = [_single_nc_file(member_dir) for member_dir in _sorted_member_dirs(init_dir)]
    else:
        raise ValueError(f"Unsupported regular archive source: {archive_source}")

    init_dir = paths.regridded_root / f"sossheig_{init}"
    if not member_files and archive_source == "legacy_4starts" and init_dir.exists():
        member_files = [_single_nc_file(member_dir) for member_dir in _sorted_member_dirs(init_dir)]
    if not member_files:
        raise FileNotFoundError(
            f"No ensemble members found for {init} in selected source {archive_source}"
        )

    datasets = [xr.open_dataset(path, chunks=chunks) for path in member_files]
    member_data = [_normalize_regular_forecast(_select_forecast_variable(ds)) for ds in datasets]
    stacked = xr.concat(member_data, dim=pd.Index(range(len(member_data)), name="member"))
    mean_da = stacked.mean("member", skipna=True)
    return mean_da.rename("ssh_anom")


def build_valid_time_index(init: str, n_leads: int) -> "pd.DatetimeIndex":
    import pandas as pd

    start = pd.to_datetime(init, format="%Y%m%d%H")
    return pd.date_range(start, periods=n_leads, freq="MS")


def attach_valid_time(da: "xr.DataArray", init: str) -> "xr.DataArray":
    import pandas as pd

    # Monthly verification is carried out against month-start altimetry fields.
    valid_time = build_valid_time_index(init, da.sizes["lead"])
    return da.assign_coords(valid_time=("lead", valid_time), init=pd.to_datetime(init, format="%Y%m%d%H"))


def open_regridded_hindcast_stack(
    paths: DataPaths,
    initializations: Iterable[str],
    archive_source: str = "yearly_allstarts",
    chunks: dict[str, int] | None = None,
) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    arrays = []
    init_values = []
    for init in initializations:
        da = attach_valid_time(
            open_regridded_ensemble_mean(paths, init, archive_source=archive_source, chunks=chunks),
            init,
        )
        arrays.append(da)
        init_values.append(pd.to_datetime(init, format="%Y%m%d%H"))
    stacked = xr.concat(
        arrays,
        dim=pd.Index(init_values, name="init"),
        coords="different",
        compat="no_conflicts",
        join="exact",
    )
    return stacked.transpose("init", "lead", "lat", "lon")


def open_native_hindcast_stack(
    paths: DataPaths,
    initializations: Iterable[str],
    chunks: dict[str, int] | None = None,
) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    arrays = []
    init_values = []
    for init in initializations:
        da = attach_valid_time(open_native_ensemble_mean(paths, init, chunks=chunks), init)
        arrays.append(da)
        init_values.append(pd.to_datetime(init, format="%Y%m%d%H"))
    stacked = xr.concat(
        arrays,
        dim=pd.Index(init_values, name="init"),
        coords="different",
        compat="no_conflicts",
        join="exact",
    )
    return stacked.transpose("init", "lead", "y", "x")
