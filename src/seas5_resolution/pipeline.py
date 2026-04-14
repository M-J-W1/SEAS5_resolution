from __future__ import annotations

from pathlib import Path

import xarray as xr

from .config import DataPaths, DomainSpec
from .domain import subset_regular_dataarray, subset_regular_dataset
from .io import available_initializations, open_altimetry, open_native_hindcast_stack, open_regridded_hindcast_stack
from .metrics import skill_dataset
from .preprocess import (
    align_to_valid_time,
    build_regular_target_grid,
    coarsen_boxcar,
    detrend_linear,
    remap_regular_to_regular,
    regrid_native_to_regular,
    snap_to_regular_grid,
)


def _prepare_observations(paths: DataPaths, domain: DomainSpec | None = None) -> xr.DataArray:
    obs = open_altimetry(paths)
    obs = detrend_linear(obs, dim="time")
    return subset_regular_dataarray(obs, domain)


def run_regular_grid_skill(
    paths: DataPaths,
    resolution_deg: float,
    max_initializations: int | None = None,
    start_month: int | None = None,
    domain: DomainSpec | None = None,
    verification: str = "matched",
    output_path: Path | None = None,
) -> xr.Dataset:
    if resolution_deg not in (1.0, 3.0):
        raise ValueError("Regular-grid workflow currently supports 1 and 3 degree analyses")
    if verification not in {"matched", "fixed_025"}:
        raise ValueError("verification must be either 'matched' or 'fixed_025'")

    initializations = available_initializations(paths)
    if start_month is not None:
        initializations = [value for value in initializations if int(value[4:6]) == start_month]
    if max_initializations is not None:
        initializations = initializations[:max_initializations]
    hindcast = open_regridded_hindcast_stack(paths, initializations)
    observations = _prepare_observations(paths, domain=domain)

    hindcast = detrend_linear(hindcast, dim="init")

    if verification == "matched":
        if resolution_deg == 3.0:
            hindcast = coarsen_boxcar(hindcast, target_deg=3.0)
            observations = coarsen_boxcar(observations, target_deg=3.0)
        else:
            observations = coarsen_boxcar(observations, target_deg=1.0)

        observations = snap_to_regular_grid(
            observations,
            hindcast,
            tolerance_deg=resolution_deg / 2.0,
        )
        hindcast = subset_regular_dataarray(hindcast, domain)
        observations = subset_regular_dataarray(observations, domain)
    else:
        if resolution_deg == 3.0:
            hindcast = coarsen_boxcar(hindcast, target_deg=3.0)

        target_grid = build_regular_target_grid(observations, target_deg=0.25)
        target_grid = subset_regular_dataset(target_grid, domain)
        hindcast = remap_regular_to_regular(hindcast, target_grid, method="linear")
        observations = subset_regular_dataarray(observations, domain)

    hindcast, obs_at_valid = align_to_valid_time(hindcast, observations)
    hindcast = hindcast.where(obs_at_valid.notnull())
    ds = skill_dataset(hindcast, obs_at_valid)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(output_path)

    return ds


def run_native_to_quarter_degree_skill(
    paths: DataPaths,
    max_initializations: int | None = None,
    start_month: int | None = None,
    domain: DomainSpec | None = None,
    output_path: Path | None = None,
) -> xr.Dataset:
    initializations = available_initializations(paths)
    if start_month is not None:
        initializations = [value for value in initializations if int(value[4:6]) == start_month]
    if max_initializations is not None:
        initializations = initializations[:max_initializations]
    native = open_native_hindcast_stack(paths, initializations)
    observations = _prepare_observations(paths, domain=domain)
    native = detrend_linear(native, dim="init")

    target_grid = build_regular_target_grid(observations, target_deg=0.25)
    target_grid = subset_regular_dataset(target_grid, domain)
    regridded = regrid_native_to_regular(native, target_grid)
    regridded = regridded.assign_coords(
        init=native["init"],
        lead=native["lead"],
        valid_time=native["valid_time"],
    )
    regridded, obs_at_valid = align_to_valid_time(regridded, observations)
    regridded = regridded.where(obs_at_valid.notnull())
    ds = skill_dataset(regridded, obs_at_valid)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(output_path)

    return ds
