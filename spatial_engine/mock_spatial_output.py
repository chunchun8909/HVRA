from __future__ import annotations


def build_mock_spatial_index(building_info: dict) -> dict:
    room_area = float(building_info.get("room_area_m2", 18.0))
    room_height = float(building_info.get("room_height_m", 2.7))
    facing = building_info.get("facing_direction", "SW")
    wall_area = building_info.get("wall_area_m2") or round((room_area ** 0.5) * room_height, 2)
    window_area = building_info.get("window_area_m2") or round(wall_area * 0.22, 2)

    building_id = building_info.get("building_id", "BLD_UNKNOWN")
    room_id = building_info.get("room_id", "ROOM_UNKNOWN")
    wall_id = f"{room_id}_WALL_EXT_{facing}"
    window_id = f"{room_id}_WINDOW_01"

    return {
        "building": {"id": building_id, "source": "building_info.json"},
        "room": {
            "id": room_id,
            "room_type": building_info.get("room_type", "room"),
            "floor": building_info.get("floor"),
            "is_top_floor": building_info.get("is_top_floor", False),
            "area_m2": room_area,
            "height_m": room_height,
        },
        "walls": [
            {
                "id": wall_id,
                "room_id": room_id,
                "orientation": facing,
                "estimated_area_m2": wall_area,
                "is_external": True,
                "scale_source": "room_area_m2_and_room_height_m",
            }
        ],
        "windows": [
            {
                "id": window_id,
                "wall_id": wall_id,
                "orientation": facing,
                "estimated_area_m2": window_area,
                "glazing_type": building_info.get("glazing_type", "unknown"),
                "has_external_shading": building_info.get("has_external_shading", False),
            }
        ],
        "scale_source": "mock_spatial_output_from_building_info",
    }

