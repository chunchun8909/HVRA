from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.config import INTERMEDIATE_DIR, INPUT_DIR, SPATIAL_OUTPUT_DIR
from utils.file_io import write_json

OPTION_COMPONENTS_BY_EFFECT = {
    "night_purge_ventilation": ["ceilingFan", "airPath"],
    "secure_night_vent_limiter": ["ceilingFan", "airPath", "venetianBlind"],
    "cross_ventilation_behaviour": ["ceilingFan", "airPath", "trellis", "planterShelf", "rectangularPlanter", "floorPlants"],
    "internal_blinds": ["venetianBlind", "romanShade", "shortSillCurtain"],
    "external_shading": ["externalAwning"],
    "external_shading_louvers": ["externalAwning"],
    "solar_control_glazing": ["solarControlGlazing"],
    "ceiling_fan_air_movement": ["ceilingFan", "airPath"],
    "interior_biophilic_cooling_zone": ["trellis", "planterShelf", "hangingRail", "plantLadder", "rectangularPlanter", "floorPlants"],
    "wall_insulation_reinforcement_layer": ["wallInsulation"],
    "internal_wall_insulation": ["wallInsulation"],
}


COMPONENT_LAYOUT_RULES = {
    "fullHeightDrape": {"group": "internal_shading", "lane": "opening_full_height", "exclusive_group": "window_covering", "room_bound": "opening_width"},
    "shortSillCurtain": {"group": "internal_shading", "lane": "opening_upper_half", "exclusive_group": "window_covering", "room_bound": "opening_width"},
    "romanShade": {"group": "internal_shading", "lane": "opening_head", "exclusive_group": "window_covering", "room_bound": "opening_width"},
    "venetianBlind": {"group": "internal_shading", "lane": "opening_glass", "exclusive_group": "window_covering", "room_bound": "opening_width"},
    "verticalBlind": {"group": "internal_shading", "lane": "opening_glass", "exclusive_group": "window_covering", "room_bound": "opening_width"},
    "solarControlGlazing": {"group": "glazing", "lane": "opening_glass", "exclusive_group": None, "room_bound": "opening_width"},
    "externalAwning": {"group": "external_shading", "lane": "outside_head", "exclusive_group": None, "room_bound": "opening_width"},
    "ceilingFan": {"group": "air_movement", "lane": "ceiling_center", "exclusive_group": None, "room_bound": "ceiling"},
    "rectangularPlanter": {"group": "biophilic", "lane": "floor_right_low", "exclusive_group": None, "room_bound": "floor_clear_zone"},
    "planterShelf": {"group": "biophilic", "lane": "right_wall_mid", "exclusive_group": None, "room_bound": "wall_side_zone"},
    "hangingRail": {"group": "biophilic", "lane": "left_wall_high", "exclusive_group": None, "room_bound": "wall_side_zone"},
    "plantLadder": {"group": "biophilic", "lane": "left_wall_low", "exclusive_group": None, "room_bound": "floor_clear_zone"},
    "trellis": {"group": "biophilic", "lane": "right_wall_high", "exclusive_group": None, "room_bound": "wall_side_zone"},
    "floorPlants": {"group": "biophilic", "lane": "floor_left_low", "exclusive_group": None, "room_bound": "floor_clear_zone"},
    "wallInsulation": {"group": "envelope", "lane": "interior_wall_face", "exclusive_group": None, "room_bound": "wall_face"},
    "airPath": {"group": "operation_overlay", "lane": "opening_no_go_zone", "exclusive_group": None, "room_bound": "opening_width"},
}

INTERNAL_SHADING_PRIORITY = ["venetianBlind", "romanShade", "shortSillCurtain", "verticalBlind", "fullHeightDrape"]


def _resolve_component_conflicts(component_ids: list[str]) -> list[str]:
    """Keep options readable: one internal covering plus compatible support components."""
    selected: list[str] = []
    has_covering = False
    for preferred in INTERNAL_SHADING_PRIORITY:
        if preferred in component_ids:
            selected.append(preferred)
            has_covering = True
            break
    for component_id in component_ids:
        rule = COMPONENT_LAYOUT_RULES.get(component_id, {})
        if rule.get("exclusive_group") == "window_covering" and has_covering:
            continue
        if component_id not in selected:
            selected.append(component_id)
    return selected

