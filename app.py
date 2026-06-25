from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import struct
import zipfile
from pathlib import Path
from typing import Any, List

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
IMAGES_DIR = INPUT_DIR / "images"
OUTPUT_DIR = DATA_DIR / "output"
INTERMEDIATE_DIR = DATA_DIR / "intermediate"
RISK_MAP_DATASET_DIR = ROOT_DIR / "risk_map" / "dataset"
RISK_MAP_TEST_DIR = ROOT_DIR / "interface" / "public" / "interface" / "risk_map_3d_test"
THREE_D_TEST_DIR = ROOT_DIR / "3D_test"
THREE_DIR = ROOT_DIR / "interface" / "node_modules" / "three"
THREE_PUBLIC_DIR = ROOT_DIR / "interface" / "public" / "vendor" / "three"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="HVRA Interface API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static-views", StaticFiles(directory=OUTPUT_DIR), name="static-views")
app.mount("/input-assets", StaticFiles(directory=INPUT_DIR), name="input-assets")
if RISK_MAP_TEST_DIR.exists():
    app.mount("/risk-map-3d-test", StaticFiles(directory=RISK_MAP_TEST_DIR, html=True), name="risk-map-3d-test")
if THREE_D_TEST_DIR.exists():
    app.mount("/3d-test", StaticFiles(directory=THREE_D_TEST_DIR, html=True), name="three-d-test")
if THREE_DIR.exists():
    app.mount("/vendor/three", StaticFiles(directory=THREE_DIR), name="three-js")
elif THREE_PUBLIC_DIR.exists():
    app.mount("/vendor/three", StaticFiles(directory=THREE_PUBLIC_DIR), name="three-js")




def _env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value.strip().strip('"').strip("'")
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return default
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, item = line.split("=", 1)
        if key.strip() == name:
            return item.strip().strip('"').strip("'")
    return default


def _polygon_from_center_size(latitude: float, longitude: float, width_m: float, length_m: float) -> dict:
    lat_delta = (length_m / 2.0) / 111_320
    lon_delta = (width_m / 2.0) / (111_320 * math.cos(math.radians(latitude)))
    min_lat = latitude - lat_delta
    max_lat = latitude + lat_delta
    min_lon = longitude - lon_delta
    max_lon = longitude + lon_delta
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]],
    }


def _mesh_to_footprint(building_id: str, mesh: Any) -> dict | None:
    if hasattr(mesh, "to_dict"):
        mesh_dict = mesh.to_dict()
    elif isinstance(mesh, dict):
        mesh_dict = mesh
    else:
        return None
    coords = mesh_dict.get("coordinates") or []
    if not coords:
        return None
    triples = []
    if coords and isinstance(coords[0], list):
        triples = [tuple(point[:3]) for point in coords if len(point) >= 3]
    else:
        triples = [tuple(coords[index:index + 3]) for index in range(0, len(coords) - 2, 3)]
    points = []
    for x, y, z in triples:
        try:
            points.append((float(x), float(y), float(z)))
        except (TypeError, ValueError):
            continue
    if not points:
        return None
    min_z = min(point[2] for point in points)
    max_z = max(point[2] for point in points)
    height = max(1.0, max_z - min_z)
    base = [(round(point[0], 3), round(point[1], 3)) for point in points if abs(point[2] - min_z) < 0.25]
    if len(base) < 3:
        base = [(round(point[0], 3), round(point[1], 3)) for point in points]
    unique = []
    seen = set()
    for point in base:
        if point not in seen:
            seen.add(point)
            unique.append(point)
    if len(unique) < 3:
        return None
    cx = sum(point[0] for point in unique) / len(unique)
    cy = sum(point[1] for point in unique) / len(unique)
    unique.sort(key=lambda point: math.atan2(point[1] - cy, point[0] - cx))
    return {
        "id": str(building_id),
        "footprint_m": [[round(x, 3), round(y, 3)] for x, y in unique],
        "height_m": round(height, 3),
        "centroid_m": [round(cx, 3), round(cy, 3)],
    }


def _normalize_tree_features(features: Any) -> list[dict]:
    if isinstance(features, dict):
        iterable = features.values()
    elif isinstance(features, list):
        iterable = features
    else:
        iterable = []
    trees = []
    for index, feature in enumerate(iterable):
        geom = (feature or {}).get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        props = (feature or {}).get("properties") or {}
        trees.append({
            "id": str((feature or {}).get("id") or f"tree_{index + 1}"),
            "lon": coords[0],
            "lat": coords[1],
            "height_m": _first_number(props.get("height"), 4.0),
            "crown_diameter_m": _first_number(props.get("diameter_crown"), props.get("crown_diameter"), 3.0),
        })
    return trees


