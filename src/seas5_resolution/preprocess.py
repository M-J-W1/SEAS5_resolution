from __future__ import annotations

import math

import numpy as np
import xarray as xr


def detrend_linear(da: xr.DataArray, dim: str) -> xr.DataArray:
    if da.sizes[dim] < 2:
        detrended = da.copy()
        detrended.attrs.update(da.attrs)
        detrended.attrs["detrended"] = "skipped_insufficient_samples"
        return detrended

    original_coord = da[dim]
    working = da.assign_coords({dim: np.arange(da.sizes[dim], dtype=np.float64)})
    coeffs = working.polyfit(dim=dim, deg=1, skipna=True)
    trend = xr.polyval(working[dim], coeffs.polyfit_coefficients)
    detrended = (working - trend).assign_coords({dim: original_coord})
    detrended.attrs.update(da.attrs)
    detrended.attrs["detrended"] = "linear"
    return detrended


def infer_resolution(da: xr.DataArray) -> tuple[float, float]:
    lat_name = "lat"
    lon_name = "lon"
    if lat_name not in da.coords or lon_name not in da.coords:
        raise ValueError("Regular lat/lon coordinates are required")
    lat_step = float(np.abs(da[lat_name].diff(lat_name).median()))
    lon_step = float(np.abs(da[lon_name].diff(lon_name).median()))
    return lat_step, lon_step


def coarsen_boxcar(da: xr.DataArray, target_deg: float) -> xr.DataArray:
    src_lat_deg, src_lon_deg = infer_resolution(da)
    lat_factor = target_deg / src_lat_deg
    lon_factor = target_deg / src_lon_deg
    if not lat_factor.is_integer() or not lon_factor.is_integer():
        raise ValueError(
            f"Target resolution {target_deg} is not an integer multiple of source resolution "
            f"({src_lat_deg}, {src_lon_deg})"
        )

    coarse = da.coarsen(
        lat=int(lat_factor),
        lon=int(lon_factor),
        boundary="trim",
    ).mean(skipna=True)
    coarse.attrs.update(da.attrs)
    coarse.attrs["boxcar_target_resolution_deg"] = target_deg
    return coarse


def snap_to_regular_grid(
    source: xr.DataArray,
    target: xr.DataArray,
    tolerance_deg: float,
) -> xr.DataArray:
    snapped = source.reindex(
        lat=target.lat,
        lon=target.lon,
        method="nearest",
        tolerance=tolerance_deg,
    )
    snapped.attrs.update(source.attrs)
    snapped.attrs["snapped_to_grid"] = "nearest"
    return snapped


def remap_regular_to_regular(
    source: xr.DataArray,
    target_grid: xr.Dataset,
    method: str = "linear",
) -> xr.DataArray:
    remapped = source.interp(
        lat=target_grid["lat"],
        lon=target_grid["lon"],
        method=method,
    )
    remapped.attrs.update(source.attrs)
    remapped.attrs["remapped_to_regular_grid"] = method
    return remapped


def build_regular_target_grid(source: xr.DataArray, target_deg: float) -> xr.Dataset:
    lat_min = math.ceil(float(source.lat.min()) / target_deg) * target_deg
    lat_max = math.floor(float(source.lat.max()) / target_deg) * target_deg
    lon_min = math.ceil(float(source.lon.min()) / target_deg) * target_deg
    lon_max = math.floor(float(source.lon.max()) / target_deg) * target_deg

    lat = np.arange(lat_min, lat_max + 0.5 * target_deg, target_deg, dtype=np.float32)
    lon = np.arange(lon_min, lon_max + 0.5 * target_deg, target_deg, dtype=np.float32)
    return xr.Dataset(coords={"lat": lat, "lon": lon})


def build_grid_from_coordinates(source: xr.DataArray) -> xr.Dataset:
    return xr.Dataset(
        coords={
            "lat": source["lat"].astype(np.float32),
            "lon": source["lon"].astype(np.float32),
        }
    )


def regrid_native_to_regular(
    native: xr.DataArray,
    target_grid: xr.Dataset,
    method: str = "bilinear",
    ignore_degenerate: bool = True,
) -> xr.DataArray:
    try:
        import xesmf as xe
    except ImportError as exc:
        raise ImportError("xESMF is required for native-grid regridding") from exc

    source = xr.Dataset(
        coords={
            "lat": native["nav_lat"],
            "lon": native["nav_lon"],
        }
    )
    regridder = xe.Regridder(
        source,
        target_grid,
        method=method,
        periodic=True,
        reuse_weights=False,
        ignore_degenerate=ignore_degenerate,
    )
    regridded = regridder(native)
    regridded.attrs.update(native.attrs)
    regridded.attrs["regridded_with"] = f"xESMF:{method}"
    regridded.attrs["ignore_degenerate"] = str(ignore_degenerate)
    return regridded.rename("ssh_anom")


def align_to_valid_time(hindcast: xr.DataArray, observations: xr.DataArray) -> tuple[xr.DataArray, xr.DataArray]:
    valid_time = hindcast["valid_time"]
    if "init" not in valid_time.dims:
        init_values = hindcast["init"].values if "init" in hindcast.coords else np.array([0])
        obs_at_valid = observations.sel(time=valid_time).expand_dims(init=init_values)
        return hindcast, obs_at_valid

    matched = []
    init_values = hindcast["init"].values
    for init_value in init_values:
        init_valid_time = valid_time.sel(init=init_value)
        obs_for_init = observations.sel(time=init_valid_time).expand_dims(init=[init_value])
        matched.append(obs_for_init)
    obs_at_valid = xr.concat(matched, dim="init", coords="minimal", compat="override")
    return hindcast, obs_at_valid
