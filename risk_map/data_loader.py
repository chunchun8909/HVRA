"""
Risk Map Data Loader
Extracts and prepares OSM, climate, tree, and building data from dataset folder.
"""

from __future__ import annotations
import json
import zipfile
from pathlib import Path
from typing import Optional

from .infrared_city_provider import load_infrared_city_context


def load_epw_metadata(epw_zip_path: str) -> dict:
    """Extract EPW file metadata (location, design conditions)."""
    try:
        with zipfile.ZipFile(epw_zip_path) as z:
            epw_file = [n for n in z.namelist() if n.endswith('.epw')][0]
            with z.open(epw_file) as f:
                lines = f.readlines()
                # Parse first line: LOCATION
                loc_line = lines[0].decode('utf-8').strip().split(',')
                return {
                    "source": "EPW",
                    "city": loc_line[1] if len(loc_line) > 1 else "unknown",
                    "region": loc_line[2] if len(loc_line) > 2 else "unknown",
                    "country": loc_line[3] if len(loc_line) > 3 else "unknown",
                    "latitude": float(loc_line[6]) if len(loc_line) > 6 else None,
                    "longitude": float(loc_line[7]) if len(loc_line) > 7 else None,
                    "available": True,
                }
    except Exception as e:
        return {"source": "EPW", "available": False, "error": str(e)}


def _read_epw_lines(epw_path: Path) -> tuple[str, list[str]]:
    if epw_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(epw_path) as archive:
            epw_file = [name for name in archive.namelist() if name.lower().endswith(".epw")][0]
            return epw_file, archive.read(epw_file).decode("utf-8", errors="replace").splitlines()
    return epw_path.name, epw_path.read_text(encoding="utf-8", errors="replace").splitlines()


