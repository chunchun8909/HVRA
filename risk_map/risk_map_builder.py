"""
Risk Map Builder
Generates location-specific urban heat risk context for the diagnosis engine.
Links building coordinates and orientation to urban/climate context.
"""

from __future__ import annotations
import json
from pathlib import Path
from .data_loader import prepare_risk_map_input
from .infrared_city_provider import load_infrared_city_context, run_live_infrared_city_context


def build_risk_map(
    building_info: dict,
    region_context: dict,
    bbox_radius_m: float = 250,
    data_root: str | None = None,
    use_infrared_city: bool = False,
    infrared_cache_json: str | None = None,
    infrared_api_key: str = "",
    infrared_base_url: str | None = None,
    infrared_live: bool = True,
    infrared_force_refresh: bool = False,
) -> dict:
    """
    Build risk map output: urban context that will modify diagnosis scores.
    
    Args:
        building_info: room-specific info from building_info.json
        region_context: location & orientation from region_context.json
        bbox_radius_m: radius for urban context extraction
        data_root: path to risk_map/dataset
        
    Returns:
        dict with risk_map results including urban_context_modifier
    """
    
    infrared_context = {"available": False, "source": "infrared_city", "reason": "USE_INFRARED_CITY=false"}
    if use_infrared_city:
        live_refresh_error = None
        if not infrared_force_refresh:
            cached_context = load_infrared_city_context(infrared_cache_json)
            if cached_context.get("available"):
                infrared_context = cached_context
        coordinates = region_context.get("coordinates", {})
        if (
            (infrared_force_refresh or not infrared_context.get("available"))
            and infrared_live
            and coordinates.get("lat") is not None
            and coordinates.get("lon") is not None
        ):
            live_context = run_live_infrared_city_context(
                latitude=float(coordinates["lat"]),
                longitude=float(coordinates["lon"]),
                bbox_radius_m=bbox_radius_m,
                api_key=infrared_api_key,
                base_url=infrared_base_url,
                cache_json=infrared_cache_json,
            )
            if live_context.get("available"):
                infrared_context = live_context
            else:
                live_refresh_error = live_context.get("reason") or "Live Infrared City refresh failed."
        if not infrared_context.get("available"):
            cached_context = load_infrared_city_context(infrared_cache_json)
            if cached_context.get("available"):
                infrared_context = cached_context
        if live_refresh_error and infrared_context.get("available"):
            infrared_context["live_refresh_error"] = live_refresh_error
            infrared_context["cache_fallback_reason"] = "Using cached Infrared summary because live refresh failed."

    # Load and prepare input
    risk_map_input = prepare_risk_map_input(
        building_info,
        region_context,
        bbox_radius_m,
        data_root,
        infrared_city_context=infrared_context,
    )
    
    # Extract relevant metrics for diagnosis modifier
    urban_context = risk_map_input["urban_context"]
    data_availability = risk_map_input["data_availability"]
    
    # Build risk map output
    return {
        "risk_map_id": f"RM_{risk_map_input['building_id']}",
        "region_id": risk_map_input["region_id"],
        "building_id": risk_map_input["building_id"],
        "room_id": risk_map_input["room_id"],
        "location": risk_map_input["building_location"],
        "bbox_radius_m": bbox_radius_m,
        
        # Urban context metrics (for diagnosis engine modifier)
        "urban_context": urban_context["urban_metrics"],
        "urban_heat_island_modifier": urban_context["uhi_modifier"],
        "infrared_city_heat_exposure": urban_context["infrared_city_heat_score"],
        "composite_urban_modifier": urban_context["urban_context_modifier"],
        "climate_context": data_availability.get("epw_hourly_summary", {}),
        "infrared_city_context": infrared_context,
        
        # Data availability summary
        "data_sources": data_availability,
        "data_completeness": {
            "climate_data": data_availability["epw_climate"].get("available", False),
            "hourly_climate_data": data_availability["epw_hourly_summary"].get("available", False),
            "urban_geometry": data_availability["osm_buildings"].get("available", False),
            "vegetation_data": data_availability["trees"].get("available", False),
            "infrared_city_data": data_availability["infrared_city"].get("available", False),
        },
    }


def save_risk_map(risk_map: dict, output_path: str) -> None:
    """Save risk map result to JSON."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(risk_map, f, indent=2)


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
    risk_map = build_risk_map(mock_building, mock_region)
    print(json.dumps(risk_map, indent=2))


