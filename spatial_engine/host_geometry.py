from __future__ import annotations

from pathlib import Path
from typing import Any


def _image_size(path_value: str | None) -> tuple[int | None, int | None]:
    if not path_value:
        return None, None
    path = Path(path_value)
    if not path.exists():
        return None, None
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _opening_uv(component: dict[str, Any]) -> dict[str, float]:
    width, height = _image_size(component.get("wall_fragment_image"))
    bbox = component.get("bbox_px")
    if width and height and isinstance(bbox, list) and len(bbox) >= 4:
        u0 = _clamp(float(bbox[0]) / width, 0.03, 0.97)
        u1 = _clamp(float(bbox[2]) / width, 0.03, 0.97)
        v0 = _clamp(float(bbox[1]) / height, 0.03, 0.97)
        v1 = _clamp(float(bbox[3]) / height, 0.03, 0.97)
        if u1 < u0:
            u0, u1 = u1, u0
        if v1 < v0:
            v0, v1 = v1, v0
        return {"u0": u0, "u1": u1, "v0": v0, "v1": v1}
    return {"u0": 0.32, "u1": 0.68, "v0": 0.18, "v1": 0.86}


def _zone(left: float, right: float, top: float, bottom: float) -> dict[str, float]:
    return {
        "u0": round(_clamp(left), 4),
        "u1": round(_clamp(right), 4),
        "v0": round(_clamp(top), 4),
        "v1": round(_clamp(bottom), 4),
    }


def _opening_zones(uv: dict[str, float]) -> dict[str, dict[str, float]]:
    width = max(0.08, uv["u1"] - uv["u0"])
    height = max(0.12, uv["v1"] - uv["v0"])
    gap = max(0.035, width * 0.14)
    top_band = max(0.06, height * 0.16)
    sill_band = max(0.08, height * 0.14)
    side_zone_width = min(0.24, max(0.12, width * 0.55))

    return {
        "opening_no_go_zone": _zone(uv["u0"], uv["u1"], uv["v0"], uv["v1"]),
        "opening_glass_zone": _zone(uv["u0"], uv["u1"], uv["v0"], uv["v1"]),
        "interior_head_zone": _zone(uv["u0"] - 0.04, uv["u1"] + 0.04, uv["v0"] - top_band, uv["v0"] + 0.025),
        "interior_blind_zone": _zone(uv["u0"] + 0.012, uv["u1"] - 0.012, uv["v0"] + 0.012, uv["v1"] - 0.012),
        "short_curtain_zone": _zone(uv["u0"] - 0.03, uv["u1"] + 0.03, uv["v0"] - 0.02, uv["v0"] + height * 0.42),
        "full_drape_zone": _zone(uv["u0"] - 0.055, uv["u1"] + 0.055, uv["v0"] - 0.035, min(0.98, uv["v1"] + 0.08)),
        "exterior_awning_zone": _zone(uv["u0"] - 0.07, uv["u1"] + 0.07, uv["v0"] - top_band * 1.2, uv["v0"] + 0.08),
        "left_wall_planting_zone": _zone(uv["u0"] - gap - side_zone_width, uv["u0"] - gap, uv["v0"] + 0.03, min(0.94, uv["v1"] + 0.1)),
        "right_wall_planting_zone": _zone(uv["u1"] + gap, uv["u1"] + gap + side_zone_width, uv["v0"] + 0.03, min(0.94, uv["v1"] + 0.1)),
        "sill_planter_zone": _zone(uv["u0"] - 0.02, uv["u1"] + 0.02, uv["v1"] - sill_band, min(0.98, uv["v1"] + 0.08)),
        "floor_planting_zone": _zone(max(0.04, uv["u0"] - 0.24), min(0.96, uv["u1"] + 0.24), min(0.82, uv["v1"] + 0.02), 0.98),
    }


