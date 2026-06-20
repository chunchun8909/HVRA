from __future__ import annotations

from .scaling_engine import distance_xz, polygon_area_xz


ORIENTATIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _wall_orientation(index: int, facing_direction: str) -> str:
    if facing_direction in ORIENTATIONS:
        start = ORIENTATIONS.index(facing_direction)
        return ORIENTATIONS[(start + index) % len(ORIENTATIONS)]
    return ORIENTATIONS[index % len(ORIENTATIONS)]


def _to_viewer_xyz(xyz: list[float]) -> list[float]:
    return [float(xyz[0]), float(xyz[1]), -float(xyz[2])]


def _to_viewer_normal(normal: list[float]) -> list[float]:
    if len(normal) < 3:
        return normal
    return [float(normal[0]), float(normal[1]), -float(normal[2])]


def _to_viewer_plane(plane: list[float]) -> list[float]:
    if len(plane) < 4:
        return plane
    return [float(plane[0]), float(plane[1]), -float(plane[2]), float(plane[3])]


def decompose_room(layout: dict, building_info: dict) -> dict:
    room_id = building_info.get("room_id", "ROOM_UNKNOWN")
    building_id = building_info.get("building_id", "BLD_UNKNOWN")
    height = float(layout.get("layoutHeight") or building_info.get("room_height_m") or 2.7)
    raw_points = layout["layoutPoints"]["points"]
    points = [{"id": point["id"], "xyz": _to_viewer_xyz(point["xyz"])} for point in raw_points]
    point_by_id = {point["id"]: point for point in points}
    facing = building_info.get("facing_direction", "SW")

    walls = []
    for index, wall in enumerate(layout["layoutWalls"]["walls"]):
        start_id, end_id = wall["pointsIdx"]
        start = point_by_id[start_id]["xyz"]
        end = point_by_id[end_id]["xyz"]
        length = distance_xz(start, end)
        wall_id = f"{room_id}_WALL_{index:02d}"
        walls.append(
            {
                "id": wall_id,
                "room_id": room_id,
                "source_points": [start_id, end_id],
                "start_xyz": start,
                "end_xyz": end,
                "height_m": round(height, 3),
                "length_m": round(length, 3),
                "estimated_area_m2": round(length * height, 3),
                "orientation": _wall_orientation(index, facing),
                "is_external": index == 0,
                "normal": _to_viewer_normal(wall.get("normal", [])),
                "plane_equation": _to_viewer_plane(wall.get("planeEquation", [])),
            }
        )

    floor_area = polygon_area_xz(points)
    return {
        "building": {"id": building_id, "source": "building_info.json"},
        "room": {
            "id": room_id,
            "room_type": building_info.get("room_type", "room"),
            "floor": building_info.get("floor"),
            "is_top_floor": building_info.get("is_top_floor", False),
            "area_m2": round(floor_area, 3),
            "height_m": round(height, 3),
            "facing_direction": facing,
        },
        "layout_points": points,
        "coordinate_transform": {
            "source": "lgtnet_json",
            "viewer_xyz": "[x, y, -z]",
            "reason": "match LGTNet panorama unwrapping convention used for wall/floor/ceiling textures",
        },
        "floor": {
            "id": f"{room_id}_FLOOR",
            "room_id": room_id,
            "surface_type": "floor",
            "estimated_area_m2": round(floor_area, 3),
            "polygon_xz": [[point["xyz"][0], point["xyz"][2]] for point in points],
        },
        "ceiling": {
            "id": f"{room_id}_CEILING",
            "room_id": room_id,
            "surface_type": "ceiling",
            "estimated_area_m2": round(floor_area, 3),
            "height_m": round(height, 3),
        },
        "walls": walls,
    }
