from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from utils.config import INTERMEDIATE_DIR
from utils.file_io import read_json, write_json


DEFAULT_OVERRIDES_PATH = INTERMEDIATE_DIR / "spatial_user_overrides.json"
VALID_ORIENTATIONS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}


def _override_map(overrides: dict, key: str) -> dict[str, dict]:
    mapped = {}
    for item in overrides.get(key, []):
        item_id = item.get("id") or item.get("component_id") or item.get("surface_id")
        if item_id:
            mapped[item_id] = item
    return mapped


def _include_item(item: dict, override: dict | None) -> bool:
    if not override:
        return True
    if override.get("include_in_calculation") is False:
        return False
    if override.get("included") is False:
        return False
    if override.get("visible") is False and override.get("affects_calculation", True):
        return False
    return True


def _orientation_map(overrides: dict) -> dict[str, dict]:
    mapped = {}
    for item in overrides.get("orientation_overrides", []):
        item_id = item.get("id") or item.get("wall_id")
        orientation = str(item.get("orientation", "")).upper()
        if item_id and orientation in VALID_ORIENTATIONS:
            mapped[item_id] = {
                **item,
                "orientation": orientation,
            }
    return mapped


def spatial_orientation_confirmed(spatial_index: dict, overrides: dict | None = None) -> bool:
    if overrides is None:
        if not DEFAULT_OVERRIDES_PATH.exists():
            return False
        overrides = read_json(DEFAULT_OVERRIDES_PATH)

    if overrides.get("orientation_confirmed") is not True:
        return False

    orientation_overrides = _orientation_map(overrides)
    wall_ids = [wall.get("id") for wall in spatial_index.get("walls", []) if wall.get("id")]
    if not wall_ids:
        return False
    return all(wall_id in orientation_overrides for wall_id in wall_ids)


def apply_spatial_overrides(spatial_index: dict, overrides: dict | None = None) -> dict:
    if overrides is None:
        if not DEFAULT_OVERRIDES_PATH.exists():
            return spatial_index
        overrides = read_json(DEFAULT_OVERRIDES_PATH)

    result = deepcopy(spatial_index)
    component_overrides = _override_map(overrides, "component_overrides")
    surface_overrides = _override_map(overrides, "surface_overrides")
    orientation_overrides = _orientation_map(overrides)

    removed_components = []
    for group in ["components", "windows", "doors", "furniture"]:
        kept = []
        for item in result.get(group, []):
            override = component_overrides.get(item.get("id"))
            if _include_item(item, override):
                if override:
                    item["user_override"] = override
                kept.append(item)
            else:
                removed_components.append(
                    {
                        "id": item.get("id"),
                        "component_type": item.get("component_type"),
                        "wall_id": item.get("wall_id"),
                        "reason": override.get("reason", "user excluded in spatial V&V"),
                    }
                )
        result[group] = kept

    removed_surfaces = []
    for group in ["walls"]:
        kept = []
        for item in result.get(group, []):
            override = surface_overrides.get(item.get("id"))
            if _include_item(item, override):
                if override:
                    item["user_override"] = override
                orientation_override = orientation_overrides.get(item.get("id"))
                if orientation_override:
                    item["orientation"] = orientation_override["orientation"]
                    item["orientation_source"] = "user_confirmed_spatial_vv"
                    item["orientation_confidence"] = "confirmed"
                    if "is_external" in orientation_override:
                        item["is_external"] = bool(orientation_override["is_external"])
                kept.append(item)
            else:
                removed_surfaces.append(
                    {
                        "id": item.get("id"),
                        "surface_type": item.get("surface_type", "wall"),
                        "reason": override.get("reason", "user excluded in spatial V&V"),
                    }
                )
        result[group] = kept

    result["spatial_user_overrides"] = {
        "source": str(DEFAULT_OVERRIDES_PATH),
        "applied": True,
        "orientation_confirmed": spatial_orientation_confirmed(result, overrides),
        "orientation_overrides": list(orientation_overrides.values()),
        "removed_components": removed_components,
        "removed_surfaces": removed_surfaces,
        "notes": overrides.get("notes", []),
    }
    result["orientation_review"] = {
        "required_before_diagnosis": True,
        "confirmed": result["spatial_user_overrides"]["orientation_confirmed"],
        "source": "data/intermediate/spatial_user_overrides.json",
        "notes": [
            "LGTNet creates room geometry first.",
            "User-confirmed wall orientations are required before diagnosis and KG graph writes.",
        ],
    }
    write_json(INTERMEDIATE_DIR / "spatial_index_with_overrides.json", result)
    return result


def load_spatial_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict:
    if not path.exists():
        return {
            "stage": "spatial_vv",
            "status": "not_provided",
            "orientation_confirmed": False,
            "orientation_overrides": [],
            "component_overrides": [],
            "surface_overrides": [],
        }
    return read_json(path)
