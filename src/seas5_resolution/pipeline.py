from __future__ import annotations

from pathlib import Path

import xarray as xr

from .config import DataPaths, DomainSpec
from .domain import subset_regular_dataarray, subset_regular_dataset
from .io import (
    available_native_initializations,
    available_regular_initializations,
    open_altimetry,
    open_native_hindcast_stack,
    open_regridded_hindcast_stack,
)
from .metrics import skill_dataset
from .preprocess import (
    align_to_valid_time,
    build_grid_from_coordinates,
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


def _normalize_verification(
    verification: str,
    fixed_obs_resolution_deg: float | None,
) -> tuple[str, float | None]:
    if verification == "matched":
        return verification, None
    if verification == "fixed":
        if fixed_obs_resolution_deg is None:
            raise ValueError("fixed observation resolution is required when verification='fixed'")
        return verification, fixed_obs_resolution_deg
    if verification == "fixed_025":
        return "fixed", 0.25
    if verification == "fixed_1":
        return "fixed", 1.0
    raise ValueError(f"Unsupported verification mode: {verification}")


def _observation_overlap_domain(
    reference: xr.DataArray,
    observations: xr.DataArray,
    domain: DomainSpec | None,
) -> DomainSpec:
    overlap = DomainSpec(
        lon_min=max(float(reference.lon.min()), float(observations.lon.min())),
        lon_max=min(float(reference.lon.max()), float(observations.lon.max())),
        lat_min=max(float(reference.lat.min()), float(observations.lat.min())),
        lat_max=min(float(reference.lat.max()), float(observations.lat.max())),
    )
    if domain is None:
        return overlap
    return DomainSpec(
        lon_min=max(domain.lon_min, overlap.lon_min),
        lon_max=min(domain.lon_max, overlap.lon_max),
        lat_min=max(domain.lat_min, overlap.lat_min),
        lat_max=min(domain.lat_max, overlap.lat_max),
    )


def run_regular_grid_skill(
    paths: DataPaths,
    resolution_deg: float,
    max_initializations: int | None = None,
    start_month: int | None = None,
    domain: DomainSpec | None = None,
    verification: str = "matched",
    fixed_obs_resolution_deg: float | None = None,
    regular_archive_source: str = "yearly_allstarts",
    output_path: Path | None = None,
) -> xr.Dataset:
    if resolution_deg not in (1.0, 2.0, 3.0):
        raise ValueError("Regular-grid workflow currently supports 1, 2, and 3 degree analyses")
    verification, fixed_obs_resolution_deg = _normalize_verification(verification, fixed_obs_resolution_deg)

    initializations = available_regular_initializations(paths, archive_source=regular_archive_source)
    if start_month is not None:
        initializations = [value for value in initializations if int(value[4:6]) == start_month]
    if max_initializations is not None:
        initializations = initializations[:max_initializations]
    hindcast_1deg = open_regridded_hindcast_stack(
        paths,
        initializations,
        archive_source=regular_archive_source,
    )
    observations = _prepare_observations(paths, domain=domain)

    hindcast_1deg = detrend_linear(hindcast_1deg, dim="init")
    hindcast = hindcast_1deg if resolution_deg == 1.0 else coarsen_boxcar(hindcast_1deg, target_deg=resolution_deg)

    if verification == "matched":
        observations = coarsen_boxcar(observations, target_deg=resolution_deg)

        observations = snap_to_regular_grid(
            observations,
            hindcast,
            tolerance_deg=resolution_deg / 2.0,
        )
        hindcast = subset_regular_dataarray(hindcast, domain)
        observations = subset_regular_dataarray(observations, domain)
    else:
        if fixed_obs_resolution_deg == 0.25:
            target_grid = build_regular_target_grid(observations, target_deg=0.25)
            target_grid = subset_regular_dataset(target_grid, domain)
            hindcast = remap_regular_to_regular(hindcast, target_grid, method="linear")
            observations = subset_regular_dataarray(observations, domain)
        elif fixed_obs_resolution_deg == 1.0:
            observations = coarsen_boxcar(observations, target_deg=1.0)
            target_domain = _observation_overlap_domain(
                hindcast_1deg.isel(init=0, lead=0, drop=True),
                observations,
                domain,
            )
            target_template = subset_regular_dataarray(
                hindcast_1deg.isel(init=0, lead=0, drop=True),
                target_domain,
            )
            target_grid = build_grid_from_coordinates(target_template)
            hindcast = remap_regular_to_regular(hindcast, target_grid, method="linear")
            observations = snap_to_regular_grid(
                observations,
                target_template,
                tolerance_deg=0.5,
            )
        else:
            raise ValueError("Fixed verification currently supports only 0.25 and 1.0 degree observation targets")

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
    initializations = available_native_initializations(paths)
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
