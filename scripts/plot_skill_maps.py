from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import xarray as xr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot SEAS5 skill maps")
    parser.add_argument("--input", type=Path, required=True, help="Input skill NetCDF")
    parser.add_argument("--output", type=Path, required=True, help="Output PNG path")
    parser.add_argument("--title", type=str, required=True, help="Figure title")
    return parser


def crop_to_valid_domain(ds: xr.Dataset) -> tuple[xr.Dataset, xr.DataArray]:
    ocean_mask = ds["rmse"].notnull().any("lead")
    lat_has_data = ocean_mask.any("lon")
    lon_has_data = ocean_mask.any("lat")

    lat_idx = np.where(lat_has_data.values)[0]
    lon_idx = np.where(lon_has_data.values)[0]
    cropped = ds.isel(
        lat=slice(lat_idx[0], lat_idx[-1] + 1),
        lon=slice(lon_idx[0], lon_idx[-1] + 1),
    )
    return cropped, ocean_mask.isel(
        lat=slice(lat_idx[0], lat_idx[-1] + 1),
        lon=slice(lon_idx[0], lon_idx[-1] + 1),
    )


def add_panel(
    ax: plt.Axes,
    field: xr.DataArray,
    ocean_mask: xr.DataArray,
    cmap: str,
    vmin: float,
    vmax: float,
    title: str,
):
    land = xr.where(ocean_mask, np.nan, 1.0)
    ax.pcolormesh(
        field["lon"],
        field["lat"],
        land,
        shading="auto",
        cmap=ListedColormap(["#d9d9d9"]),
        vmin=0,
        vmax=1,
    )
    image = ax.pcolormesh(
        field["lon"],
        field["lat"],
        field,
        shading="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_title(title, fontsize=11, weight="bold")
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(np.arange(0, 361, 60))
    ax.set_yticks(np.arange(-60, 61, 30))
    ax.tick_params(labelsize=8, length=3)
    return image


def make_plot(ds: xr.Dataset, output: Path, title: str) -> None:
    ds, ocean_mask = crop_to_valid_domain(ds)

    fig, axes = plt.subplots(
        2,
        ds.sizes["lead"],
        figsize=(24, 8),
        constrained_layout=True,
        sharex=True,
        sharey=True,
    )

    acc_vmin, acc_vmax = -1.0, 1.0
    rmse_vmin = 0.0
    rmse_vmax = float(ds["rmse"].quantile(0.98, skipna=True))

    for i, lead in enumerate(ds["lead"].values):
        acc = ds["acc"].sel(lead=lead)
        rmse = ds["rmse"].sel(lead=lead)

        acc_im = add_panel(
            axes[0, i],
            acc,
            ocean_mask,
            cmap="RdBu_r",
            vmin=acc_vmin,
            vmax=acc_vmax,
            title=f"ACC Lead {int(lead)}",
        )
        rmse_im = add_panel(
            axes[1, i],
            rmse,
            ocean_mask,
            cmap="viridis",
            vmin=rmse_vmin,
            vmax=rmse_vmax,
            title=f"RMSE Lead {int(lead)}",
        )
        axes[1, i].set_xlabel("Longitude", fontsize=9)

    axes[0, 0].set_ylabel("Latitude", fontsize=9)
    axes[1, 0].set_ylabel("Latitude", fontsize=9)

    acc_bar = fig.colorbar(acc_im, ax=axes[0, :], shrink=0.9, pad=0.015)
    acc_bar.set_label("ACC", fontsize=10)
    rmse_bar = fig.colorbar(rmse_im, ax=axes[1, :], shrink=0.9, pad=0.015)
    rmse_bar.set_label("RMSE (m)", fontsize=10)

    fig.suptitle(title, fontsize=17, weight="bold")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = build_parser().parse_args()
    ds = xr.open_dataset(args.input)
    make_plot(ds, args.output, args.title)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
