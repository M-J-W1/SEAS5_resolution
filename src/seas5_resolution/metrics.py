from __future__ import annotations

import numpy as np
import xarray as xr


def anomaly_correlation_coefficient(
    forecast: xr.DataArray,
    observed: xr.DataArray,
    dim: str = "init",
) -> xr.DataArray:
    forecast_anom = forecast - forecast.mean(dim)
    observed_anom = observed - observed.mean(dim)
    numerator = (forecast_anom * observed_anom).sum(dim)
    denominator = np.sqrt((forecast_anom**2).sum(dim) * (observed_anom**2).sum(dim))
    return (numerator / denominator).rename("acc")


def root_mean_square_error(
    forecast: xr.DataArray,
    observed: xr.DataArray,
    dim: str = "init",
) -> xr.DataArray:
    mse = ((forecast - observed) ** 2).mean(dim, skipna=True)
    return np.sqrt(mse).rename("rmse")


def skill_dataset(forecast: xr.DataArray, observed: xr.DataArray, dim: str = "init") -> xr.Dataset:
    return xr.Dataset(
        {
            "acc": anomaly_correlation_coefficient(forecast, observed, dim=dim),
            "rmse": root_mean_square_error(forecast, observed, dim=dim),
        }
    )
