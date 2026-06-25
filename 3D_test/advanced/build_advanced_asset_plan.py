"""Build an advanced GLB-ready retrofit asset plan.

This is a non-interactive planning layer. It does not download assets and does
not render the room. It reads the current HVRA spatial/constraint outputs and
selects higher-quality GLB-ready asset slots with decision reasons.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import struct

ROOT_DIR = Path(__file__).resolve().parents[2]
SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index_with_overrides.json"
FALLBACK_SPATIAL_PATH = ROOT_DIR / "data" / "intermediate" / "spatial_index.json"
CONSTRAINTS_PATH = ROOT_DIR / "data" / "input" / "retrofit_constraints.json"
BUILDING_INFO_PATH = ROOT_DIR / "data" / "input" / "building_info.json"
CATALOGUE_PATH = Path(__file__).resolve().parent / "advanced_asset_catalogue.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "advanced_asset_plan.json"


def read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return fallback or {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def png_size(path_value: str | None) -> tuple[int | None, int | None]:
    if not path_value:
        return None, None
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() != ".png":
        return None, None
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None, None


def opening_position_from_bbox(component: dict[str, Any]) -> dict[str, Any]:
    bbox = component.get("bbox_px") or []
    width_px, height_px = png_size(component.get("wall_fragment_image"))
    if len(bbox) < 4:
        return {"wall_position_ratio": 0.5, "vertical_position_ratio": 0.5, "bbox_source": "fallback_center"}
    image_w = width_px or max(float(bbox[2]), 1.0)
    image_h = height_px or max(float(bbox[3]), 1.0)
    center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
    center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
    bbox_w = max(float(bbox[2]) - float(bbox[0]), 0.0)
    bbox_h = max(float(bbox[3]) - float(bbox[1]), 0.0)
    return {
        "wall_position_ratio": min(max(center_x / image_w, 0.0), 1.0),
        "vertical_position_ratio": min(max(center_y / image_h, 0.0), 1.0),
        "bbox_width_ratio": min(max(bbox_w / image_w, 0.0), 1.0),
        "bbox_height_ratio": min(max(bbox_h / image_h, 0.0), 1.0),
        "wall_fragment_image_size_px": {"width": width_px, "height": height_px},
        "bbox_source": "sam3_bbox_on_wall_fragment",
    }


def infer_opening(spatial: dict[str, Any], override: str | None = None) -> dict[str, Any]:
    components = spatial.get("components", [])
    openings = [item for item in components if item.get("component_type") in {"window", "door"}]
    if not openings:
        return {"opening_type": override or "window", "component": None, "target_wall_id": None}
    component = max(openings, key=lambda item: float(item.get("estimated_area_m2") or 0))
    height = component.get("height_m") or component.get("estimated_height_m") or 0
    width = component.get("width_m") or component.get("estimated_width_m") or 0
    area = component.get("estimated_area_m2") or 0
    inferred = "window"
    if component.get("component_type") == "door" or float(height or 0) >= 1.9 or float(area or 0) >= 3.2 or float(width or 0) >= 1.15:
        inferred = "sliding_glass_door"
    return {
        "opening_type": override or inferred,
        "inferred_opening_type": inferred,
        "override_used": bool(override),
        "component": component,
        "target_wall_id": component.get("wall_id"),
        "width_m": width,
        "height_m": height,
        "area_m2": area,
        **opening_position_from_bbox(component),
    }


def boolish(value: Any) -> bool:
    return bool(value) and str(value).lower() not in {"false", "0", "none", "no"}


def max_status(current: str, candidate: str) -> str:
    order = {"allowed": 0, "conditional": 1, "blocked": 2}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def evaluate_asset(
    asset: dict[str, Any],
    family: dict[str, Any],
    opening: dict[str, Any],
    constraints: dict[str, Any],
    building_info: dict[str, Any],
) -> dict[str, Any]:
    opening_type = opening.get("opening_type", "window")
    reasons: list[str] = []
    status = asset.get("default_status", "allowed")

    ownership = str(constraints.get("ownership_status") or constraints.get("ownership_type") or "").lower()
    facing = str(building_info.get("facing_direction") or "").upper()
    excluded = set(constraints.get("excluded_strategy_type") or [])
    low_disruption = "major_structural_change" in excluded or constraints.get("disruption_tolerance") == "low"
    facade_allowed = boolish(constraints.get("facade_modification_allowed")) or boolish(constraints.get("owner_approval_available"))
    balcony_access = boolish(constraints.get("has_balcony")) or boolish(building_info.get("has_balcony")) or boolish(constraints.get("outdoor_maintenance_access"))
    ceiling_height = float(building_info.get("room_height_m") or 2.8)
    low_head_height = ceiling_height < 2.45
    has_damp_risk = boolish(constraints.get("mold_risk")) or boolish(constraints.get("damp_wall"))
    needs_low_maintenance = str(constraints.get("maintenance_tolerance") or "").lower() in {"low", "very_low"}
    likely_low_daylight = facing in {"N", "NE", "NW"} and not boolish(building_info.get("high_daylight"))
    active_door = opening_type in {"sliding_glass_door", "balcony_door"}
    width = float(opening.get("width_m") or 0)
    side_clearance_limited = active_door and width >= 1.1 and not balcony_access

    avoid_tokens = set(asset.get("avoid_for", []))

    if opening_type not in family.get("valid_openings", []):
        status = "blocked"
        reasons.append(f"Family {family.get('family')} is not suitable for {opening_type}.")

    if opening_type in avoid_tokens:
        status = "blocked"
        reasons.append(f"Asset is explicitly avoided for {opening_type}.")

    if "no_facade_permission" in avoid_tokens and not facade_allowed:
        status = "blocked"
        reasons.append("Facade-mounted asset requires owner/building approval.")

    if family.get("requires_facade_permission") is True and not facade_allowed:
        status = "blocked"
        reasons.append("Facade-mounted asset requires owner/building approval.")

    if family.get("requires_balcony_or_maintenance_access") and asset.get("id") != "glb_interior_plant_cluster" and not balcony_access:
        status = "blocked"
        reasons.append("Biophilic exterior asset requires balcony or outdoor maintenance access.")

    if "rental_no_ceiling_fixing" in avoid_tokens and ownership == "renter":
        status = max_status(status, "conditional")
        reasons.append("Ceiling or rail fixing should be renter-safe or user-confirmed before use.")

    if "low_head_height" in avoid_tokens and low_head_height:
        status = max_status(status, "conditional")
        reasons.append("Head clearance is limited; rail height and hanging drop need confirmation.")

    if "frequently_used_door_without_side_clearance" in avoid_tokens and side_clearance_limited:
        status = max_status(status, "conditional")
        reasons.append("Sliding/balcony door operation must stay clear; place asset beside the active passage, not in front of it.")

    if "mobility_clearance_conflict" in avoid_tokens and low_disruption:
        status = max_status(status, "conditional")
        reasons.append("Maintain a clear circulation strip; use compact/side placement only.")

    if "low_daylight" in avoid_tokens and likely_low_daylight:
        status = max_status(status, "conditional")
        reasons.append("North-facing daylight may be limited; choose shade-tolerant species or preserved greenery.")

    if "low_maintenance_requirement" in avoid_tokens and needs_low_maintenance:
        status = max_status(status, "conditional")
        reasons.append("Living climbing plants require pruning/watering; confirm maintenance capacity.")

    if {"damp_wall", "mold_risk", "direct_splash_zone"} & avoid_tokens and has_damp_risk:
        status = "blocked"
        reasons.append("Biophilic wall panels should not be placed on damp or mold-risk surfaces.")

    if not reasons:
        reasons.append("Asset is compatible with current opening and constraint assumptions.")

    reasons = list(dict.fromkeys(reasons))

    if family.get("family", "").startswith("biophilic"):
        reasons.append("Biophilic assets support comfort perception and nature connection; they are not counted as the primary air-quality or thermal-control system.")

    reasons = list(dict.fromkeys(reasons))

    return {
        "asset_id": asset["id"],
        "label": asset["label"],
        "family": family["family"],
        "status": status,
        "target_wall_id": opening.get("target_wall_id"),
        "opening_type": opening_type,
        "strategy_binding": asset.get("strategy_binding", []),
        "future_glb_slot": asset.get("future_glb_slot"),
        "procedural_fallback": asset.get("procedural_fallback"),
        "placement_rule": asset.get("placement_rule"),
        "plant_palette": asset.get("plant_palette", []),
        "care_profile": asset.get("care_profile"),
        "reasons": reasons,
    }


def build_plan(opening_type: str | None = None) -> dict[str, Any]:
    spatial = read_json(SPATIAL_PATH) or read_json(FALLBACK_SPATIAL_PATH)
    constraints = read_json(CONSTRAINTS_PATH)
    building_info = read_json(BUILDING_INFO_PATH)
    catalogue = read_json(CATALOGUE_PATH)
    opening = infer_opening(spatial, override=opening_type)

    candidates = []
    for family in catalogue.get("families", []):
        for asset in family.get("assets", []):
            candidates.append(evaluate_asset(asset, family, opening, constraints, building_info))

    allowed = [item for item in candidates if item["status"] == "allowed"]
    conditional = [item for item in candidates if item["status"] == "conditional"]
    blocked = [item for item in candidates if item["status"] == "blocked"]

    return {
        "plan_id": "HVRA_ADVANCED_3D_ASSET_PLAN_V1",
        "mode": "advanced_glb_ready_asset_plan",
        "source": {
            "spatial": str(SPATIAL_PATH if SPATIAL_PATH.exists() else FALLBACK_SPATIAL_PATH),
            "constraints": str(CONSTRAINTS_PATH),
            "building_info": str(BUILDING_INFO_PATH),
            "catalogue": str(CATALOGUE_PATH),
        },
        "building_context": {
            "room_id": spatial.get("room_id") or spatial.get("id") or "ROOM_001",
            "building_type": building_info.get("building_type"),
            "ownership_status": constraints.get("ownership_status") or constraints.get("ownership_type"),
            "facade_modification_allowed": constraints.get("facade_modification_allowed"),
            "has_balcony": constraints.get("has_balcony") or building_info.get("has_balcony"),
            "facing_direction": building_info.get("facing_direction"),
            "room_height_m": building_info.get("room_height_m"),
        },
        "opening_context": opening,
        "asset_quality_requirements": catalogue.get("quality_requirements", {}),
        "summary": {
            "allowed": len(allowed),
            "conditional": len(conditional),
            "blocked": len(blocked),
            "preferred_next_step": "Replace procedural fallbacks with curated GLB assets for allowed and conditional candidates only.",
        },
        "allowed_assets": allowed,
        "conditional_assets": conditional,
        "blocked_assets": blocked,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opening-type", choices=["window", "sliding_glass_door", "balcony_door"], default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    plan = build_plan(args.opening_type)
    write_json(args.output, plan)
    print(f"Wrote {args.output}")
    print(f"Opening: {plan['opening_context'].get('opening_type')}")
    print(f"Allowed: {plan['summary']['allowed']} | Conditional: {plan['summary']['conditional']} | Blocked: {plan['summary']['blocked']}")


if __name__ == "__main__":
    main()
