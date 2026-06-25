from __future__ import annotations

import json
import math
import os
from pathlib import Path
from statistics import mean
from typing import Any


GRID_KEYS = {
    "solar_radiation": ("solar_radiation", "solarRadiation", "solar", "radiation"),
    "direct_sun_hours": ("direct_sun_hours", "directSunHours", "sun_hours"),
    "sky_view_factor": ("sky_view_factor", "skyViewFactor", "svf"),
    "wind_speed": ("wind_speed", "windSpeed", "wind"),
    "utci": ("utci", "thermal_comfort", "thermalComfort"),
}


def _flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        result: list[float] = []
        for item in value:
            result.extend(_flatten_numbers(item))
        return result
    return []


def _grid_stats(value: Any) -> dict:
    if isinstance(value, dict) and any(key in value for key in ("mean", "max", "min")):
        return {
            "available": value.get("available", value.get("mean") is not None or value.get("max") is not None),
            "min": value.get("min"),
            "mean": value.get("mean"),
            "max": value.get("max"),
            "grid_shape": value.get("grid_shape"),
            "raw_grid_shape": value.get("raw_grid_shape"),
            "legend_min": value.get("legend_min"),
            "legend_max": value.get("legend_max"),
            "succeeded_jobs": value.get("succeeded_jobs"),
            "total_jobs": value.get("total_jobs"),
            "bounds": value.get("bounds"),
            "cells": value.get("cells", []),
            "cell_source": value.get("cell_source"),
            "downsample_step": value.get("downsample_step"),
        }
    numbers = [number for number in _flatten_numbers(value) if number == number]
    if not numbers:
        return {"available": False}
    return {
        "available": True,
        "min": round(min(numbers), 3),
        "mean": round(mean(numbers), 3),
        "max": round(max(numbers), 3),
    }