QA_ALL_COMPONENTS = [
    "fullHeightDrape",
    "shortSillCurtain",
    "romanShade",
    "venetianBlind",
    "verticalBlind",
    "solarControlGlazing",
    "externalAwning",
    "ceilingFan",
    "rectangularPlanter",
    "planterShelf",
    "hangingRail",
    "plantLadder",
    "trellis",
    "floorPlants",
    "wallInsulation",
    "airPath",
]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _components_for_option(option: dict[str, Any]) -> list[str]:
    strategy = option.get("strategy", {})
    strategy_id = strategy.get("strategy_id") or ""
    effect_id = option.get("effect_profile", {}).get("effect_profile_id") or strategy.get("effect_profile_id") or strategy_id
    text = " ".join(
        str(value).lower()
        for value in [strategy_id, effect_id, strategy.get("strategy_name"), strategy.get("rationale")]
        if value
    )
    components = list(OPTION_COMPONENTS_BY_EFFECT.get(effect_id, OPTION_COMPONENTS_BY_EFFECT.get(strategy_id, [])))
    if not components:
        if "shade" in text or "blind" in text or "curtain" in text:
            components.extend(["venetianBlind", "romanShade"])
        if "glaz" in text or "film" in text:
            components.append("solarControlGlazing")
        if "fan" in text or "vent" in text or "purge" in text:
            components.extend(["ceilingFan", "airPath"])
        if "plant" in text or "green" in text or "biophilic" in text:
            components.extend(["trellis", "planterShelf", "floorPlants"])
        if "insulation" in text or "envelope" in text:
            components.append("wallInsulation")
    ordered = []
    for item in components:
        if item not in ordered:
            ordered.append(item)
    return _resolve_component_conflicts(ordered) or ["ceilingFan", "airPath"]


def build_component_composition() -> dict[str, Any]:
    validation = _load_json(INTERMEDIATE_DIR / "retrofit_validation_options.json", {})
    host = _load_json(SPATIAL_OUTPUT_DIR / "host_geometry.json", {})
    visual_catalogue = _load_json(INPUT_DIR / "visual_retrofit_catalogue.json", {})
    variants = visual_catalogue.get("tested_component_variants", {}).get("components", {})
    options = []
    for index, option in enumerate(validation.get("validated_options", [])[:3], start=1):
        strategy = option.get("strategy", {})
        component_ids = _components_for_option(option)
        options.append(
            {
                "option_key": f"option_{index}",
                "label": f"option {index}",
                "strategy_id": strategy.get("strategy_id"),
                "strategy_name": strategy.get("strategy_name"),
                "target_wall_id": host.get("main_wall_id"),
                "target_opening_id": host.get("main_opening_id"),
                "components": [
                    {
                        "component_id": component_id,
                        "host": variants.get(component_id, {}).get("host"),
                        "effect_profile_id": variants.get(component_id, {}).get("effect_profile_id"),
                        "thermal_effect": variants.get(component_id, {}).get("thermal_effect"),
                        "layout_rule": COMPONENT_LAYOUT_RULES.get(component_id, {}),
                    }
                    for component_id in component_ids
                ],
            }
        )
    options.append(
        {
            "option_key": "all",
            "label": "all",
            "strategy_id": "qa_all_components",
            "strategy_name": "QA all tested 3D components",
            "target_wall_id": host.get("main_wall_id"),
            "target_opening_id": host.get("main_opening_id"),
            "components": [
                {
                    "component_id": component_id,
                    "host": variants.get(component_id, {}).get("host"),
                    "effect_profile_id": variants.get(component_id, {}).get("effect_profile_id"),
                    "thermal_effect": variants.get(component_id, {}).get("thermal_effect"),
                    "layout_rule": COMPONENT_LAYOUT_RULES.get(component_id, {}),
                }
                for component_id in QA_ALL_COMPONENTS
            ],
        }
    )
    return {
        "composition_id": "HVRA_COMPONENT_COMPOSITION_V1",
        "source_options": "data/intermediate/retrofit_validation_options.json",
        "host_geometry": "data/output/spatial/host_geometry.json",
        "visual_catalogue": "data/input/visual_retrofit_catalogue.json",
        "default_option_key": options[0]["option_key"] if options else "all",
        "options": options,
    }


def write_component_composition(path: Path | None = None) -> str:
    output_path = path or SPATIAL_OUTPUT_DIR / "component_composition.json"
    write_json(output_path, build_component_composition())
    return str(output_path)


if __name__ == "__main__":
    print(write_component_composition())

