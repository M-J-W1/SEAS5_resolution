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
ALTIMETRY_VAR = "absolute_dynamic_topography_monthly_anomaly"


def discover_initializations(root: Path) -> list[str]:
    starts = []
    for child in sorted(root.iterdir()):
        match = START_PATTERN.match(child.name)
        if match and child.is_dir():
            starts.append(match.group(1))
    return starts


def available_initializations(paths: DataPaths) -> list[str]:
    native = set(discover_initializations(paths.native_root))
    regridded = set(discover_initializations(paths.regridded_root))
    return sorted(native & regridded)


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
    chunks: dict[str, int] | None = None,
) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    init_dir = paths.regridded_root / f"sossheig_{init}"
    member_files = [_single_nc_file(member_dir) for member_dir in _sorted_member_dirs(init_dir)]
    if not member_files:
        raise FileNotFoundError(f"No ensemble members found in {init_dir}")

    datasets = [xr.open_dataset(path, chunks=chunks) for path in member_files]
    member_data = [ds["sossheig"] for ds in datasets]
    stacked = xr.concat(member_data, dim=pd.Index(range(len(member_data)), name="member"))
    mean_da = stacked.mean("member", skipna=True).rename({"time_counter": "lead"})
    lead = np.arange(1, mean_da.sizes["lead"] + 1, dtype=np.int16)
    return mean_da.assign_coords(lead=lead).rename("ssh_anom")


def build_valid_time_index(init: str, n_leads: int) -> "pd.DatetimeIndex":
    import pandas as pd

    start = pd.to_datetime(init, format="%Y%m%d%H")
    return pd.date_range(start, periods=n_leads, freq="MS")


def attach_valid_time(da: "xr.DataArray", init: str) -> "xr.DataArray":
    import pandas as pd

    valid_time = build_valid_time_index(init, da.sizes["lead"])
    return da.assign_coords(valid_time=("lead", valid_time), init=pd.Timestamp(valid_time[0]))


def open_regridded_hindcast_stack(
    paths: DataPaths,
    initializations: Iterable[str],
    chunks: dict[str, int] | None = None,
) -> "xr.DataArray":
    import pandas as pd
    import xarray as xr

    arrays = []
    init_values = []
    for init in initializations:
        da = attach_valid_time(open_regridded_ensemble_mean(paths, init, chunks=chunks), init)
        arrays.append(da)
        init_values.append(pd.to_datetime(init, format="%Y%m%d%H"))
    stacked = xr.concat(arrays, dim=pd.Index(init_values, name="init"), coords="different", compat="no_conflicts")
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
    stacked = xr.concat(arrays, dim=pd.Index(init_values, name="init"), coords="different", compat="no_conflicts")
    return stacked.transpose("init", "lead", "y", "x")