def build_host_geometry(room_model: dict[str, Any]) -> dict[str, Any]:
    """Build invisible placement hosts for visual retrofit component QA."""

    walls = room_model.get("walls", [])
    components = room_model.get("components", [])
    windows = [item for item in components if item.get("component_type") == "window"]
    main_opening = max(windows, key=lambda item: item.get("estimated_area_m2") or 0, default=None)

    wall_hosts = []
    for index, wall in enumerate(walls):
        wall_hosts.append(
            {
                "id": f"{wall['id']}_HOST",
                "surface_id": wall["id"],
                "surface_type": "wall",
                "ui_label": f"wall {index + 1:02d}",
                "start_xyz": wall.get("start_xyz"),
                "end_xyz": wall.get("end_xyz"),
                "height_m": wall.get("height_m"),
                "length_m": wall.get("length_m"),
                "normal": wall.get("normal"),
                "interior_side": "room_side",
                "exterior_side": "outside_side",
                "visible": False,
            }
        )

    opening_hosts = []
    for component in windows:
        uv = _opening_uv(component)
        is_main = bool(main_opening and component.get("id") == main_opening.get("id"))
        opening_hosts.append(
            {
                "id": f"{component['id']}_HOST",
                "component_id": component["id"],
                "wall_id": component.get("wall_id"),
                "surface_type": "opening",
                "component_type": component.get("component_type"),
                "ui_label": "main large opening" if is_main else "secondary opening",
                "is_main_opening": is_main,
                "uv": {key: round(value, 4) for key, value in uv.items()},
                "estimated_area_m2": component.get("estimated_area_m2"),
                "width_m": component.get("width_m"),
                "height_m": component.get("height_m"),
                "zones": _opening_zones(uv),
                "visible": False,
            }
        )

    component_rules = {
        "solarControlGlazing": {"host": "opening_glass_zone", "side": "inside", "blocks_opening": False},
        "venetianBlind": {"host": "interior_blind_zone", "side": "inside", "blocks_opening": False},
        "verticalBlind": {"host": "interior_blind_zone", "side": "inside", "blocks_opening": False},
        "romanShade": {"host": "interior_head_zone", "side": "inside", "blocks_opening": False},
        "shortSillCurtain": {"host": "short_curtain_zone", "side": "inside", "blocks_opening": False},
        "fullHeightDrape": {"host": "full_drape_zone", "side": "inside", "blocks_opening": "conditional"},
        "externalAwning": {"host": "exterior_awning_zone", "side": "outside", "blocks_opening": False},
        "wallInsulation": {"host": "wall_face", "side": "inside", "blocks_opening": False},
        "trellis": {"host": "right_wall_planting_zone", "side": "inside", "blocks_opening": False},
        "planterShelf": {"host": "sill_planter_zone", "side": "inside", "blocks_opening": False},
        "hangingRail": {"host": "left_wall_planting_zone", "side": "inside", "blocks_opening": False},
        "plantLadder": {"host": "left_wall_planting_zone", "side": "inside", "blocks_opening": False},
        "rectangularPlanter": {"host": "floor_planting_zone", "side": "inside", "blocks_opening": False},
        "floorPlants": {"host": "floor_planting_zone", "side": "inside", "blocks_opening": False},
        "airPath": {"host": "opening_no_go_zone", "side": "inside", "blocks_opening": False},
        "ceilingFan": {"host": "ceiling_center", "side": "inside", "blocks_opening": False},
    }

    room_id = room_model.get("room", {}).get("id", "ROOM")
    return {
        "version": "HVRA_HOST_GEOMETRY_V1",
        "purpose": "Invisible placement hosts for strategy component QA over the textured room viewer.",
        "room_id": room_id,
        "main_opening_id": main_opening.get("id") if main_opening else None,
        "main_wall_id": main_opening.get("wall_id") if main_opening else None,
        "surfaces": {
            "walls": wall_hosts,
            "floor": {"id": f"{room_id}_FLOOR_HOST", "surface_type": "floor", "visible": False},
            "ceiling": {"id": f"{room_id}_CEILING_HOST", "surface_type": "ceiling", "visible": False},
        },
        "openings": opening_hosts,
        "component_rules": component_rules,
        "notes": [
            "Host geometry is invisible and should be regenerated from spatial_index JSON.",
            "Texture pixels identify openings; strategy components attach to normalized wall zones.",
            "Wall 08 in the UI corresponds to ROOM_001_WALL_07 for the current test case.",
        ],
    }