def _grid_to_normalized_cells(value: Any, max_size: int = 64) -> dict:
    """Return a compact viewer-ready raster from an Infrared merged_grid.

    Infrared results can be dense 2D arrays. The risk-map checkpoint only needs
    enough cells to show the spatial pattern, so we keep a downsampled normalized
    grid and preserve the raw value on each cell for inspection.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list) or not value or not isinstance(value[0], list):
        return {"cells": [], "raw_grid_shape": []}

    rows = len(value)
    cols = max((len(row) for row in value), default=0)
    if not rows or not cols:
        return {"cells": [], "raw_grid_shape": [rows, cols]}

    y_step = max(1, math.ceil(rows / max_size))
    x_step = max(1, math.ceil(cols / max_size))
    sampled: list[tuple[int, int, float]] = []
    for y in range(0, rows, y_step):
        row = value[y]
        if not isinstance(row, list):
            continue
        for x in range(0, len(row), x_step):
            try:
                number = float(row[x])
            except (TypeError, ValueError):
                continue
            if number == number:
                sampled.append((x // x_step, y // y_step, number))

    if not sampled:
        return {"cells": [], "raw_grid_shape": [rows, cols]}

    minimum = min(number for _, _, number in sampled)
    maximum = max(number for _, _, number in sampled)
    spread = maximum - minimum or 1.0
    cells = [
        {
            "x": x,
            "y": y,
            "value": round((number - minimum) / spread, 3),
            "raw_value": round(number, 3),
        }
        for x, y, number in sampled
    ]
    return {
        "cells": cells,
        "raw_grid_shape": [rows, cols],
        "grid_size": max(max(cell["x"] for cell in cells), max(cell["y"] for cell in cells)) + 1,
        "downsample_step": [y_step, x_step],
        "cell_source": "infrared_result.merged_grid",
    }

def _as_fraction(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return round(max(0.0, min(1.0, number)), 3)


def _normalize_fraction_stats(stats: dict) -> dict:
    normalized = dict(stats or {})
    for key in ("min", "mean", "max", "legend_min", "legend_max"):
        value = _as_fraction(normalized.get(key))
        if value is not None:
            normalized[key] = value
    return normalized


def _normalized_heat_score(metrics: dict) -> float | None:
    solar_score = _score_from_stats(metrics.get("solar_radiation", {}), high_value=850.0)
    utci_score = _score_from_stats(metrics.get("utci", {}), high_value=42.0, low_value=26.0)
    svf_score = None
    sky_view = metrics.get("sky_view_factor", {})
    if sky_view.get("available"):
        mean_svf = _as_fraction(sky_view.get("mean"))
        if mean_svf is not None:
            svf_score = round(1.0 - mean_svf, 3)
    available_scores = [score for score in [solar_score, utci_score, svf_score] if score is not None]
    return round(sum(available_scores) / len(available_scores), 3) if available_scores else None


def normalize_existing_infrared_context(payload: dict) -> dict:
    """Normalize already-cached Infrared City summaries into project units."""
    normalized = json.loads(json.dumps(payload))
    metrics = normalized.setdefault("metrics", {})
    if "sky_view_factor" in metrics:
        metrics["sky_view_factor"] = _normalize_fraction_stats(metrics["sky_view_factor"])

    sky_view_mean = metrics.get("sky_view_factor", {}).get("mean")
    urban_updates = normalized.setdefault("urban_context_updates", {})
    if sky_view_mean is not None:
        urban_updates["sky_view_factor"] = sky_view_mean

    heat_score = _normalized_heat_score(metrics)
    if heat_score is not None:
        normalized["heat_exposure_score"] = heat_score
    normalized["unit_normalization"] = {
        "sky_view_factor": "fraction_0_to_1",
        "note": "Infrared City exports can provide sky-view as percent; HVRA stores it as a fraction.",
    }
    return normalized


def _first_grid(payload: dict, key_options: tuple[str, ...]) -> Any:
    for key in key_options:
        if key in payload:
            return payload[key]
        if "results" in payload and isinstance(payload["results"], dict) and key in payload["results"]:
            return payload["results"][key]
        if "grids" in payload and isinstance(payload["grids"], dict) and key in payload["grids"]:
            return payload["grids"][key]
    return None


def _score_from_stats(stats: dict, high_value: float, low_value: float = 0.0) -> float | None:
    if not stats.get("available"):
        return None
    value = float(stats.get("mean") or stats.get("max") or 0.0)
    if high_value <= low_value:
        return None
    return round(max(0.0, min(1.0, (value - low_value) / (high_value - low_value))), 3)


def polygon_from_center_size(latitude: float, longitude: float, width_m: float, length_m: float) -> dict:
    lat_delta = (length_m / 2.0) / 111_320
    lon_delta = (width_m / 2.0) / (111_320 * math.cos(math.radians(latitude)))
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


def _stats_from_area_result(result: Any) -> dict:
    grid = getattr(result, "merged_grid", None)
    stats = _grid_stats(grid.tolist() if hasattr(grid, "tolist") else grid)
    raster = _grid_to_normalized_cells(grid)
    stats.update(
        {
            "grid_shape": list(getattr(result, "grid_shape", []) or []),
            "raw_grid_shape": raster.get("raw_grid_shape"),
            "legend_min": getattr(result, "min_legend", None),
            "legend_max": getattr(result, "max_legend", None),
            "succeeded_jobs": getattr(result, "succeeded_jobs", None),
            "total_jobs": getattr(result, "total_jobs", None),
            "bounds": list(getattr(result, "bounds", []) or []),
            "cells": raster.get("cells", []),
            "cell_source": raster.get("cell_source"),
            "downsample_step": raster.get("downsample_step"),
        }
    )
    return stats


def normalize_infrared_payload(payload: dict, source: str) -> dict:
    """Normalize cached Infrared City result exports into the Risk Map contract."""
    metrics = {}
    for metric_name, key_options in GRID_KEYS.items():
        metrics[metric_name] = _grid_stats(_first_grid(payload, key_options))

    metrics["sky_view_factor"] = _normalize_fraction_stats(metrics.get("sky_view_factor", {}))
    heat_score = _normalized_heat_score(metrics)

    return {
        "available": heat_score is not None,
        "source": source,
        "provider": "infrared_city",
        "metrics": metrics,
        "heat_exposure_score": heat_score,
        "urban_context_updates": {
            "sky_view_factor": metrics["sky_view_factor"].get("mean"),
            "mean_wind_speed_m_s": metrics["wind_speed"].get("mean"),
            "infrared_city_utci_mean_c": metrics["utci"].get("mean"),
            "infrared_city_solar_radiation_mean": metrics["solar_radiation"].get("mean"),
            "infrared_city_direct_sun_hours_mean": metrics["direct_sun_hours"].get("mean"),
        },
        "climate_updates": {
            "infrared_city_utci_max_c": metrics["utci"].get("max"),
            "infrared_city_mean_wind_speed_m_s": metrics["wind_speed"].get("mean"),
            "infrared_city_solar_radiation_max": metrics["solar_radiation"].get("max"),
        },
    }


def run_live_infrared_city_context(
    *,
    latitude: float,
    longitude: float,
    bbox_radius_m: float,
    api_key: str,
    base_url: str | None = None,
    cache_json: str | None = None,
) -> dict:
    """Run a compact live Infrared City analysis for the Risk Map.

    The live run uses a single-month July afternoon window to respect current
    Infrared SDK constraints for UTCI, solar radiation, and sun-hours analyses.
    Results are saved as normalized statistics plus compact downsampled grid
    cells so the Risk Map can draw real analysis rasters without huge JSON.
    """
    if not api_key:
        return {"available": False, "source": "infrared_city_live", "reason": "Missing API key."}

    try:
        from infrared_sdk import InfraredClient
        from infrared_sdk.analyses.types import (
            AnalysesName,
            BaseAnalysisPayload,
            SolarModelRequest,
            SolarRadiationModelRequest,
            SvfModelRequest,
            UtciModelBaseRequest,
            UtciModelRequest,
            WindModelRequest,
        )
        from infrared_sdk.models import Location, TimePeriod
    except ModuleNotFoundError as error:
        return {
            "available": False,
            "source": "infrared_city_live",
            "reason": f"infrared-sdk is not installed: {error}",
        }

    os.environ.setdefault("INFRARED_API_KEY", api_key)
    if base_url:
        os.environ.setdefault("INFRARED_BASE_URL", base_url)
    width_m = max(80.0, min(float(bbox_radius_m) * 2.0, 500.0))
    polygon = polygon_from_center_size(latitude, longitude, width_m, width_m)
    time_period = TimePeriod(
        start_month=7,
        start_day=1,
        start_hour=12,
        end_month=7,
        end_day=31,
        end_hour=16,
    )
    location = Location(latitude=latitude, longitude=longitude)

    try:
        with InfraredClient(api_key=api_key) as client:
            buildings = client.buildings.get_area(polygon)
            vegetation = client.vegetation.get_area(polygon)
            ground_materials = client.ground_materials.get_area(polygon)
            ground_layers = ground_materials.layers if ground_materials.total_features <= 5000 else {}

            stations = client.weather.get_weather_file_from_location(
                lat=latitude,
                lon=longitude,
                radius=50,
            )
            weather_data = []
            weather_id = None
            if stations:
                weather_id = stations[0].get("uuid") or stations[0].get("identifier")
                if weather_id:
                    weather_data = client.weather.filter_weather_data(
                        identifier=weather_id,
                        time_period=time_period,
                    )

            payloads = [
                WindModelRequest(
                    analysis_type=AnalysesName.wind_speed,
                    wind_speed=8,
                    wind_direction=270,
                ),
                SvfModelRequest(
                    analysis_type=AnalysesName.sky_view_factors,
                    latitude=latitude,
                    longitude=longitude,
                ),
                SolarModelRequest(
                    analysis_type=AnalysesName.direct_sun_hours,
                    latitude=latitude,
                    longitude=longitude,
                    time_period=time_period,
                ),
            ]
            if weather_data:
                payloads.extend(
                    [
                        SolarRadiationModelRequest.from_weatherfile_payload(
                            payload=BaseAnalysisPayload(analysis_type=AnalysesName.solar_radiation),
                            location=location,
                            time_period=time_period,
                            weather_data=weather_data,
                        ),
                        UtciModelRequest.from_weatherfile_payload(
                            payload=UtciModelBaseRequest(
                                analysis_type=AnalysesName.thermal_comfort_index,
                            ),
                            location=location,
                            time_period=time_period,
                            weather_data=weather_data,
                        ),
                    ]
                )

            results = client.run_area_and_wait(
                payloads,
                polygon,
                buildings=buildings.buildings,
                vegetation=vegetation.features,
                ground_materials=ground_layers,
            )
    except Exception as error:
        return {"available": False, "source": "infrared_city_live", "reason": str(error)}

    results_by_type = {
        str(getattr(result, "analysis_type", f"analysis_{index}")): _stats_from_area_result(result)
        for index, result in enumerate(results)
    }
    payload = {
        "source": "infrared_city_live",
        "location": {"latitude": latitude, "longitude": longitude},
        "polygon": polygon,
        "time_period": {
            "start_month": 7,
            "start_day": 1,
            "start_hour": 12,
            "end_month": 7,
            "end_day": 31,
            "end_hour": 16,
        },
        "layers": {
            "building_count": getattr(buildings, "total_buildings", None),
            "tree_count": getattr(vegetation, "total_trees", None),
            "ground_material_feature_count": getattr(ground_materials, "total_features", None),
            "weather_station_id": weather_id,
        },
        "results": {
            "wind_speed": results_by_type.get("wind-speed", {}),
            "sky_view_factor": results_by_type.get("sky-view-factors", {}),
            "direct_sun_hours": results_by_type.get("direct-sun-hours", {}),
            "solar_radiation": results_by_type.get("solar-radiation", {}),
            "utci": results_by_type.get("thermal-comfort-index", {}),
        },
    }
    normalized = normalize_infrared_payload(payload, "infrared_city_live")
    normalized["raw_summary"] = payload
    if cache_json:
        path = Path(cache_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def load_infrared_city_context(cache_json: str | None) -> dict:
    """Load a local Infrared City export if available.

    Live API calls are intentionally kept outside this function until the exact
    project/account payload is known. The Risk Map can already consume cached
    API exports saved at INFRARED_CITY_CACHE_JSON.
    """
    if not cache_json:
        return {"available": False, "source": "infrared_city", "reason": "No cache path configured."}

    path = Path(cache_json)
    if not path.exists():
        return {
            "available": False,
            "source": "infrared_city",
            "reason": f"Cache export not found: {path}",
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {"available": False, "source": "infrared_city", "reason": f"Invalid JSON: {error}"}

    if payload.get("provider") == "infrared_city" and payload.get("metrics"):
        return normalize_existing_infrared_context(payload)
    return normalize_infrared_payload(payload, str(path))




