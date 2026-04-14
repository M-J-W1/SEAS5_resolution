from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from seas5_resolution.config import DataPaths, DomainSpec
from seas5_resolution.io import available_initializations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEAS5 resolution sensitivity workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Summarize discovered hindcast starts")
    inspect_parser.add_argument("--limit", type=int, default=8, help="Number of start dates to print")

    run_parser = subparsers.add_parser("run", help="Run a skill calculation")
    run_parser.add_argument(
        "--resolution",
        type=float,
        required=True,
        choices=(0.25, 1.0, 3.0),
        help="Target analysis resolution in degrees",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional NetCDF output path",
    )
    run_parser.add_argument(
        "--max-starts",
        type=int,
        default=None,
        help="Optional limit on the number of hindcast initializations to process",
    )
    run_parser.add_argument(
        "--start-month",
        type=int,
        choices=range(1, 13),
        default=None,
        help="Optional calendar month filter for hindcast starts",
    )
    run_parser.add_argument(
        "--verification",
        choices=("matched", "fixed_025"),
        default="matched",
        help="Verification design: matched resolution or fixed 0.25-degree observations",
    )
    run_parser.add_argument("--lon-min", type=float, default=None, help="Optional domain minimum longitude")
    run_parser.add_argument("--lon-max", type=float, default=None, help="Optional domain maximum longitude")
    run_parser.add_argument("--lat-min", type=float, default=None, help="Optional domain minimum latitude")
    run_parser.add_argument("--lat-max", type=float, default=None, help="Optional domain maximum latitude")
    return parser


def cmd_inspect(limit: int) -> int:
    paths = DataPaths()
    starts = available_initializations(paths)
    print(f"Discovered {len(starts)} shared SSH initializations")
    print("First starts:")
    for value in starts[:limit]:
        print(f"  {value}")
    print("Last starts:")
    for value in starts[-limit:]:
        print(f"  {value}")
    return 0


def cmd_run(
    resolution: float,
    output: Path | None,
    max_starts: int | None,
    start_month: int | None,
    domain: DomainSpec | None,
    verification: str,
) -> int:
    from seas5_resolution.pipeline import run_native_to_quarter_degree_skill, run_regular_grid_skill

    paths = DataPaths()
    if resolution == 0.25:
        ds = run_native_to_quarter_degree_skill(
            paths,
            max_initializations=max_starts,
            start_month=start_month,
            domain=domain,
            output_path=output,
        )
    else:
        ds = run_regular_grid_skill(
            paths,
            resolution_deg=resolution,
            max_initializations=max_starts,
            start_month=start_month,
            domain=domain,
            verification=verification,
            output_path=output,
        )

    print(ds)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    domain = None
    domain_values = [args.lon_min, args.lon_max, args.lat_min, args.lat_max]
    if any(value is not None for value in domain_values):
        if not all(value is not None for value in domain_values):
            raise ValueError("All of --lon-min, --lon-max, --lat-min, and --lat-max are required together")
        domain = DomainSpec(
            lon_min=args.lon_min,
            lon_max=args.lon_max,
            lat_min=args.lat_min,
            lat_max=args.lat_max,
        )
    if args.command == "inspect":
        return cmd_inspect(args.limit)
    if args.command == "run":
        return cmd_run(
            args.resolution,
            args.output,
            args.max_starts,
            args.start_month,
            domain,
            args.verification,
        )
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
