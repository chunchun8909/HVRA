from __future__ import annotations

from copy import deepcopy
from typing import Any

from validation_engine.combo_effects import combine_effect_profiles
from validation_engine.retrofit_effects import infer_effect_profile


SCENARIO_LIBRARY = [
    {
        "scenario_id": "solar_opening_control",
        "scenario_name": "Solar opening control",
        "trigger": "solar_gain_or_main_opening_exposure",
        "required_profiles": ["external_shading", "internal_blinds", "interior_biophilic_cooling_zone"],
        "fallback_profiles": ["solar_control_glazing", "temporary_window_film", "ceiling_fan_air_movement"],
        "visual_components": ["externalAwning", "venetianBlind", "trellis", "rectangularPlanterB"],
        "visual_density": "medium",
        "placement_logic": {
            "main_target": "main_window_wall",
            "left_side": ["rectangularPlanterB"],
            "right_side": ["trellis"],
            "opening_zone": ["venetianBlind"],
            "external_zone": ["externalAwning"],
        },
    },
    {
        "scenario_id": "night_purge_air_movement",
        "scenario_name": "Night purge and air movement",
        "trigger": "ventilation_deficit_or_poor_nocturnal_recovery",
        "required_profiles": ["night_purge_ventilation", "secure_night_vent_limiter", "ceiling_fan_air_movement"],
        "fallback_profiles": ["cross_ventilation_behaviour", "interior_opening_improvement"],
        "visual_components": ["verticalBlind", "hangingRail", "floorPlantsB", "rectangularPlanter", "ceilingFan"],
        "visual_density": "medium",
        "placement_logic": {
            "main_target": "main_window_wall_and_ceiling",
            "left_side": ["hangingRail", "floorPlantsB"],
            "right_side": ["rectangularPlanter"],
            "opening_zone": ["verticalBlind"],
            "ceiling_zone": ["ceilingFan"],
        },
    },
    {
        "scenario_id": "envelope_reinforcement",
        "scenario_name": "Wall insulation reinforcement",
        "trigger": "envelope_heat_transfer",
        "required_profiles": ["wall_insulation_reinforcement_layer", "internal_wall_insulation", "ceiling_fan_air_movement"],
        "fallback_profiles": ["cool_facade_paint", "phase_change_materials"],
        "visual_components": ["insulationReinforcementLayer", "romanShade", "planterShelfB", "floorPlants"],
        "visual_density": "medium",
        "placement_logic": {
            "main_target": "diagnosed_external_wall",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["planterShelfB"],
            "right_side": ["floorPlants"],
            "opening_zone": ["romanShade"],
        },
    },
    {
        "scenario_id": "low_disruption_vulnerable_resident",
        "scenario_name": "Low-disruption vulnerable resident support",
        "trigger": "high_vulnerability_or_low_disruption_constraint",
        "required_profiles": ["internal_blinds", "ceiling_fan_air_movement", "interior_biophilic_cooling_zone"],
        "fallback_profiles": ["secure_night_vent_limiter"],
        "visual_components": ["fullHeightDrape", "rectangularPlanter", "planterShelfB"],
        "visual_density": "low",
        "placement_logic": {
            "main_target": "main_window_wall",
            "left_side": ["planterShelfB"],
            "right_side": ["rectangularPlanter"],
            "opening_zone": ["fullHeightDrape"],
        },
    },
    {
        "scenario_id": "no_external_permission",
        "scenario_name": "Interior-only retrofit package",
        "trigger": "external_permission_limited",
        "required_profiles": ["internal_blinds", "wall_insulation_reinforcement_layer", "ceiling_fan_air_movement"],
        "fallback_profiles": ["interior_biophilic_cooling_zone", "phase_change_materials"],
        "visual_components": ["venetianBlind", "insulationReinforcementLayer", "planterShelf", "floorPlantsB", "ceilingFan"],
        "visual_density": "high",
        "placement_logic": {
            "main_target": "interior_wall_and_opening",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["floorPlantsB"],
            "right_side": ["planterShelf"],
            "opening_zone": ["venetianBlind"],
            "ceiling_zone": ["ceilingFan"],
        },
    },
    {
        "scenario_id": "critical_combined_heat_risk",
        "scenario_name": "Combined critical heat-risk package",
        "trigger": "critical_risk_requires_combination",
        "required_profiles": ["external_shading", "night_purge_ventilation", "wall_insulation_reinforcement_layer", "ceiling_fan_air_movement"],
        "fallback_profiles": ["interior_biophilic_cooling_zone", "secure_night_vent_limiter"],
        "visual_components": ["externalAwning", "shortSillCurtain", "insulationReinforcementLayer", "plantLadder", "trellis", "ceilingFan"],
        "visual_density": "high",
        "placement_logic": {
            "main_target": "main_window_wall_external_wall_and_ceiling",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["plantLadder"],
            "right_side": ["trellis"],
            "opening_zone": ["shortSillCurtain"],
            "external_zone": ["externalAwning"],
            "ceiling_zone": ["ceilingFan"],
        },
    },
    {
        "scenario_id": "benchmark_max_passive_package",
        "scenario_name": "Benchmark test: maximum passive package",
        "trigger": "test_option_chasing_all_benchmarks",
        "required_profiles": [
            "external_shading",
            "external_shutters",
            "solar_control_glazing",
            "temporary_window_film",
            "night_purge_ventilation",
            "secure_night_vent_limiter",
            "wall_insulation_reinforcement_layer",
            "internal_wall_insulation",
            "phase_change_materials",
            "ceiling_fan_air_movement",
        ],
        "fallback_profiles": ["interior_biophilic_cooling_zone"],
        "visual_components": ["externalAwning", "venetianBlind", "insulationReinforcementLayer", "hangingRail", "floorPlantsB", "rectangularPlanter", "ceilingFan"],
        "visual_density": "benchmark_high",
        "placement_logic": {
            "main_target": "full_opening_wall_ceiling_and_internal_layer",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["hangingRail", "floorPlantsB"],
            "right_side": ["rectangularPlanter"],
            "opening_zone": ["venetianBlind"],
            "external_zone": ["externalAwning"],
            "ceiling_zone": ["ceilingFan"],
        },
    },
    {
        "scenario_id": "benchmark_interior_only_high_package",
        "scenario_name": "Benchmark test: interior-only high package",
        "trigger": "test_option_no_external_permission_benchmark_chase",
        "required_profiles": [
            "internal_blinds",
            "solar_control_glazing",
            "wall_insulation_reinforcement_layer",
            "internal_wall_insulation",
            "phase_change_materials",
            "night_purge_ventilation",
            "secure_night_vent_limiter",
            "ceiling_fan_air_movement",
            "interior_biophilic_cooling_zone",
        ],
        "fallback_profiles": [],
        "visual_components": ["verticalBlind", "insulationReinforcementLayer", "planterShelf", "floorPlantsB", "rectangularPlanter", "ceilingFan"],
        "visual_density": "benchmark_high",
        "placement_logic": {
            "main_target": "interior_only_wall_opening_and_ceiling",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["floorPlantsB"],
            "right_side": ["planterShelf", "rectangularPlanter"],
            "opening_zone": ["verticalBlind"],
            "ceiling_zone": ["ceilingFan"],
        },
    },
    {
        "scenario_id": "benchmark_solar_vent_envelope_package",
        "scenario_name": "Benchmark test: solar + vent + envelope",
        "trigger": "test_option_balanced_high_performance_package",
        "required_profiles": [
            "external_shading",
            "external_shutters",
            "night_purge_ventilation",
            "cross_ventilation_behaviour",
            "wall_insulation_reinforcement_layer",
            "phase_change_materials",
            "ceiling_fan_air_movement",
            "interior_biophilic_cooling_zone",
        ],
        "fallback_profiles": [],
        "visual_components": ["externalAwning", "shortSillCurtain", "insulationReinforcementLayer", "plantLadder", "trellis", "rectangularPlanterB", "ceilingFan"],
        "visual_density": "benchmark_high",
        "placement_logic": {
            "main_target": "balanced_solar_vent_envelope_test",
            "wall_layer": ["insulationReinforcementLayer"],
            "left_side": ["plantLadder", "rectangularPlanterB"],
            "right_side": ["trellis"],
            "opening_zone": ["shortSillCurtain"],
            "external_zone": ["externalAwning"],
            "ceiling_zone": ["ceilingFan"],
        },
    },]


