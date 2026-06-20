#!/usr/bin/env python
"""
Risk Map Integration Test
Tests the complete risk_map flow: region_context â†’ urban_context â†’ diagnosis modifier
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from risk_map.risk_map_builder import build_risk_map
from diagnosis_engine.environmental_diagnosis import compute_diagnosis


def get_mock_interpreted_case(building_info: dict, user_case: dict) -> dict:
    """Generate a mock interpreted case for testing."""
    return {
        "case_id": user_case.get("case_id", "CASE_001"),
        "diagnosis_profile": "default",
        "vulnerability_scenario": "elderly_heat_risk",
        "profile_selected": True,
    }


def get_mock_spatial_index(building_info: dict) -> dict:
    """Generate mock spatial index from building_info."""
    room_area = building_info.get("room_area_m2", 18.5)
    room_height = building_info.get("room_height_m", 2.8)
    
    # Assume ~50% walls are exposed (external), rest are interior
    # Estimate wall area: perimeter Ã— height
    perimeter = 2 * (room_area ** 0.5) * 2  # rough square room estimate
    wall_area = perimeter * room_height
    external_facades = building_info.get("external_facades", 1)
    external_wall_area = wall_area * (external_facades / 4)
    
    # Window area estimate
    window_area = building_info.get("window_area_m2")
    if not window_area:
        window_area = external_wall_area * 0.3  # assume 30% glazing
    
    return {
        "room": {
            "id": building_info.get("room_id", "ROOM_001"),
            "type": building_info.get("room_type", "bedroom"),
            "area_m2": room_area,
            "height_m": room_height,
        },
        "walls": [
            {
                "id": "WALL_001",
                "orientation": building_info.get("facing_direction", "SW"),
                "estimated_area_m2": external_wall_area,
                "external": True,
            }
        ],
        "windows": [
            {
                "id": "WIN_001",
                "orientation": building_info.get("facing_direction", "SW"),
                "estimated_area_m2": window_area,
                "type": building_info.get("glazing_type", "single_glazing"),
            }
        ],
    }


def test_risk_map():
    """Test risk_map module end-to-end."""
    
    print("\n" + "="*80)
    print("RISK MAP INTEGRATION TEST")
    print("="*80)
    
    # Load test data
    print("\n[1] Loading test inputs...")
    
    with open("data/input/building_info.json") as f:
        building_info = json.load(f)
    
    with open("data/input/region_context.json") as f:
        region_context = json.load(f)
    
    with open("data/input/user_case.json") as f:
        user_case = json.load(f)
    
    print(f"  âœ“ Building: {building_info['building_id']}")
    print(f"  âœ“ Region: {region_context['neighbourhood']}")
    print(f"  âœ“ Location: {region_context['coordinates']}")
    print(f"  âœ“ Orientation: {region_context.get('facing_direction', 'N/A')}")
    
    # Build risk map
    print("\n[2] Building risk map (location + urban context)...")
    try:
        risk_map = build_risk_map(building_info, region_context)
        print(f"  âœ“ Risk map generated: {risk_map['risk_map_id']}")
        print(f"  âœ“ Urban modifier: {risk_map['composite_urban_modifier']}")
        print(f"  âœ“ UHI effect: {risk_map['urban_heat_island_modifier']}")
        print(f"  âœ“ Data available: {risk_map['data_completeness']}")
    except Exception as e:
        print(f"  âœ— Error building risk map: {e}")
        return False
    
    # Save risk map
    risk_map_path = Path("data/intermediate/risk_map.json")
    risk_map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(risk_map_path, 'w') as f:
        json.dump(risk_map, f, indent=2)
    print(f"  âœ“ Saved to {risk_map_path}")
    
    # Test diagnosis WITHOUT urban context
    print("\n[3] Computing diagnosis WITHOUT urban context...")
    
    interpreted_case = get_mock_interpreted_case(building_info, user_case)
    spatial_index = get_mock_spatial_index(building_info)
    
    try:
        diagnosis_no_context = compute_diagnosis(
            interpreted_case,
            building_info,
            spatial_index,
            user_case,
            urban_context=None,
        )
        room_score = diagnosis_no_context.get('composite_room_risk_score', 0)
        risk_level_no_context = diagnosis_no_context.get('risk_level', 'unknown')
        print(f"  âœ“ Room-only score: {room_score}")
        print(f"  âœ“ Risk level (no context): {risk_level_no_context}")
    except Exception as e:
        print(f"  âœ— Error computing diagnosis: {e}")
        return False
    
    # Test diagnosis WITH urban context
    print("\n[4] Computing diagnosis WITH urban context (from risk_map)...")
    
    try:
        # Pass the full urban context including modifier
        urban_context_for_diagnosis = {
            "uhi_modifier": risk_map.get("urban_heat_island_modifier", 1.0),
            "urban_context_modifier": risk_map.get("composite_urban_modifier", 1.0),
            **risk_map.get("urban_context", {}),  # include urban metrics
        }
        
        diagnosis_with_context = compute_diagnosis(
            interpreted_case,
            building_info,
            spatial_index,
            user_case,
            urban_context=urban_context_for_diagnosis,
        )
        with_context_score = diagnosis_with_context.get('composite_risk_score_with_urban_context', 0)
        urban_mod = diagnosis_with_context.get('urban_modifier', 1.0)
        risk_level_with_context = diagnosis_with_context.get('risk_level', 'unknown')
        
        print(f"  âœ“ Urban modifier applied: {urban_mod}")
        print(f"  âœ“ Final score (with context): {with_context_score}")
        print(f"  âœ“ Risk level (with context): {risk_level_with_context}")
    except Exception as e:
        print(f"  âœ— Error computing diagnosis with context: {e}")
        return False
    
    # Compare
    print("\n[5] Comparison:")
    print(f"  Room-only score: {room_score}")
    print(f"  Urban modifier: {urban_mod}")
    print(f"  Final score: {with_context_score}")
    print(f"  Impact: {room_score} Ã— {urban_mod} = {with_context_score}")
    print(f"  Risk changed: {risk_level_no_context} â†’ {risk_level_with_context}")
    
    # Save diagnosis result
    diagnosis_path = Path("data/intermediate/diagnosis_result_with_context.json")
    with open(diagnosis_path, 'w') as f:
        json.dump(diagnosis_with_context, f, indent=2)
    print(f"\n  âœ“ Saved diagnosis to {diagnosis_path}")
    
    print("\n" + "="*80)
    print("âœ“ RISK MAP INTEGRATION TEST PASSED")
    print("="*80)
    return True


if __name__ == "__main__":
    success = test_risk_map()
    sys.exit(0 if success else 1)

