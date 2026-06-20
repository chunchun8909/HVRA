from __future__ import annotations

import math


def _round_point(point: list[float]) -> list[float]:
    return [round(float(value), 6) for value in point]


def estimate_wall_area(room_area_m2: float, room_height_m: float) -> float:
    return round((room_area_m2 ** 0.5) * room_height_m, 2)


def polygon_area_xz(points: list[dict]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        x1, _y1, z1 = point["xyz"]
        x2, _y2, z2 = next_point["xyz"]
        area += x1 * z2 - x2 * z1
    return abs(area) / 2.0


def distance_xz(a: list[float], b: list[float]) -> float:
    return math.dist([a[0], a[2]], [b[0], b[2]])


def layout_wall_metrics(layout: dict) -> list[dict]:
    points = layout["layoutPoints"]["points"]
    point_by_id = {point["id"]: point for point in points}
    height = float(layout.get("layoutHeight") or 0)
    metrics = []
    for index, wall in enumerate(layout["layoutWalls"]["walls"]):
        start_id, end_id = wall["pointsIdx"]
        start = point_by_id[start_id]["xyz"]
        end = point_by_id[end_id]["xyz"]
        length = distance_xz(start, end)
        metrics.append(
            {
                "index": index,
                "source_points": [start_id, end_id],
                "start_xyz": _round_point(start),
                "end_xyz": _round_point(end),
                "length_m": round(length, 3),
                "height_m": round(height, 3),
                "estimated_area_m2": round(length * height, 3),
            }
        )
    return metrics


def build_scaling_report(raw_layout: dict, scaled_layout: dict, building_info: dict) -> dict:
    raw_points = raw_layout["layoutPoints"]["points"]
    scaled_points = scaled_layout["layoutPoints"]["points"]
    source_area = polygon_area_xz(raw_points)
    scaled_area = polygon_area_xz(scaled_points)
    target_area = float(building_info.get("room_area_m2") or scaled_area or 0)
    target_height = float(building_info.get("room_height_m") or scaled_layout.get("layoutHeight") or 0)
    scale = scaled_layout.get("scale", {})
    area_delta = scaled_area - target_area
    area_error_pct = abs(area_delta / target_area * 100) if target_area else None

    return {
        "mode": "room_area_uniform_scale",
        "scale_source": scale.get("scale_source", "room_area_m2_and_room_height_m"),
        "source_area_m2": round(source_area, 4),
        "target_area_m2": round(target_area, 4),
        "scaled_area_m2": round(scaled_area, 4),
        "area_delta_m2": round(area_delta, 4),
        "area_error_pct": round(area_error_pct, 4) if area_error_pct is not None else None,
        "scale_factor": scale.get("scale_factor"),
        "source_height_m": raw_layout.get("layoutHeight"),
        "target_height_m": round(target_height, 3),
        "scaled_height_m": round(float(scaled_layout.get("layoutHeight") or 0), 3),
        "point_count": len(scaled_points),
        "wall_count": len(scaled_layout.get("layoutWalls", {}).get("walls", [])),
        "raw_wall_metrics": layout_wall_metrics(raw_layout),
        "scaled_wall_metrics": layout_wall_metrics(scaled_layout),
        "validation": {
            "area_matches_target": area_error_pct is not None and area_error_pct <= 1.0,
            "height_matches_target": round(float(scaled_layout.get("layoutHeight") or 0), 3) == round(target_height, 3),
            "notes": [
                "Uniform XZ scaling is derived from target room_area_m2.",
                "Wall and component metric dimensions are downstream estimates, not survey-grade measurements.",
            ],
        },
    }


def scale_layout_to_room(lgtnet_layout: dict, building_info: dict) -> dict:
    points = lgtnet_layout["layoutPoints"]["points"]
    source_area = polygon_area_xz(points)
    target_area = float(building_info.get("room_area_m2") or source_area or 18.0)
    height = float(building_info.get("room_height_m") or lgtnet_layout.get("layoutHeight") or 2.7)
    scale_factor = math.sqrt(target_area / source_area) if source_area > 0 else 1.0

    scaled_points = []
    for point in points:
        x, _y, z = point["xyz"]
        scaled_points.append({"id": point["id"], "xyz": [x * scale_factor, 0.0, z * scale_factor]})

    return {
        **lgtnet_layout,
        "scale": {
            "source_area_m2": round(source_area, 4),
            "target_area_m2": round(target_area, 4),
            "scale_factor": round(scale_factor, 6),
            "height_m": height,
            "scale_source": "room_area_m2_and_room_height_m",
        },
        "layoutHeight": height,
        "layoutPoints": {
            "num": len(scaled_points),
            "points": scaled_points,
        },
    }
