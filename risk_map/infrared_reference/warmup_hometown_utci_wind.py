"""Warm-up 1: run Infrared wind speed + UTCI over a hometown rectangle.

Edit location.json to choose the center point and rectangle dimensions.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any


WARMUP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WARMUP_DIR.parent
DEFAULT_CONFIG_PATH = WARMUP_DIR / "location.json"
HTML_PATH = WARMUP_DIR / "warmup_hometown_results.html"

DEFAULT_LOCATION: dict[str, Any] = {
    "name": "Taichung, Taiwan",
    "latitude": 24.1477,
    "longitude": 120.6736,
    "width_m": 870,
    "length_m": 510,
}

UTCI_TIME_PERIOD_PARAMS = {
    "start_month": 7,
    "start_day": 1,
    "start_hour": 12,
    "end_month": 7,
    "end_day": 31,
    "end_hour": 16,
}


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(WARMUP_DIR / ".env")


def import_infrared_deps() -> dict[str, Any]:
    try:
        from infrared_sdk import InfraredClient
        from infrared_sdk.analyses.types import (
            AnalysesName,
            UtciModelBaseRequest,
            UtciModelRequest,
            WindModelRequest,
        )
        from infrared_sdk.models import Location, TimePeriod
    except ModuleNotFoundError as exc:
        missing = exc.name or "a dependency"
        print(
            f"Missing {missing}. Install dependencies with: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    return {
        "AnalysesName": AnalysesName,
        "InfraredClient": InfraredClient,
        "Location": Location,
        "TimePeriod": TimePeriod,
        "UtciModelBaseRequest": UtciModelBaseRequest,
        "UtciModelRequest": UtciModelRequest,
        "WindModelRequest": WindModelRequest,
    }


def polygon_from_center_size(
    latitude: float,
    longitude: float,
    width_m: float,
    length_m: float,
) -> dict[str, Any]:
    lat_delta = (length_m / 2) / 111_320
    lon_delta = (width_m / 2) / (111_320 * math.cos(math.radians(latitude)))
    min_lat = latitude - lat_delta
    max_lat = latitude + lat_delta
    min_lon = longitude - lon_delta
    max_lon = longitude + lon_delta

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def load_location_config(path: Path | None) -> dict[str, Any]:
    location = dict(DEFAULT_LOCATION)
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return with_generated_polygon(location)

    with config_path.open(encoding="utf-8") as file:
        overrides = json.load(file)

    for key in ("name", "latitude", "longitude", "width_m", "length_m"):
        if key in overrides:
            location[key] = overrides[key]
    return with_generated_polygon(location)


def with_generated_polygon(location: dict[str, Any]) -> dict[str, Any]:
    location["polygon"] = polygon_from_center_size(
        latitude=float(location["latitude"]),
        longitude=float(location["longitude"]),
        width_m=float(location["width_m"]),
        length_m=float(location["length_m"]),
    )
    return location


def build_location(args: argparse.Namespace) -> dict[str, Any]:
    location = load_location_config(args.location_config)

    if args.location_name:
        location["name"] = args.location_name
    if args.lat is not None:
        location["latitude"] = args.lat
    if args.lon is not None:
        location["longitude"] = args.lon
    if args.width_m is not None:
        location["width_m"] = args.width_m
    if args.length_m is not None:
        location["length_m"] = args.length_m

    location = with_generated_polygon(location)

    return location


def validate_location(location: dict[str, Any]) -> None:
    missing = [
        key
        for key in ("name", "latitude", "longitude", "width_m", "length_m", "polygon")
        if key not in location
    ]
    if missing:
        raise ValueError(f"Location is missing required field(s): {', '.join(missing)}")

    if float(location["width_m"]) <= 0 or float(location["length_m"]) <= 0:
        raise ValueError("width_m and length_m must be positive numbers")

    polygon = location["polygon"]
    if polygon.get("type") != "Polygon":
        raise ValueError("Location polygon must be a GeoJSON Polygon")

    rings = polygon.get("coordinates")
    if not rings or not rings[0] or len(rings[0]) < 4:
        raise ValueError("Location polygon must contain a closed exterior ring")

    if rings[0][0] != rings[0][-1]:
        raise ValueError("Location polygon ring must be closed: first point must equal last point")


def finite_stats(grid: Any) -> dict[str, float | int | None]:
    import numpy as np

    values = np.asarray(grid, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"count": 0, "min": None, "mean": None, "max": None}
    return {
        "count": int(finite.size),
        "min": float(np.nanmin(finite)),
        "mean": float(np.nanmean(finite)),
        "max": float(np.nanmax(finite)),
    }


def legend_bounds(result: Any) -> tuple[float | None, float | None]:
    zmin = result.min_legend
    zmax = result.max_legend
    return (
        float(zmin) if zmin is not None else None,
        float(zmax) if zmax is not None else None,
    )


def write_outputs(wind_result: Any, utci_result: Any, metadata: dict[str, Any]) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    summary = {
        "location": metadata,
        "wind": {
            "units": "m/s",
            "grid_shape": list(wind_result.grid_shape),
            "legend": list(legend_bounds(wind_result)),
            "stats": finite_stats(wind_result.merged_grid),
            "succeeded_jobs": wind_result.succeeded_jobs,
            "total_jobs": wind_result.total_jobs,
        },
        "utci": {
            "units": "degC UTCI",
            "grid_shape": list(utci_result.grid_shape),
            "legend": list(legend_bounds(utci_result)),
            "stats": finite_stats(utci_result.merged_grid),
            "succeeded_jobs": utci_result.succeeded_jobs,
            "total_jobs": utci_result.total_jobs,
        },
    }

    print(json.dumps(summary, indent=2))

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Wind speed (m/s)", "UTCI (degC)"),
    )
    fig.add_trace(
        go.Heatmap(
            z=wind_result.merged_grid,
            colorscale="Turbo",
            zmin=wind_result.min_legend,
            zmax=wind_result.max_legend,
            colorbar=dict(title="m/s", x=0.46),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Heatmap(
            z=utci_result.merged_grid,
            colorscale="RdBu_r",
            zmin=utci_result.min_legend,
            zmax=utci_result.max_legend,
            colorbar=dict(title="degC"),
        ),
        row=1,
        col=2,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1, row=1, col=1)
    fig.update_yaxes(scaleanchor="x2", scaleratio=1, row=1, col=2)
    fig.update_layout(
        title=f"{metadata['name']} | Infrared warm-up 1",
        width=1200,
        height=620,
        template="plotly_white",
    )
    fig.write_html(HTML_PATH, include_plotlyjs=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print request details only")
    parser.add_argument(
        "--location-config",
        type=Path,
        help="JSON file with name, latitude, longitude, width_m, and length_m fields",
    )
    parser.add_argument("--location-name", help="Override the location name")
    parser.add_argument("--lat", type=float, help="Override the location latitude")
    parser.add_argument("--lon", type=float, help="Override the location longitude")
    parser.add_argument("--width-m", type=float, help="Override rectangle width in meters")
    parser.add_argument("--length-m", type=float, help="Override rectangle length in meters")
    parser.add_argument("--wind-speed", type=int, default=8, help="Wind speed in m/s")
    parser.add_argument(
        "--wind-direction",
        type=int,
        default=270,
        help="Meteorological direction in degrees; 270 means wind from west",
    )
    args = parser.parse_args()

    load_env()
    location = build_location(args)
    validate_location(location)

    metadata = {
        "name": location["name"],
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "width_m": location["width_m"],
        "length_m": location["length_m"],
        "polygon": location["polygon"],
        "utci_time_period": UTCI_TIME_PERIOD_PARAMS,
        "wind_speed": args.wind_speed,
        "wind_direction": args.wind_direction,
    }

    if args.dry_run:
        print(json.dumps(metadata, indent=2))
        return 0

    if not os.getenv("INFRARED_API_KEY"):
        print(
            "INFRARED_API_KEY is not set. Add it to .env or the shell environment.",
            file=sys.stderr,
        )
        return 2

    deps = import_infrared_deps()
    AnalysesName = deps["AnalysesName"]
    InfraredClient = deps["InfraredClient"]
    Location = deps["Location"]
    TimePeriod = deps["TimePeriod"]
    UtciModelBaseRequest = deps["UtciModelBaseRequest"]
    UtciModelRequest = deps["UtciModelRequest"]
    WindModelRequest = deps["WindModelRequest"]
    utci_time_period = TimePeriod(**UTCI_TIME_PERIOD_PARAMS)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )
    logger = logging.getLogger("warmup_hometown")

    with InfraredClient(logger=logger) as client:
        logger.info("Fetching buildings, vegetation, and ground materials for %s", location["name"])
        buildings = client.buildings.get_area(location["polygon"])
        vegetation = client.vegetation.get_area(location["polygon"])
        ground_materials = client.ground_materials.get_area(location["polygon"])

        logger.info(
            "Fetched buildings=%d, trees=%d, ground features=%d",
            buildings.total_buildings,
            vegetation.total_trees,
            ground_materials.total_features,
        )

        logger.info("Running wind-speed analysis")
        wind_result = client.run_area_and_wait(
            WindModelRequest(
                analysis_type=AnalysesName.wind_speed,
                wind_speed=args.wind_speed,
                wind_direction=args.wind_direction,
            ),
            location["polygon"],
            buildings=buildings.buildings,
        )

        logger.info("Finding nearest weather station for UTCI")
        stations = client.weather.get_weather_file_from_location(
            lat=location["latitude"],
            lon=location["longitude"],
            radius=50,
        )
        if not stations:
            raise RuntimeError("No weather station found within 50 km")

        station = stations[0]
        weather_id = station.get("uuid") or station.get("identifier")
        if not weather_id:
            raise RuntimeError(f"Weather station has no usable identifier: {station}")

        logger.info("Using weather station %s", station.get("fileName") or weather_id)
        weather_data = client.weather.filter_weather_data(
            identifier=weather_id,
            time_period=utci_time_period,
        )

        utci_payload = UtciModelRequest.from_weatherfile_payload(
            payload=UtciModelBaseRequest(
                analysis_type=AnalysesName.thermal_comfort_index,
            ),
            location=Location(latitude=location["latitude"], longitude=location["longitude"]),
            time_period=utci_time_period,
            weather_data=weather_data,
        )

        logger.info("Running UTCI analysis")
        utci_result = client.run_area_and_wait(
            utci_payload,
            location["polygon"],
            buildings=buildings.buildings,
            vegetation=vegetation.features,
            ground_materials=ground_materials.layers,
        )

    write_outputs(wind_result, utci_result, metadata)
    logger.info("Wrote %s", HTML_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
