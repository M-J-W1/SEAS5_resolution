from __future__ import annotations

import xarray as xr

from .config import DomainSpec


def subset_regular_dataarray(da: xr.DataArray, domain: DomainSpec | None) -> xr.DataArray:
    if domain is None:
        return da

    lon_mask = (da["lon"] >= domain.lon_min) & (da["lon"] <= domain.lon_max)
    lat_mask = (da["lat"] >= domain.lat_min) & (da["lat"] <= domain.lat_max)
    lon_idx = lon_mask.values.nonzero()[0]
    lat_idx = lat_mask.values.nonzero()[0]
    if lon_idx.size == 0 or lat_idx.size == 0:
        raise ValueError(f"Requested domain {domain} does not overlap the data grid")

    return da.isel(
        lon=slice(lon_idx[0], lon_idx[-1] + 1),
        lat=slice(lat_idx[0], lat_idx[-1] + 1),
    )


def subset_regular_domain(da: xr.DataArray, domain: DomainSpec | None) -> xr.DataArray:
    return subset_regular_dataarray(da, domain)


def subset_regular_dataset(ds: xr.Dataset, domain: DomainSpec | None) -> xr.Dataset:
    if domain is None:
        return ds

    lon_mask = (ds["lon"] >= domain.lon_min) & (ds["lon"] <= domain.lon_max)
    lat_mask = (ds["lat"] >= domain.lat_min) & (ds["lat"] <= domain.lat_max)
    lon_idx = lon_mask.values.nonzero()[0]
    lat_idx = lat_mask.values.nonzero()[0]
    if lon_idx.size == 0 or lat_idx.size == 0:
        raise ValueError(f"Requested domain {domain} does not overlap the data grid")

    return ds.isel(
        lon=slice(lon_idx[0], lon_idx[-1] + 1),
        lat=slice(lat_idx[0], lat_idx[-1] + 1),
    )