def _score_diagnosis(diagnosis: dict[str, Any]) -> dict[str, float]:
    scores = diagnosis.get("component_scores") or {}
    details = diagnosis.get("calculation_details") or {}
    room = diagnosis.get("room_diagnosis") or {}
    return {
        "solar_gain": float(scores.get("solar_gain", room.get("solar_gain_score", 0.0)) or 0.0),
        "ventilation_deficit": float(scores.get("ventilation_deficit", room.get("vent_deficit_score", 0.0)) or 0.0),
        "envelope": float(scores.get("envelope", room.get("envelope_score", 0.0)) or 0.0),
        "nocturnal_recovery": float(scores.get("nocturnal_recovery", 1.0 if room.get("nocturnal_recovery_fail") else 0.0) or 0.0),
        "occupant_vulnerability": float(scores.get("occupant_vulnerability", 0.0) or 0.0),
        "final_score": float(room.get("final_score", diagnosis.get("composite_risk_score_with_urban_context", 0.0)) or 0.0),
        "roof_exposed": 1.0 if (details.get("envelope") or {}).get("roof_exposed") else 0.0,
    }


def _scenario_priority(scenario_id: str, scores: dict[str, float]) -> float:
    if scenario_id == "solar_opening_control":
        return max(scores["solar_gain"], 0.35 if scores["final_score"] >= 0.75 else 0.0)
    if scenario_id == "night_purge_air_movement":
        return max(scores["ventilation_deficit"], scores["nocturnal_recovery"])
    if scenario_id == "envelope_reinforcement":
        return max(scores["envelope"], 0.65 if scores["roof_exposed"] else 0.0)
    if scenario_id == "low_disruption_vulnerable_resident":
        return scores["occupant_vulnerability"]
    if scenario_id == "no_external_permission":
        return max(scores["envelope"] * 0.8, scores["occupant_vulnerability"] * 0.65)
    if scenario_id == "critical_combined_heat_risk":
        return scores["final_score"]
    return 0.0