def load_epw_metadata_any(epw_path: str) -> dict:
    try:
        epw_file, lines = _read_epw_lines(Path(epw_path))
        loc_line = lines[0].strip().split(",")
        return {
            "source": "EPW",
            "epw_file": epw_file,
            "city": loc_line[1] if len(loc_line) > 1 else "unknown",
            "region": loc_line[2] if len(loc_line) > 2 else "unknown",
            "country": loc_line[3] if len(loc_line) > 3 else "unknown",
            "latitude": float(loc_line[6]) if len(loc_line) > 6 else None,
            "longitude": float(loc_line[7]) if len(loc_line) > 7 else None,
            "available": True,
        }
    except Exception as e:
        return {"source": "EPW", "available": False, "error": str(e)}


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_epw_climate_summary(epw_zip_path: str, hot_months: tuple[int, ...] = (6, 7, 8, 9)) -> dict:
    """
    Extract real hourly climate metrics from an EPW file.

    EPW weather rows start after 8 header lines. The fields used here are
    dry bulb temperature, relative humidity, global horizontal radiation,
    direct normal radiation, diffuse horizontal radiation, wind direction,
    and wind speed.
    """
    try:
        epw_file, lines = _read_epw_lines(Path(epw_zip_path))
        rows = lines[8:]

        hourly = []
        for line in rows:
            parts = line.split(",")
            if len(parts) < 22:
                continue
            month = int(_safe_float(parts[1], 0))
            if month not in hot_months:
                continue
            hour = int(_safe_float(parts[3], 1))
            dry_bulb = _safe_float(parts[6])
            relative_humidity = _safe_float(parts[8])
            global_horizontal_radiation = max(0.0, _safe_float(parts[13]))
            direct_normal_radiation = max(0.0, _safe_float(parts[14]))
            diffuse_horizontal_radiation = max(0.0, _safe_float(parts[15]))
            wind_direction = _safe_float(parts[20])
            wind_speed = max(0.0, _safe_float(parts[21]))
            hourly.append(
                {
                    "month": month,
                    "day": int(_safe_float(parts[2], 1)),
                    "hour": hour,
                    "dry_bulb_c": dry_bulb,
                    "relative_humidity_pct": relative_humidity,
                    "global_horizontal_radiation_w_m2": global_horizontal_radiation,
                    "direct_normal_radiation_w_m2": direct_normal_radiation,
                    "diffuse_horizontal_radiation_w_m2": diffuse_horizontal_radiation,
                    "wind_direction_deg": wind_direction,
                    "wind_speed_m_s": wind_speed,
                }
            )

        if not hourly:
            return {"source": "EPW", "available": False, "error": "No hot-season hourly EPW records parsed."}

        peak_temp = max(hourly, key=lambda row: row["dry_bulb_c"])
        peak_solar = max(hourly, key=lambda row: row["global_horizontal_radiation_w_m2"])
        night_rows = [row for row in hourly if row["hour"] in {2, 3, 4, 24}]
        night_reference = max(night_rows or hourly, key=lambda row: row["dry_bulb_c"])

        def mean(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        return {
            "source": "EPW",
            "available": True,
            "epw_file": epw_file,
            "hot_months": list(hot_months),
            "hour_count": len(hourly),
            "peak_dry_bulb_c": round(peak_temp["dry_bulb_c"], 2),
            "peak_temperature_record": peak_temp,
            "peak_global_horizontal_radiation_w_m2": round(
                peak_solar["global_horizontal_radiation_w_m2"], 2
            ),
            "peak_solar_record": peak_solar,
            "mean_hot_season_dry_bulb_c": round(mean([row["dry_bulb_c"] for row in hourly]), 2),
            "mean_hot_season_relative_humidity_pct": round(
                mean([row["relative_humidity_pct"] for row in hourly]), 2
            ),
            "mean_hot_season_wind_speed_m_s": round(mean([row["wind_speed_m_s"] for row in hourly]), 2),
            "night_reference_temperature_3am_c": round(night_reference["dry_bulb_c"], 2),
            "night_reference_record": night_reference,
            "hourly_hot_season_temperatures_c": [round(row["dry_bulb_c"], 2) for row in hourly],
        }
    except Exception as e:
        return {"source": "EPW", "available": False, "error": str(e)}


def find_best_epw(data_root: Path) -> Path | None:
    direct_files = sorted(data_root.glob("*.epw"))
    if direct_files:
        return direct_files[0]
    zipped = sorted(path for path in data_root.glob("*.zip") if "epw" in path.name.lower() or "tmy" in path.name.lower())
    if zipped:
        return zipped[0]
    return None


def inventory_risk_map_sources(data_root: Path) -> dict:
    files = {path.name: path for path in data_root.glob("*") if path.is_file()}
    return {
        "epw_weather": [name for name in files if name.lower().endswith(".epw") or "tmy" in name.lower()],
        "meteocat": [name for name in files if "meteocat" in name.lower()],
        "neighbourhood_boundaries": [name for name in files if "unitats_adm" in name.lower() or "adminareas" in name.lower()],
        "uhi_or_thermal_reference": [name for name in files if "ijerph" in name.lower() or "confort" in name.lower()],
        "tree_inventory": [name for name in files if "arbrat" in name.lower() or "tree" in name.lower()],
        "vegetation_cover": [name for name in files if "vegetacio" in name.lower() or "vegetation" in name.lower()],
        "osm_buildings": [name for name in files if "osm" in name.lower() or "cataluna" in name.lower()],
        "building_heights": [name for name in files if "alçades" in name.lower() or "alcades" in name.lower()],
        "heat_exposed_population": [name for name in files if "densitat" in name.lower() or "density" in name.lower()],
        "heat_exposed_facilities": [name for name in files if "ate_equip" in name.lower()],
        "vulnerability": [name for name in files if "vulnera" in name.lower() or "75plus" in name.lower()],
        "cooling_refuges": [name for name in files if "refugi" in name.lower() or "espaisrefugi" in name.lower()],
        "thermal_comfort": [name for name in files if "confort" in name.lower()],
        "infrared_city": [
            str(path.relative_to(data_root))
            for path in sorted((data_root / "infrared_city").glob("*.json"))
            if path.is_file()
        ] if (data_root / "infrared_city").exists() else [],
    }


def load_tree_inventory(csv_path: str, bbox_coords: tuple[float, float, float, float]) -> dict:
    """
    Load tree inventory CSV.
    bbox_coords: (min_lat, max_lat, min_lon, max_lon)
    Returns tree counts and canopy estimate.
    """
    try:
        import csv
        min_lat, max_lat, min_lon, max_lon = bbox_coords
        trees_in_bbox = 0
        
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse geometry: "POINT (lon lat)"
                    geom = row.get('geom_wgs84', '')
                    if 'POINT' in geom:
                        coords = geom.replace('POINT (', '').replace(')', '').split()
                        lon, lat = float(coords[0]), float(coords[1])
                        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                            trees_in_bbox += 1
                except (ValueError, IndexError):
                    pass
        
        # Rough canopy estimate: assume avg tree canopy ~15 m² per tree
        tree_canopy_area_m2 = trees_in_bbox * 15
        return {
            "source": "Barcelona Tree Inventory",
            "trees_in_bbox": trees_in_bbox,
            "estimated_canopy_area_m2": tree_canopy_area_m2,
            "available": True,
        }
    except Exception as e:
        return {"source": "Tree Inventory", "available": False, "error": str(e)}


def load_osm_buildings_summary(shp_zip_path: str, bbox_coords: tuple[float, float, float, float]) -> dict:
    """
    Summarize OSM buildings shapefile (building count, area, avg height).
    bbox_coords: (min_lat, max_lat, min_lon, max_lon)
    """
    try:
        import zipfile
        # For MVP: just report that data exists
        with zipfile.ZipFile(shp_zip_path) as z:
            shp_files = [n for n in z.namelist() if 'buildings' in n and n.endswith('.shp')]
            if shp_files:
                return {
                    "source": "OpenStreetMap Buildings",
                    "available": True,
                    "shapefile_found": True,
                    "note": "Full building processing requires geopandas; mock summary for MVP",
                    "estimated_building_count": 500,  # placeholder
                    "estimated_avg_height_m": 18,  # placeholder based on Barcelona urban context
                }
    except Exception as e:
        return {"source": "OSM Buildings", "available": False, "error": str(e)}


def generate_urban_context(
    building_location: tuple[float, float],
    bbox_radius_m: float = 250,
) -> dict:
    """
    Generate urban context for a building location.
    For MVP: use synthetic/mock values based on Barcelona typical urban context.
    
    Args:
        building_location: (latitude, longitude)
        bbox_radius_m: bounding box radius in meters
        
    Returns:
        dict with urban context metrics
    """
    # Convert bbox_radius_m to approximate lat/lon (rough approximation)
    # At Barcelona latitude (~41°): 1° ≈ 111 km
    # bbox_radius_m / 111000 ≈ lat/lon delta
    delta = bbox_radius_m / 111000
    lat, lon = building_location
    bbox = (lat - delta, lat + delta, lon - delta, lon + delta)
    
    # For MVP, return synthetic urban context based on Barcelona typical values
    # These can be replaced with real OSM/climate data processing later
    return {
        "location": {"latitude": lat, "longitude": lon},
        "bbox_radius_m": bbox_radius_m,
        "bbox": bbox,
        "urban_metrics": {
            "building_density": 0.68,  # typical Barcelona Eixample
            "avg_building_height_m": 18.5,
            "street_width_m": 8.0,
            "hw_ratio": 2.31,  # H/W ratio (height/width)
            "sky_view_factor": 0.38,
            "tree_canopy_percent": 6.5,
            "green_space_distance_m": 420,
            "cooling_refuge_distance_m": 610,
        },
        "uhi_modifier": 1.15,  # synthetic: moderate UHI
        "infrared_city_heat_score": 0.82,  # synthetic: moderate heat exposure
        "urban_context_modifier": 1.22,  # composite urban heat amplification
        "source": "synthetic_mvp",
    }


def prepare_risk_map_input(
    building_info: dict,
    region_context: dict,
    bbox_radius_m: float = 250,
    data_root: Optional[str] = None,
    infrared_city_context: Optional[dict] = None,
) -> dict:
    """
    Prepare risk map input from region_context (location + orientation) and available dataset.
    
    Args:
        building_info: room-specific info (room_id, room_area, floor, etc.)
        region_context: location and orientation from region_context.json
        bbox_radius_m: bounding box radius in meters
        data_root: path to risk_map/dataset
    """
    if data_root is None:
        data_root = str(Path(__file__).parent / "dataset")
    
    data_root = Path(data_root)
    
    # Extract location and orientation from region_context
    if "coordinates" in region_context:
        lat = region_context["coordinates"].get("lat", 41.3851)
        lon = region_context["coordinates"].get("lon", 2.1734)
    else:
        lat, lon = 41.3851, 2.1734  # mock Barcelona default
    
    facing_direction = region_context.get("facing_direction", building_info.get("facing_direction", "SW"))
    
    # Generate urban context
    urban_context = generate_urban_context((lat, lon), bbox_radius_m)
    if infrared_city_context and infrared_city_context.get("available"):
        updates = {
            key: value
            for key, value in infrared_city_context.get("urban_context_updates", {}).items()
            if value is not None
        }
        urban_context["urban_metrics"].update(updates)
        heat_score = infrared_city_context.get("heat_exposure_score")
        if heat_score is not None:
            urban_context["infrared_city_heat_score"] = heat_score
            urban_context["urban_context_modifier"] = round(1.0 + heat_score * 0.32, 3)
    
    # Load data summaries
    epw_meta = {}
    epw_climate = {}
    tree_data = {}
    osm_data = {}
    
    epw_file = find_best_epw(data_root)
    if epw_file:
        epw_meta = load_epw_metadata_any(str(epw_file))
        epw_climate = load_epw_climate_summary(str(epw_file))
    
    tree_csv = data_root / "ab_vw_arbrat_geometries.csv"
    if tree_csv.exists():
        tree_data = load_tree_inventory(str(tree_csv), urban_context["bbox"])
    
    osm_zip = data_root / "cataluna-260528-free.shp.zip"
    if osm_zip.exists():
        osm_data = load_osm_buildings_summary(str(osm_zip), urban_context["bbox"])
    
    return {
        "building_id": building_info.get("building_id", "BLD_UNKNOWN"),
        "building_location": {"latitude": lat, "longitude": lon},
        "room_id": building_info.get("room_id", "ROOM_UNKNOWN"),
        "facing_direction": facing_direction,
        "is_top_floor": building_info.get("is_top_floor", False),
        "urban_context": urban_context,
        "data_availability": {
            "epw_climate": epw_meta,
            "epw_hourly_summary": epw_climate,
            "trees": tree_data,
            "osm_buildings": osm_data,
            "infrared_city": infrared_city_context or {
                "available": False,
                "source": "infrared_city",
                "reason": "USE_INFRARED_CITY is disabled or no cache export is available.",
            },
            "dataset_inventory": inventory_risk_map_sources(data_root),
        },
        "bbox_radius_m": bbox_radius_m,
        "region_id": region_context.get("region_id", "REGION_UNKNOWN"),
    }


if __name__ == "__main__":
    # Test
    mock_building = {
        "building_id": "BLD_001",
        "room_id": "ROOM_001",
        "is_top_floor": True,
    }
    mock_region = {
        "region_id": "REGION_001",
        "coordinates": {"lat": 41.389, "lon": 2.159},
        "facing_direction": "SW",
    }
    result = prepare_risk_map_input(mock_building, mock_region)
    print(json.dumps(result, indent=2))
