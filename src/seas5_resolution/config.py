from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    native_root: Path = Path("/home/ahu/archive/MMforecast/SEAS5_OCEAN025")
    regridded_root: Path = Path("/home/ahu/archive/MMforecast/SEAS5-ECMWF")
    regridded_yearly_root: Path = Path("/home/aniau/yuxinw/SEAS5_hindcast")
    altimetry_path: Path = Path("/home/aniau/archive/Altimetry/processed/cmems_20260407.nc")


@dataclass(frozen=True)
class ResolutionSpec:
    degrees: float

    @property
    def label(self) -> str:
        if float(self.degrees).is_integer():
            return f"{int(self.degrees)}deg"
        return f"{self.degrees:g}deg"


@dataclass(frozen=True)
class DomainSpec:
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    @property
    def label(self) -> str:
        return (
            f"lon{self.lon_min:g}_{self.lon_max:g}_"
            f"lat{self.lat_min:g}_{self.lat_max:g}"
        )