def _strategy_by_profile(ranked_strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for strategy in ranked_strategies:
        profile = infer_effect_profile(strategy)
        profile_id = str(profile.get("effect_profile_id", "generic"))
        if profile_id not in found:
            found[profile_id] = strategy
    return found


def _strategy_stub(profile_id: str) -> dict[str, Any]:
    return {
        "strategy_id": profile_id,
        "strategy_name": profile_id.replace("_", " ").title(),
        "constraints_fit": "added by conditional scenario rule because the diagnosis requires this effect type",
    }


def _select_strategies(template: dict[str, Any], by_profile: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for profile_id in template["required_profiles"]:
        selected.append(deepcopy(by_profile.get(profile_id, _strategy_stub(profile_id))))
    if not any(infer_effect_profile(strategy).get("effect_profile_id") == "ceiling_fan_air_movement" for strategy in selected):
        selected.append(deepcopy(by_profile.get("ceiling_fan_air_movement", _strategy_stub("ceiling_fan_air_movement"))))
    for profile_id in template.get("fallback_profiles", []):
        if len(selected) >= 4:
            break
        if profile_id in by_profile:
            selected.append(deepcopy(by_profile[profile_id]))
    return selected


def _visual_generation(template: dict[str, Any]) -> dict[str, Any]:
    components = list(template["visual_components"])
    placement_logic = deepcopy(template["placement_logic"])
    if "ceilingFan" not in components:
        components.append("ceilingFan")
    placement_logic.setdefault("ceiling_zone", [])
    if "ceilingFan" not in placement_logic["ceiling_zone"]:
        placement_logic["ceiling_zone"].append("ceilingFan")
    return {
        "component_ids": components,
        "density": template["visual_density"],
        "placement_logic": placement_logic,
        "notes": [
            "These are generated from conditional rules, not fixed test buttons.",
            "Ceiling fan is included by default when the room has no fan or AC, unless a later user constraint blocks it.",
            "Wall insulation reinforcement is rendered as a thin internal wall layer when selected.",
            "Biophilic components are supportive; they should not be used alone to claim benchmark compliance.",
        ],
    }


def _round_effect(effect: dict[str, Any]) -> dict[str, Any]:
    rounded = deepcopy(effect)
    for key, value in list(rounded.items()):
        if isinstance(value, float):
            rounded[key] = round(value, 3)
    return rounded


def generate_retrofit_generation_scenarios(
    diagnosis_result: dict[str, Any],
    strategy_options: dict[str, Any],
    limit: int = 6,
) -> dict[str, Any]:
    ranked = strategy_options.get("ranked_strategies", strategy_options.get("validated_options", []))
    ranked_strategies = [item.get("strategy", item) for item in ranked]
    by_profile = _strategy_by_profile(ranked_strategies)
    scores = _score_diagnosis(diagnosis_result)

    scenarios = []
    for template in SCENARIO_LIBRARY:
        priority = _scenario_priority(template["scenario_id"], scores)
        selected = _select_strategies(template, by_profile)
        effect_profiles = [infer_effect_profile(strategy) for strategy in selected]
        combined_effect = combine_effect_profiles(effect_profiles)
        scenarios.append(
            {
                "scenario_id": template["scenario_id"],
                "scenario_name": template["scenario_name"],
                "trigger": template["trigger"],
                "priority_score": round(priority, 3),
                "selected_strategy_ids": [s.get("strategy_id") for s in selected],
                "selected_strategy_names": [s.get("strategy_name") for s in selected],
                "visual_generation": _visual_generation(template),
                "combined_effect_profile": _round_effect(combined_effect),
                "source": "validation_engine.strategy_scenario_generator",
            }
        )

    scenarios.sort(key=lambda item: item["priority_score"], reverse=True)
    return {
        "case_id": diagnosis_result.get("case_id", "CASE_001"),
        "room_id": diagnosis_result.get("room_id", "ROOM_001"),
        "purpose": "Conditional retrofit scenario generation before Phase 3 visual integration.",
        "rules": {
            "minimum_visual_balance": "Each generated visual option should include clear left and right biophilic anchors when biophilic components are used.",
            "door_clearance": "Ground components must stay outside the sliding/opening path.",
            "wall_installation": "Wall-hosted components attach to the selected wall image plane and project inward only by their thickness.",
            "insulation_reinforcement": "Render as a thin internal lining on the diagnosed vulnerable wall, not as a freestanding object.",
            "numeric_effect_method": "Combined effects use validation_engine.combo_effects.combine_effect_profiles.",
        },
        "diagnosis_driver_scores": scores,
        "generated_scenarios": scenarios[:limit],
    }