def _load_or_fetch_infrared_geometry(latitude: float, longitude: float, bbox_radius_m: float) -> dict:
    cache_path = RISK_MAP_DATASET_DIR / "infrared_city" / "infrared_city_geometry.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("buildings") or cached.get("available") is False:
                return cached
        except json.JSONDecodeError:
            pass

    api_key = _env_value("INFRARED_API_KEY") or _env_value("INFRARED_CITY_API_KEY")
    if not api_key:
        payload = {"available": False, "source": "infrared_city_geometry", "reason": "Missing Infrared City API key."}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    try:
        from infrared_sdk import InfraredClient
    except ModuleNotFoundError as error:
        payload = {"available": False, "source": "infrared_city_geometry", "reason": f"infrared-sdk unavailable: {error}"}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    width_m = max(80.0, min(float(bbox_radius_m) * 2.0, 500.0))
    polygon = _polygon_from_center_size(latitude, longitude, width_m, width_m)
    try:
        with InfraredClient(api_key=api_key) as client:
            area = client.buildings.get_area(polygon)
            vegetation = client.vegetation.get_area(polygon)
    except Exception as error:
        payload = {"available": False, "source": "infrared_city_geometry", "reason": str(error)}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    buildings = []
    for building_id, mesh in getattr(area, "buildings", {}).items():
        footprint = _mesh_to_footprint(str(building_id), mesh)
        if footprint:
            buildings.append(footprint)
    payload = {
        "available": bool(buildings),
        "source": "infrared_city_geometry_live",
        "provider": "infrared_city",
        "polygon": polygon,
        "coordinate_frame": "meters_from_polygon_south_west",
        "total_buildings": getattr(area, "total_buildings", len(buildings)),
        "buildings": buildings,
        "trees": _normalize_tree_features(getattr(vegetation, "features", {})),
        "tree_count": getattr(vegetation, "total_trees", None),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload




def _lonlat_to_local_m(lon: float, lat: float, center_lon: float, center_lat: float) -> list[float]:
    earth_radius = 6_378_137.0
    x = math.radians(lon - center_lon) * earth_radius * math.cos(math.radians(center_lat))
    z = -math.radians(lat - center_lat) * earth_radius
    return [round(x, 3), round(z, 3)]


def _shape_parts_from_shp_record(content: bytes) -> tuple[int, tuple[float, float, float, float], list[list[tuple[float, float]]]] | None:
    if len(content) < 44:
        return None
    shape_type = struct.unpack('<i', content[:4])[0]
    if shape_type not in {3, 5}:  # PolyLine, Polygon
        return None
    xmin, ymin, xmax, ymax = struct.unpack('<4d', content[4:36])
    num_parts, num_points = struct.unpack('<2i', content[36:44])
    if num_parts <= 0 or num_points <= 0:
        return None
    parts_offset = 44
    points_offset = parts_offset + num_parts * 4
    if len(content) < points_offset + num_points * 16:
        return None
    part_starts = list(struct.unpack(f'<{num_parts}i', content[parts_offset:points_offset]))
    points = [struct.unpack('<2d', content[points_offset + index * 16:points_offset + index * 16 + 16]) for index in range(num_points)]
    part_starts.append(num_points)
    parts = []
    for index in range(num_parts):
        part = points[part_starts[index]:part_starts[index + 1]]
        if len(part) >= 2:
            parts.append(part)
    return shape_type, (xmin, ymin, xmax, ymax), parts


def _bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _read_shp_contours(
    *,
    zip_path: Path,
    shp_name: str,
    bbox: tuple[float, float, float, float],
    center_lon: float,
    center_lat: float,
    max_features: int,
    simplify_every: int = 1,
) -> list[dict]:
    if not zip_path.exists():
        return []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            data = archive.read(shp_name)
    except Exception:
        return []
    contours = []
    offset = 100
    while offset + 8 < len(data) and len(contours) < max_features:
        try:
            _record_number, content_words = struct.unpack('>2i', data[offset:offset + 8])
        except struct.error:
            break
        offset += 8
        content_length = content_words * 2
        content = data[offset:offset + content_length]
        offset += content_length
        parsed = _shape_parts_from_shp_record(content)
        if not parsed:
            continue
        _shape_type, record_bbox, parts = parsed
        if not _bbox_intersects(record_bbox, bbox):
            continue
        for part_index, part in enumerate(parts):
            sampled = part[::max(1, simplify_every)]
            if sampled[-1] != part[-1]:
                sampled.append(part[-1])
            local_points = [_lonlat_to_local_m(lon, lat, center_lon, center_lat) for lon, lat in sampled]
            if len(local_points) >= 2:
                contours.append({"id": f"{Path(shp_name).stem}_{len(contours)}_{part_index}", "points_m": local_points})
            if len(contours) >= max_features:
                break
    return contours


def _local_osm_visual_geometry(latitude: float, longitude: float, radius_m: float) -> dict:
    cache_dir = RISK_MAP_DATASET_DIR / "visual_cache"
    cache_path = cache_dir / f"osm_visual_{latitude:.5f}_{longitude:.5f}_{int(radius_m)}.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("available") and cached.get("visual_cache_version") == 2 and cached.get("context_contours"):
                return cached
        except json.JSONDecodeError:
            pass

    zip_path = RISK_MAP_DATASET_DIR / "cataluna-260528-free.shp.zip"
    city_bbox = (2.05, 41.30, 2.25, 41.48)
    cos_lat = math.cos(math.radians(latitude))
    lat_delta = (radius_m / 111_320)
    lon_delta = (radius_m / (111_320 * cos_lat)) if cos_lat else 0.003
    local_bbox = (longitude - lon_delta, latitude - lat_delta, longitude + lon_delta, latitude + lat_delta)
    context_radius_m = max(radius_m * 2.0, 500.0)
    context_lat_delta = context_radius_m / 111_320
    context_lon_delta = (context_radius_m / (111_320 * cos_lat)) if cos_lat else 0.006
    context_bbox = (
        longitude - context_lon_delta,
        latitude - context_lat_delta,
        longitude + context_lon_delta,
        latitude + context_lat_delta,
    )
    city_roads = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_roads_free_1.shp",
        bbox=city_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=1400,
        simplify_every=6,
    )
    city_buildings = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_buildings_a_free_1.shp",
        bbox=city_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=1600,
        simplify_every=2,
    )
    local_buildings = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_buildings_a_free_1.shp",
        bbox=local_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=500,
        simplify_every=1,
    )
    local_roads = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_roads_free_1.shp",
        bbox=local_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=300,
        simplify_every=1,
    )
    context_buildings = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_buildings_a_free_1.shp",
        bbox=context_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=1200,
        simplify_every=1,
    )
    context_roads = _read_shp_contours(
        zip_path=zip_path,
        shp_name="gis_osm_roads_free_1.shp",
        bbox=context_bbox,
        center_lon=longitude,
        center_lat=latitude,
        max_features=700,
        simplify_every=1,
    )
    estimated_buildings = []
    for index, outline in enumerate(local_buildings):
        points = outline.get("points_m") or []
        if len(points) >= 3:
            estimated_buildings.append({
                "id": f"osm_local_{index:03d}",
                "footprint_m": points,
                "height_m": 10 + (index % 7) * 2.8,
                "height_source": "estimated_from_missing_height_attribute",
            })
    payload = {
        "available": bool(city_roads or city_buildings or estimated_buildings),
        "visual_cache_version": 2,
        "source": "local_osm_shapefile_cataluna_260528",
        "city_contours": {
            "source": "local_osm_shapefile_cataluna_260528",
            "extent": "barcelona_bbox_2.05_41.30_2.25_41.48",
            "roads": city_roads,
            "building_outlines": city_buildings,
        },
        "context_contours": {
            "source": "local_osm_shapefile_cataluna_260528",
            "extent_m": context_radius_m * 2.0,
            "roads": context_roads,
            "building_outlines": context_buildings,
        },
        "local_contours": {
            "source": "local_osm_shapefile_cataluna_260528",
            "radius_m": radius_m,
            "roads": local_roads,
            "building_outlines": local_buildings,
        },
        "estimated_3d_buildings": {
            "available": bool(estimated_buildings),
            "source": "local_osm_footprints_with_estimated_heights",
            "buildings": estimated_buildings,
            "note": "Footprints are local OSM geometry. Heights are estimated because this shapefile has no height field.",
        },
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _barcelona_city_contours() -> dict:
    # Lightweight city-wide context used when live/vector-tile geometry is not available.
    # It spans Barcelona's approximate municipal extent and is deliberately labelled as a fallback.
    roads = []
    buildings = []
    for index in range(18):
        z = -5200 + index * 610
        roads.append({"id": f"city_ew_{index}", "kind": "street", "points_m": [[-6900, z], [6900, z + ((index % 3) - 1) * 90]]})
    for index in range(16):
        x = -6400 + index * 850
        roads.append({"id": f"city_ns_{index}", "kind": "street", "points_m": [[x, -5600], [x + ((index % 4) - 1.5) * 80, 5600]]})
    for index in range(280):
        col = index % 28
        row = index // 28
        x = -6500 + col * 480 + (row % 2) * 95
        z = -4600 + row * 720
        w = 150 + (index * 17) % 180
        d = 110 + (index * 29) % 170
        buildings.append({"id": f"city_b_{index:03d}", "points_m": [[x, z], [x + w, z], [x + w, z + d], [x, z + d], [x, z]]})
    return {
        "source": "fallback_city_contours_not_survey_geometry",
        "extent_m": 14000,
        "roads": roads,
        "building_outlines": buildings,
    }



def _detected_wall_count() -> int:
    for candidate in [INTERMEDIATE_DIR / "spatial_index.json", INTERMEDIATE_DIR / "spatial_index_with_overrides.json"]:
        try:
            if candidate.exists():
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                walls = payload.get("walls", [])
                if walls:
                    return len(walls)
        except Exception:
            continue
    return 0


def _normalize_display_wall_ids(payload: Any, wall_count: int | None = None) -> Any:
    """Convert UI display wall ids such as WALL_08 to zero-based engine ids WALL_07."""
    count = wall_count if wall_count is not None else _detected_wall_count()
    if isinstance(payload, list):
        return [_normalize_display_wall_ids(item, count) for item in payload]
    if isinstance(payload, dict):
        return {key: _normalize_display_wall_ids(value, count) for key, value in payload.items()}
    if not isinstance(payload, str) or count <= 0:
        return payload

    def repl(match: re.Match) -> str:
        ordinal = int(match.group(1))
        if ordinal >= count and 1 <= ordinal <= count:
            return f"ROOM_001_WALL_{ordinal - 1:02d}"
        return match.group(0)

    return re.sub(r"ROOM_001_WALL_(\d{2})(?!\d)", repl, payload)

class CheckpointAction(BaseModel):
    checkpoint: str = "08_strategy_validation"
    llm: bool = False
    apply: bool = True
    mock_llm: bool = False
    mock_gemini: bool = False
    mock_neo4j: bool = False


@app.post("/api/spatial/overrides")
async def save_spatial_overrides(payload: dict = Body(...)) -> JSONResponse:
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = _normalize_display_wall_ids(payload)
    destination = INTERMEDIATE_DIR / "spatial_user_overrides.json"
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return JSONResponse(
        {
            "status": "ok",
            "path": "data/intermediate/spatial_user_overrides.json",
            "message": "Room check saved. Press continue when you are ready to run diagnosis.",
        }
    )


@app.post("/api/spatial/continue")
async def continue_from_spatial(payload: dict = Body(...)) -> JSONResponse:
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = _normalize_display_wall_ids(payload)
    destination = INTERMEDIATE_DIR / "spatial_user_overrides.json"
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    try:
        _run_main_pipeline()
        _refresh_component_view_from_overrides()
    except subprocess.CalledProcessError as error:
        raise HTTPException(status_code=500, detail=error.stderr or error.stdout or str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    pipeline_status = _read_pipeline_status()
    current_stage = pipeline_status.get("current_stage", "processing")
    if current_stage == "spatial_vv":
        current_stage = "processing"
    return JSONResponse(
        {
            "status": "ok",
            "path": "data/intermediate/spatial_user_overrides.json",
            "current_stage": current_stage,
            "message": pipeline_status.get("message") or "Spatial check saved. Diagnosis and review outputs are ready.",
            "refresh_views": True,
        }
    )


@app.get("/api/status")
async def api_status() -> JSONResponse:
    pipeline_status = _read_pipeline_status()
    return JSONResponse(
        {
            "status": pipeline_status.get("status", "input_gathering"),
            "current_stage": pipeline_status.get("current_stage", "input_gathering"),
            "message": pipeline_status.get("message", ""),
            "primary_output": pipeline_status.get("primary_output"),
        }
    )


@app.get("/api/strategy-options")
async def api_strategy_options() -> JSONResponse:
    package_path = INTERMEDIATE_DIR / "phase3_strategy_packages.json"
    if package_path.exists():
        try:
            payload = json.loads(package_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        packages = payload.get("packages", [])
        if packages:
            return JSONResponse(
                {
                    "options": [
                        {
                            "rank": index,
                            "id": package.get("package_id") or f"package_{index}",
                            "label": f"option {index}",
                            "name": package.get("package_name") or f"option {index}",
                            "status": package.get("benchmark_status"),
                            "confidence": package.get("confidence_level"),
                            "component_ids": package.get("visual_generation", {}).get("component_ids", []),
                        }
                        for index, package in enumerate(packages[:3], start=1)
                    ]
                }
            )

    options_path = INTERMEDIATE_DIR / "retrofit_validation_options.json"
    if not options_path.exists():
        return JSONResponse({"options": []})

    try:
        payload = json.loads(options_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return JSONResponse({"options": []})

    options = []
    for index, option in enumerate(payload.get("validated_options", [])[:3], start=1):
        strategy = option.get("strategy", {})
        benchmark = option.get("benchmark_result", {})
        confidence = option.get("confidence", {})
        options.append(
            {
                "rank": index,
                "id": strategy.get("strategy_id") or f"option_{index}",
                "label": f"option {index}",
                "name": strategy.get("strategy_name") or f"option {index}",
                "status": benchmark.get("overall"),
                "confidence": confidence.get("level"),
            }
        )
    return JSONResponse({"options": options})



@app.get("/api/risk-map/context")
async def api_risk_map_context(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> JSONResponse:
    return JSONResponse(_build_risk_map_context_payload(address=address, lat=lat, lon=lon))

def _read_user_case() -> dict:
    user_case_path = INPUT_DIR / "user_case.json"
    if user_case_path.exists():
        try:
            return json.loads(user_case_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _write_user_case(payload: dict) -> None:
    user_case_path = INPUT_DIR / "user_case.json"
    user_case_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_building_info() -> dict:
    building_info_path = INPUT_DIR / "building_info.json"
    if building_info_path.exists():
        try:
            return json.loads(building_info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _write_building_info(payload: dict) -> None:
    building_info_path = INPUT_DIR / "building_info.json"
    building_info_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_region_context() -> dict:
    region_context_path = INPUT_DIR / "region_context.json"
    if region_context_path.exists():
        try:
            return json.loads(region_context_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _write_region_context(payload: dict) -> None:
    region_context_path = INPUT_DIR / "region_context.json"
    region_context_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _extract_coordinates(text: str) -> dict | None:
    lat_lon_pattern = re.search(
        r"lat(?:itude)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)\D+lon(?:gitude)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if lat_lon_pattern:
        return {"lat": float(lat_lon_pattern.group(1)), "lon": float(lat_lon_pattern.group(2))}

    pair_pattern = re.search(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", text)
    if pair_pattern:
        lat = float(pair_pattern.group(1))
        lon = float(pair_pattern.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return {"lat": lat, "lon": lon}
    return None


def _extract_location_text(text: str) -> str | None:
    explicit_pattern = re.search(
        r"\b(?:address|location|site)\s*[:=]\s*([^.;\n]+)",
        text,
        re.IGNORECASE,
    )
    if explicit_pattern:
        return explicit_pattern.group(1).strip(" ,")

    comma_parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(comma_parts) >= 2:
        first_part = comma_parts[0]
        if not re.search(r"\b(?:bedroom|living|kitchen|bathroom|office|room)\b", first_part, re.IGNORECASE):
            return first_part

    return None


def _extract_room_details(text: str) -> dict:
    details: dict[str, Any] = {}
    clean = text.lower()

    room_types = [
        "bedroom",
        "living room",
        "kitchen",
        "bathroom",
        "office",
        "study",
        "studio",
    ]
    for room_type in room_types:
        if re.search(rf"\b{re.escape(room_type)}\b", clean):
            details["room_type"] = room_type
            break

    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|m\^2|sqm|sq\.?\s*m|square\s*met(?:er|re)s?)\b", clean)
    if area_match:
        details["room_area_m2"] = float(area_match.group(1))

    height_match = re.search(r"(\d+(?:\.\d+)?)\s*m\s*(?:high|height|ceiling)", clean)
    if not height_match:
        height_match = re.search(r"(?:height|ceiling)\D{0,12}(\d+(?:\.\d+)?)\s*m\b", clean)
    if height_match:
        details["room_height_m"] = float(height_match.group(1))

    if re.search(r"\b(pre[- ]?1980|before\s+1980|1960|1970|pre[- ]?80)\b", clean):
        details["construction_era"] = "1960_1979"
    elif re.search(r"\b(1980|1990)\b", clean):
        details["construction_era"] = "1980_1999"
    elif re.search(r"\b(2000|2010|2020|post[- ]?2000|after\s+2000)\b", clean):
        details["construction_era"] = "post_2000"

    if re.search(r"\b(no\s+ac|without\s+ac|no\s+air\s*conditioning|without\s+air\s*conditioning)\b", clean):
        details["has_ac"] = False

    return details
def _read_json_object(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_group_payload(metadata: dict) -> list[dict]:
    groups = {
        "weather": [
            "ESP_Barcelona.081810_SWEC.epw",
            "ESP_CT_Barcelona-El.Prat.AP.081810_TMYx.2011-2025.zip",
            "2020_MeteoCat_Estacions.csv",
            "2025_MeteoCat_Detall_Estacions.csv",
        ],
        "boundaries": ["BCN_UNITATS_ADM.zip"],
        "urban_form": [
            "cataluna-260528-free.gpkg.zip",
            "cataluna-260528-free.shp.zip",
            "cataluna-260528.osm.pbf",
            "cataluna-260530-free.gpkg.zip",
            "MTM_GPKG_al?ades.zip",
            "2026_edificacions_superficie.csv",
        ],
        "green_blue": ["ab_vw_arbrat_geometries.csv", "2017_vegetacio.gpkg"],
        "cooling_access": [
            "2017_cobertura_espaisrefugi.gpkg",
            "2017_equip_refugi.gpkg",
            "2017_parcs_refugi.gpkg",
            "2017_vulnera_espaisrefugi.gpkg",
        ],
        "vulnerability": [
            "2017_factors_vulnera.gpkg",
            "ate_vulnera_75plus_od.gpkg",
            "2018_ate_densitat_75plus_od.gpkg",
            "ate_equip_20-34_od.gpkg",
            "ate_equip_35-74_od.gpkg",
        ],
        "thermal_comfort": ["confort_termic_od.gpkg"],
        "research": ["ijerph-17-02553-s001.zip"],
        "infrared_city": ["infrared_city/infrared_city_context.json"],
    }
    payload = []
    for group_id, files in groups.items():
        payload.append(
            {
                "id": group_id,
                "count": len(files),
                "files": files,
                "titles": [metadata.get(file_name, {}).get("source_title", file_name) for file_name in files],
            }
        )
    return payload


def _first_number(*values: object) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _clamp_number(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _grid_value(x: int, y: int, n: int, base: float, mode: str) -> float:
    cx = (x + 0.5) / n
    cy = (y + 0.5) / n
    center = 1.0 - min(1.0, (((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5 / 0.72))
    east_west = cx
    north_south = 1.0 - cy
    canyon_bands = 0.16 if 0.25 <= cx <= 0.74 and (0.30 <= cy <= 0.38 or 0.62 <= cy <= 0.70) else 0.0
    if mode == "temperature":
        return _clamp_number(base + center * 0.28 + canyon_bands + east_west * 0.12, 0, 1)
    if mode == "solar":
        return _clamp_number(base + east_west * 0.30 + center * 0.12 - north_south * 0.08, 0, 1)
    if mode == "wind":
        # Higher visual value means lower wind relief / more stagnant air.
        return _clamp_number(base + canyon_bands + center * 0.10 - north_south * 0.16, 0, 1)
    if mode == "utci":
        return _clamp_number(base + center * 0.24 + canyon_bands * 0.8 + east_west * 0.08, 0, 1)
    if mode == "canopy":
        return _clamp_number(base + (1.0 - east_west) * 0.22 + cy * 0.18, 0, 1)
    if mode == "direct_sun":
        return _clamp_number(base + east_west * 0.24 + center * 0.10, 0, 1)
    if mode == "sky_view":
        return _clamp_number(base + canyon_bands * 0.9 + center * 0.18, 0, 1)
    return _clamp_number(base, 0, 1)


def _build_context_grid(name: str, base: float, mode: str, n: int = 50) -> dict:
    cells = []
    for y in range(n):
        for x in range(n):
            cells.append({"x": x, "y": y, "value": round(_grid_value(x, y, n, base, mode), 3)})
    return {"id": name, "grid_size": n, "cell_size_m": round(500 / n, 2), "cells": cells, "source": "synthetic_screening_surface"}



def _raw_grid_cells(metric: dict, name: str) -> dict:
    """Convert cached raw grid cells to viewer cells only when they exist."""
    raw = metric.get("cells") or metric.get("grid") or metric.get("values")
    empty = {"id": name, "grid_size": 0, "cell_size_m": None, "cells": [], "source": "summary_only_no_spatial_raster"}
    if raw is None:
        return empty
    if isinstance(raw, dict):
        raw = raw.get("cells") or raw.get("values") or raw.get("grid")
    if not isinstance(raw, list) or not raw:
        return empty

    if isinstance(raw[0], dict):
        cells = []
        for item in raw:
            if item.get("value") is None:
                continue
            cells.append({
                "x": int(item.get("x", 0)),
                "y": int(item.get("y", 0)),
                "value": round(_clamp_number(float(item.get("value", 0.0)), 0, 1), 3),
            })
        n = int(max(max((cell["x"] for cell in cells), default=0), max((cell["y"] for cell in cells), default=0)) + 1)
        return {"id": name, "grid_size": n, "cell_size_m": round(500 / max(n, 1), 2), "cells": cells, "source": "raw_spatial_raster"}

    if isinstance(raw[0], list):
        flat_values = [float(value) for row in raw for value in row if value is not None]
        if not flat_values:
            return empty
        minimum = min(flat_values)
        maximum = max(flat_values)
        spread = maximum - minimum or 1.0
        cells = []
        for y, row in enumerate(raw):
            for x, value in enumerate(row):
                if value is not None:
                    cells.append({"x": x, "y": y, "value": round((float(value) - minimum) / spread, 3)})
        n = max(len(raw), max((len(row) for row in raw), default=0))
        return {"id": name, "grid_size": n, "cell_size_m": round(500 / max(n, 1), 2), "cells": cells, "source": "raw_spatial_raster"}

    return empty

def _metric_normalized(metric: dict, fallback: float, invert: bool = False) -> float:
    value = _first_number(metric.get("mean"), fallback) or fallback
    min_value = _first_number(metric.get("min"), metric.get("legend_min"), value - 1) or value - 1
    max_value = _first_number(metric.get("max"), metric.get("legend_max"), value + 1) or value + 1
    if max_value == min_value:
        return 0.5
    normalized = (value - min_value) / (max_value - min_value)
    if invert:
        normalized = 1.0 - normalized
    return _clamp_number(normalized, 0, 1)


def _build_risk_visual_context(metrics: dict, urban: dict, climate: dict, infrared: dict | None = None) -> dict:
    infrared = infrared or {}
    infrared_metrics = infrared.get("metrics", {}) if isinstance(infrared, dict) else {}
    tree_canopy = _first_number(metrics.get("tree_canopy_percent"), urban.get("tree_canopy_percent"), 6.5) or 6.5
    refuge_distance = _first_number(metrics.get("cooling_refuge_distance_m"), urban.get("cooling_refuge_distance_m"), 610) or 610
    peak_temp = _first_number(metrics.get("peak_dry_bulb_c"), climate.get("peak_dry_bulb_c"), 32.2) or 32.2
    solar_peak = _first_number(
        metrics.get("peak_global_horizontal_radiation_w_m2"),
        climate.get("peak_global_horizontal_radiation_w_m2"),
        955,
    ) or 955
    utci_mean = _first_number(metrics.get("utci_mean_c"), urban.get("infrared_city_utci_mean_c"), 29.0) or 29.0
    wind_mean = _first_number(urban.get("mean_wind_speed_m_s"), climate.get("mean_hot_season_wind_speed_m_s"), 1.0) or 1.0

    temperature_base = _clamp_number((peak_temp - 24.0) / 14.0, 0, 1)
    solar_base = _metric_normalized(infrared_metrics.get("solar_radiation", {}), solar_peak)
    wind_stagnation_base = _metric_normalized(infrared_metrics.get("wind_speed", {}), wind_mean, invert=True)
    utci_base = _metric_normalized(infrared_metrics.get("utci", {}), utci_mean)
    canopy_base = _clamp_number(tree_canopy / 35.0, 0, 1)
    direct_sun_base = _metric_normalized(infrared_metrics.get("direct_sun_hours", {}), 6.0)
    sky_view_base = _metric_normalized(infrared_metrics.get("sky_view_factor", {}), 0.55)

    tree_markers = []
    tree_count = int(round(_clamp_number(tree_canopy / 2.5, 2, 14)))
    for index in range(tree_count):
        tree_markers.append(
            {
                "id": f"T{index + 1:02d}",
                "x_pct": round(10 + (index * 17) % 78, 2),
                "y_pct": round(74 - (index * 11) % 34, 2),
                "canopy_m": round(4 + (index % 4) * 1.5, 1),
            }
        )

    raw_grid_status = {}
    for metric_name, metric in infrared_metrics.items():
        raw_grid_status[metric_name] = {
            "available": bool(metric.get("available")),
            "min": metric.get("min"),
            "mean": metric.get("mean"),
            "max": metric.get("max"),
            "grid_shape": metric.get("grid_shape"),
            "bounds": metric.get("bounds"),
            "has_raw_cells": bool(metric.get("cells") or metric.get("grid") or metric.get("values")),
        }

    return {
        "contextual_grids": {
            "temperature": {"id": "temperature", "grid_size": 0, "cell_size_m": None, "cells": [], "source": "summary_only_no_spatial_raster"},
            "solar": _raw_grid_cells(infrared_metrics.get("solar_radiation", {}), "solar"),
            "wind_stagnation": _raw_grid_cells(infrared_metrics.get("wind_speed", {}), "wind_stagnation"),
            "utci": _raw_grid_cells(infrared_metrics.get("utci", {}), "utci"),
            "direct_sun": _raw_grid_cells(infrared_metrics.get("direct_sun_hours", {}), "direct_sun"),
            "sky_view": _raw_grid_cells(infrared_metrics.get("sky_view_factor", {}), "sky_view"),
            "canopy": {"id": "canopy", "grid_size": 0, "cell_size_m": None, "cells": [], "source": "summary_only_no_spatial_raster"},
        },
        "infrared_analysis": {
            "available": bool(infrared.get("available")),
            "source": infrared.get("source"),
            "heat_exposure_score": infrared.get("heat_exposure_score"),
            "raw_grid_status": raw_grid_status,
            "raw_grid_note": "Current cache stores Infrared min/mean/max, bounds and grid shape. No heat-map raster is drawn unless raw merged-grid cells are cached.",
        },
        "tree_markers": tree_markers,
        "cooling_refuge": {
            "distance_m": round(refuge_distance, 1),
            "x_pct": 86,
            "y_pct": 16,
        },
        "visual_method": "urban_geometry_plus_numerical_analysis_summary",
        "visual_limits": [
            "The 500 m analysis square remains blank unless raw spatial raster cells are available.",
            "Current analysis values are shown as numerical summaries, not fake spatial heat-map pixels.",
            "Infrared City cache currently provides summary statistics and grid metadata. True urban-analysis heat maps require raw merged_grid cells.",
        ],
    }


def _build_risk_map_context_payload(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    risk_map = _read_json_object(INTERMEDIATE_DIR / "risk_map.json")
    metadata = _read_json_object(RISK_MAP_DATASET_DIR / "source_metadata.json")

    site = risk_map.get("site") or risk_map.get("location") or {}
    metrics = risk_map.get("metrics") or {}
    climate = risk_map.get("climate_context") or risk_map.get("climate") or {}
    urban = risk_map.get("urban_context") or risk_map.get("urban") or {}
    vulnerability = risk_map.get("vulnerability_context") or risk_map.get("vulnerability") or {}
    infrared = risk_map.get("infrared_city_context") or risk_map.get("infrared_city") or {}

    resolved_lat = _first_number(lat, site.get("latitude"), site.get("lat"), risk_map.get("latitude"), risk_map.get("lat"), 41.389)
    resolved_lon = _first_number(lon, site.get("longitude"), site.get("lon"), risk_map.get("longitude"), risk_map.get("lon"), 2.159)

    resolved_radius = _first_number(site.get("bbox_radius_m"), risk_map.get("bbox_radius_m"), 250) or 250
    infrared_geometry = _load_or_fetch_infrared_geometry(resolved_lat or 41.389, resolved_lon or 2.159, resolved_radius)
    osm_geometry = _local_osm_visual_geometry(resolved_lat or 41.389, resolved_lon or 2.159, resolved_radius)
    city_contours = osm_geometry.get("city_contours") if osm_geometry.get("available") else _barcelona_city_contours()
    local_building_geometry = infrared_geometry if infrared_geometry.get("available") else osm_geometry.get("estimated_3d_buildings", {})

    return {
        "generated_from": "backend:/api/risk-map/context",
        "backend": {"connected": True, "source": "fastapi"},
        "site": {
            "risk_map_id": risk_map.get("risk_map_id") or site.get("risk_map_id") or "RM_BLD_001",
            "region_id": risk_map.get("region_id") or site.get("region_id") or "BCN_SAMPLE",
            "building_id": risk_map.get("building_id") or site.get("building_id") or "BLDG_001",
            "room_id": risk_map.get("room_id") or site.get("room_id") or "ROOM_001",
            "address": address or site.get("address") or site.get("location_name") or "Barcelona sample site",
            "latitude": resolved_lat,
            "longitude": resolved_lon,
            "bbox_radius_m": resolved_radius,
        },
        "metrics": {
            "peak_dry_bulb_c": _first_number(metrics.get("peak_dry_bulb_c"), climate.get("peak_dry_bulb_c"), 32.2),
            "peak_global_horizontal_radiation_w_m2": _first_number(
                metrics.get("peak_global_horizontal_radiation_w_m2"),
                climate.get("peak_global_horizontal_radiation_w_m2"),
                955,
            ),
            "night_reference_temperature_3am_c": _first_number(
                metrics.get("night_reference_temperature_3am_c"),
                climate.get("night_reference_temperature_3am_c"),
                23.9,
            ),
            "utci_mean_c": _first_number(metrics.get("utci_mean_c"), climate.get("utci_mean_c"), 29),
            "tree_canopy_percent": _first_number(metrics.get("tree_canopy_percent"), urban.get("tree_canopy_percent"), 6.5),
            "cooling_refuge_distance_m": _first_number(
                metrics.get("cooling_refuge_distance_m"),
                urban.get("cooling_refuge_distance_m"),
                610,
            ),
            "hw_ratio": _first_number(metrics.get("hw_ratio"), urban.get("hw_ratio"), 2.31),
            "composite_urban_modifier": _first_number(
                metrics.get("composite_urban_modifier"),
                urban.get("composite_urban_modifier"),
                infrared.get("composite_urban_modifier"),
                1.029,
            ),
            "vulnerability_index": _first_number(
                metrics.get("vulnerability_index"),
                vulnerability.get("vulnerability_index"),
            ),
        },
        "records": {
            "risk_map": risk_map,
            "metadata_file": "risk_map/dataset/source_metadata.json",
        },
        "visual_context": {
            **_build_risk_visual_context(
                {
                    "peak_dry_bulb_c": _first_number(metrics.get("peak_dry_bulb_c"), climate.get("peak_dry_bulb_c"), 32.2),
                    "peak_global_horizontal_radiation_w_m2": _first_number(
                        metrics.get("peak_global_horizontal_radiation_w_m2"),
                        climate.get("peak_global_horizontal_radiation_w_m2"),
                        955,
                    ),
                    "utci_mean_c": _first_number(metrics.get("utci_mean_c"), urban.get("infrared_city_utci_mean_c"), 29),
                    "tree_canopy_percent": _first_number(metrics.get("tree_canopy_percent"), urban.get("tree_canopy_percent"), 6.5),
                    "cooling_refuge_distance_m": _first_number(metrics.get("cooling_refuge_distance_m"), urban.get("cooling_refuge_distance_m"), 610),
                    "hw_ratio": _first_number(metrics.get("hw_ratio"), urban.get("hw_ratio"), 2.31),
                },
                urban,
                climate,
                infrared,
            ),
            "geometry": {
                "city_contours": city_contours,
                "context_contours": osm_geometry.get("context_contours", {}),
                "local_contours": osm_geometry.get("local_contours", {}),
                "local_buildings": local_building_geometry,
                "osm_aligned_buildings": osm_geometry.get("estimated_3d_buildings", {}),
                "infrared_buildings": infrared_geometry,
                "building_geometry_status": "infrared_city_geometry" if infrared_geometry.get("available") else ("local_osm_estimated_heights" if local_building_geometry.get("available") else "unavailable"),
                "visual_alignment_source": "local_osm_shapefile_cataluna_260528",
                "geometry_note": "The visual checkpoint uses local OSM footprints for map and 3D alignment. Infrared City is used for analysis values; its mesh coordinate frame is kept separately.",
            },
        },
        "source_groups": _source_group_payload(metadata),
    }


def _read_pipeline_status() -> dict:
    status_path = INTERMEDIATE_DIR / "pipeline_status.json"
    if status_path.exists():
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _sync_region_orientation(facing_direction: str) -> None:
    region_context = _read_region_context()
    region_context["facing_direction"] = facing_direction
    _write_region_context(region_context)


def _to_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _save_upload_file(upload_file: UploadFile, destination_name: str) -> str:
    filename = f"{destination_name}_{Path(upload_file.filename).name}"
    destination = IMAGES_DIR / filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return filename


def _infer_uploaded_image_names() -> List[str]:
    return [path.name for path in IMAGES_DIR.rglob("*") if path.is_file()]


def _assess_inputs(
    user_case: dict,
    building_info: dict,
    region_context: dict,
    image_names: List[str],
) -> tuple[bool, List[str], str]:
    missing_inputs: List[str] = []
    plain_names = {
        "building_location": "building location",
        "user_text": "room note",
        "room_type": "room type",
        "room_area_m2": "room area",
        "room_height_m": "ceiling height",
        "pano_image": "room image",
        "occupant_profile": "resident profile",
    }

    if not user_case.get("latest_user_message") and not user_case.get("user_intention"):
        missing_inputs.append("user_text")

    if not region_context.get("coordinates") and not region_context.get("address"):
        missing_inputs.append("building_location")

    if not building_info.get("room_type"):
        missing_inputs.append("room_type")
    if not building_info.get("room_area_m2"):
        missing_inputs.append("room_area_m2")
    if not building_info.get("room_height_m"):
        missing_inputs.append("room_height_m")

    if not any("pano" in name.lower() or "panorama" in name.lower() for name in image_names):
        missing_inputs.append("pano_image")


    if not user_case.get("occupant_profile"):
        missing_inputs.append("occupant_profile")

    if missing_inputs:
        missing_labels = [plain_names.get(item, item.replace("_", " ")) for item in missing_inputs]
        message = (
            "I still need a few inputs to move forward. "
            f"Missing: {', '.join(missing_labels)}. "
            "Please type the missing room/location details in the chat and add the room image if it is still missing."
        )
        return False, missing_inputs, message

    return True, [], "Your input set is complete. Running the diagnostic pipeline and refreshing the visual views now."


def _run_main_pipeline() -> None:
    subprocess.run(
        [sys.executable, str(ROOT_DIR / "main.py")],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


def _refresh_component_view_from_overrides() -> None:
    from spatial_engine.component_composition import write_component_composition
    from spatial_engine.full_texture_component_refresher import refresh_full_texture_component_check
    from spatial_engine.host_geometry import build_host_geometry
    from spatial_engine.overrides import apply_spatial_overrides, load_spatial_overrides
    from spatial_engine.room_component_viewer import export_room_component_view
    from spatial_engine.textured_component_viewer import export_textured_component_view
    from utils.file_io import write_json

    base_spatial_index = _json_read(INTERMEDIATE_DIR / "spatial_index.json")
    if not base_spatial_index:
        return
    spatial_index = apply_spatial_overrides(base_spatial_index, load_spatial_overrides())
    _json_write(INTERMEDIATE_DIR / "spatial_index_with_overrides.json", spatial_index)

    spatial_output_dir = OUTPUT_DIR / "spatial"
    write_json(spatial_output_dir / "host_geometry.json", build_host_geometry(spatial_index))
    export_room_component_view(spatial_index, spatial_output_dir / "room_3d_component_view.html")
    if (INTERMEDIATE_DIR / "retrofit_validation_options.json").exists():
        write_component_composition(spatial_output_dir / "component_composition.json")
    export_textured_component_view(spatial_output_dir / "room_3d_textured_component_test.html")
    refresh_full_texture_component_check(spatial_index)

FAST_PHASE3_REQUIRED = [
    "interpreted_case.json",
    "diagnosis_result.json",
    "problem_map.json",
    "strategy_options.json",
    "retrofit_validation_options.json",
]


def _json_read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _can_fast_phase3_continue() -> bool:
    return all((INTERMEDIATE_DIR / name).exists() for name in FAST_PHASE3_REQUIRED)


def _run_fast_phase3_refresh() -> None:
    from checkpoint_engine import create_strategy_validation_checkpoint
    from diagnosis_engine.environmental_diagnosis import compute_diagnosis
    from diagnosis_engine.problem_map_builder import build_problem_map
    from llm_agent.agent import rank_retrofit_options
    from rag_engine.manual_checker import check_manuals
    from report_engine.html_exporter import export_html
    from report_engine.markdown_exporter import export_markdown
    from report_engine.report_compiler import compile_report
    from scripts.build_phase3_strategy_packages import build_packages
    from spatial_engine.component_composition import write_component_composition
    from spatial_engine.overrides import apply_spatial_overrides, load_spatial_overrides
    from spatial_engine.room_component_viewer import export_room_component_view
    from spatial_engine.wall_diagnosis_state import export_wall_diagnosis_state
    from utils.config import load_settings
    from validation_engine import validate_retrofit, validate_retrofit_options
    from validation_engine.html_exporter import export_validation_html
    from validation_engine.strategy_scenario_generator import generate_retrofit_generation_scenarios

    settings = load_settings()
    user_case = _read_user_case()
    building_info = _read_building_info()
    interpreted_case = _json_read(INTERMEDIATE_DIR / "interpreted_case.json")
    constraints = _json_read(INPUT_DIR / "retrofit_constraints.json")
    risk_map = _json_read(INTERMEDIATE_DIR / "risk_map.json")

    base_spatial_index = _json_read(INTERMEDIATE_DIR / "spatial_index.json")
    spatial_index = apply_spatial_overrides(base_spatial_index, load_spatial_overrides())
    _json_write(INTERMEDIATE_DIR / "spatial_index_with_overrides.json", spatial_index)
    export_room_component_view(spatial_index, OUTPUT_DIR / "spatial" / "room_3d_component_view.html")

    diagnosis_result = compute_diagnosis(
        interpreted_case,
        building_info,
        spatial_index,
        user_case,
        urban_context=risk_map,
    )
    _json_write(INTERMEDIATE_DIR / "diagnosis_result.json", diagnosis_result)

    problem_map = build_problem_map(diagnosis_result, spatial_index)
    _json_write(INTERMEDIATE_DIR / "problem_map.json", problem_map)
    export_wall_diagnosis_state(problem_map, spatial_index)

    manual_check = _json_read(INTERMEDIATE_DIR / "manual_check_result.json")
    strategy_options = _json_read(INTERMEDIATE_DIR / "strategy_options.json")

    retrofit_validation_options = validate_retrofit_options(diagnosis_result, problem_map, strategy_options, spatial_index)
    _json_write(INTERMEDIATE_DIR / "retrofit_validation_options.json", retrofit_validation_options)
    write_component_composition(OUTPUT_DIR / "spatial" / "component_composition.json")

    retrofit_generation_scenarios = generate_retrofit_generation_scenarios(diagnosis_result, strategy_options, limit=9)
    _json_write(INTERMEDIATE_DIR / "retrofit_generation_scenarios.json", retrofit_generation_scenarios)

    phase3_strategy_packages = build_packages()
    _json_write(INTERMEDIATE_DIR / "phase3_strategy_packages.json", phase3_strategy_packages)

    validation_view_payload = dict(phase3_strategy_packages)
    validation_view_payload["baseline"] = retrofit_validation_options.get("baseline", {})
    (OUTPUT_DIR / "validation_view.html").write_text(export_validation_html(validation_view_payload), encoding="utf-8")

    packages = phase3_strategy_packages.get("packages", [])
    recommended_strategy = dict((retrofit_validation_options.get("validated_options") or [{}])[0].get("strategy", {}))
    target_wall_id = next(
        (
            target.get("wall_id")
            for problem in problem_map.get("problems", [])
            for target in problem.get("spatial_targets", [])
            if target.get("wall_id")
        ),
        None,
    )
    if target_wall_id:
        target_problem = (problem_map.get("problems") or [{}])[0].get("id", "current diagnosis")
        recommended_strategy["target_wall_id"] = target_wall_id
        recommended_strategy["rationale"] = f"Responds to {target_problem} on wall {target_wall_id}."
    user_selection = {
        "id": f"{interpreted_case.get('case_id', 'CASE_001')}_SELECTION_001",
        "case_id": interpreted_case.get("case_id", "CASE_001"),
        "selected_strategy": recommended_strategy,
        "responds_to_problem_ids": [problem.get("id") for problem in problem_map.get("problems", []) if problem.get("id")],
        "selection_mode": "web_fast_phase3_refresh",
        "recommended_package_id": packages[0].get("package_id") if packages else None,
    }
    _json_write(INTERMEDIATE_DIR / "user_selection.json", user_selection)

    retrofit_validation = validate_retrofit(diagnosis_result, problem_map, user_selection, spatial_index)
    _json_write(INTERMEDIATE_DIR / "retrofit_validation.json", retrofit_validation)

    strategy_validation_stage_result = {
        **retrofit_validation_options,
        "phase3_strategy_packages": phase3_strategy_packages,
        "packages": packages,
        "recommended_package_id": packages[0].get("package_id") if packages else None,
    }
    report_payload = {
        "interpreted_case": interpreted_case,
        "spatial_index": spatial_index,
        "risk_map": risk_map,
        "diagnosis_result": diagnosis_result,
        "problem_map": problem_map,
        "manual_check": manual_check,
        "strategy_options": strategy_options,
        "retrofit_validation_options": retrofit_validation_options,
        "retrofit_generation_scenarios": retrofit_generation_scenarios,
        "phase3_strategy_packages": phase3_strategy_packages,
        "strategy_validation_checkpoint": create_strategy_validation_checkpoint(strategy_validation_stage_result),
        "user_selection": user_selection,
        "retrofit_validation": retrofit_validation,
        "gemini_prompt": _json_read(INTERMEDIATE_DIR / "gemini_prompt.json"),
        "gemini_result": _json_read(INTERMEDIATE_DIR / "gemini_result.json") or {"status": "skipped", "reason": "web_fast_phase3_refresh"},
        "llm_review": _json_read(INTERMEDIATE_DIR / "llm_review.json") or {"status": "skipped", "reason": "web_fast_phase3_refresh"},
    }
    final_report = compile_report(report_payload)
    _json_write(OUTPUT_DIR / "final_report.json", final_report)
    (OUTPUT_DIR / "final_report.md").write_text(export_markdown(final_report), encoding="utf-8")
    (OUTPUT_DIR / "final_report_view.html").write_text(export_html(final_report), encoding="utf-8")
    _json_write(INTERMEDIATE_DIR / "pipeline_status.json", {
        "status": "complete",
        "current_stage": "complete",
        "message": "Diagnosis and Phase 3 refreshed using fast web-test mode.",
        "primary_output": "data/output/final_report_view.html",
    })

@app.post("/api/chat")
async def chat_endpoint(
    text: str | None = Form(None),
    client_stage: str | None = Form(None),
    room_type: str | None = Form(None),
    facing_direction: str | None = Form(None),
    room_area_m2: str | None = Form(None),
    room_height_m: str | None = Form(None),
    pano_image: UploadFile | None = File(None),
    perspective_image: UploadFile | None = File(None),
) -> JSONResponse:
    user_case = _read_user_case()
    building_info = _read_building_info()
    region_context = _read_region_context()
    if text:
        clean_text = text.strip()
        user_case["latest_user_message"] = clean_text
        coordinates = _extract_coordinates(clean_text)
        if coordinates:
            region_context["coordinates"] = coordinates
            region_context.setdefault("region_id", "REGION_001")
            region_context["location_source"] = "chat_message"
            _write_region_context(region_context)
        else:
            location_text = _extract_location_text(clean_text)
            if location_text:
                region_context["address"] = location_text
                region_context.setdefault("region_id", "REGION_001")
                region_context["location_source"] = "chat_message"
                _write_region_context(region_context)
        extracted_details = _extract_room_details(clean_text)
        if extracted_details:
            building_info.update(extracted_details)
            _write_building_info(building_info)
        _write_user_case(user_case)

    if room_type and len(room_type.strip()) >= 3:
        building_info["room_type"] = room_type.strip().lower()
    if facing_direction:
        building_info["facing_direction"] = facing_direction.strip().upper()
        _sync_region_orientation(building_info["facing_direction"])
    area_value = _to_float(room_area_m2)
    if area_value is not None:
        building_info["room_area_m2"] = area_value
    height_value = _to_float(room_height_m)
    if height_value is not None:
        building_info["room_height_m"] = height_value
    if any([room_type and len(room_type.strip()) >= 3, facing_direction, area_value is not None, height_value is not None]):
        _write_building_info(building_info)

    uploaded_names: List[str] = []
    if pano_image is not None:
        uploaded_names.append(_save_upload_file(pano_image, "pano_image"))
    if perspective_image is not None:
        uploaded_names.append(_save_upload_file(perspective_image, "perspective_image"))

    uploaded_names.extend(_infer_uploaded_image_names())
    region_context = _read_region_context()
    is_satisfied, missing_inputs, chat_message = _assess_inputs(user_case, building_info, region_context, uploaded_names)

    if is_satisfied:
        # The web test flow starts from Phase 1 each session. Remove stale spatial V&V
        # decisions so the pipeline stops at the Phase 2 room-check checkpoint.
        stale_spatial_overrides = INTERMEDIATE_DIR / "spatial_user_overrides.json"
        if (client_stage in (None, "input_gathering")) and stale_spatial_overrides.exists():
            stale_spatial_overrides.unlink()
        try:
            _run_main_pipeline()
        except subprocess.CalledProcessError as error:
            raise HTTPException(status_code=500, detail=error.stderr or str(error))

        pipeline_status = _read_pipeline_status()
        if pipeline_status.get("status") == "waiting_for_user":
            return JSONResponse(
                {
                    "current_stage": pipeline_status.get("current_stage", "spatial_vv"),
                    "is_satisfied": False,
                    "missing_inputs": [],
                    "chat_message": pipeline_status.get(
                        "message",
                        "Room geometry is ready. Please complete the spatial check before diagnosis continues.",
                    ),
                    "refresh_views": True,
                }
            )

        return JSONResponse(
            {
                "current_stage": pipeline_status.get("current_stage", "processing"),
                "is_satisfied": True,
                "missing_inputs": [],
                "chat_message": pipeline_status.get("message", chat_message),
                "refresh_views": True,
            }
        )

    return JSONResponse(
        {
            "current_stage": "input_gathering",
            "is_satisfied": False,
            "missing_inputs": missing_inputs,
            "chat_message": chat_message,
            "refresh_views": False,
        }
    )


@app.post("/api/checkpoint/action")
async def checkpoint_action(action: CheckpointAction) -> JSONResponse:
    command = [sys.executable, str(ROOT_DIR / "continue_from_checkpoint.py"), "--checkpoint", action.checkpoint]
    if action.llm:
        command.append("--llm")
    if action.apply:
        command.append("--apply")
    if action.mock_llm:
        command.append("--mock-llm")
    if action.mock_gemini:
        command.append("--mock-gemini")
    if action.mock_neo4j:
        command.append("--mock-neo4j")

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise HTTPException(status_code=500, detail=error.stderr or error.stdout or str(error))

    return JSONResponse(
        {
            "status": "ok",
            "checkpoint": action.checkpoint,
            "message": completed.stdout.strip() or f"Checkpoint {action.checkpoint} continued successfully.",
            "refresh_views": True,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=int(os.getenv("HVRA_API_PORT", "8010")), reload=False)









