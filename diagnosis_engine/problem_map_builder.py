from __future__ import annotations


HIGH_SOLAR_ORIENTATIONS = {"S", "SW", "W", "SE"}

PROBLEM_ACTIONS = {
    "excess_solar_gain": {
        "plain_action": "Reduce direct sun before it enters the room, starting with external shading on the exposed window wall.",
        "suggested_strategy_ids": [
            "window_external_shutters",
            "external_shading_louvers",
            "solar_control_glazing",
            "internal_blinds",
        ],
        "surface_instruction": "Prioritise the external wall and any detected glazing on the high-solar facade.",
    },
    "poor_nocturnal_recovery": {
        "plain_action": "Lower retained heat overnight by combining safe night ventilation with roof or ceiling heat-transfer reduction where the room is top-floor exposed.",
        "suggested_strategy_ids": [
            "night_purge_ventilation",
            "stack_effect_roof_vent",
            "roof_insulation",
            "cool_roof_coating",
            "phase_change_materials",
        ],
        "surface_instruction": "Prioritise the ceiling or roof-adjacent surfaces and the external opening used for night purge.",
    },
    "ventilation_deficit": {
        "plain_action": "Increase useful air change and create a safer purge path; if cross-flow is not available, use a low-disruption opening or stack-assisted exhaust strategy.",
        "suggested_strategy_ids": [
            "interior_opening_improvement",
            "stack_effect_roof_vent",
            "night_purge_ventilation",
            "window_enlargement",
            "cross_ventilation_behaviour",
        ],
        "surface_instruction": "Prioritise the confirmed external opening wall and any internal path that can connect it to another air route.",
    },
    "envelope_heat_transfer": {
        "plain_action": "Reduce heat transfer through the exposed opaque envelope using insulation reinforcement or reflective/cool surface treatment.",
        "suggested_strategy_ids": [
            "wall_insulation_reinforcement_layer",
            "internal_wall_insulation",
            "external_wall_insulation_etics",
            "cool_facade_paint",
        ],
        "surface_instruction": "Prioritise the external wall surfaces identified in the spatial problem map.",
    },
}


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _wall_lookup(spatial_index: dict) -> dict[str, dict]:
    return {wall["id"]: wall for wall in spatial_index.get("walls", [])}


def _windows_by_wall(spatial_index: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for window in spatial_index.get("windows", []):
        grouped.setdefault(window.get("wall_id"), []).append(window)
    return grouped


def _doors_by_wall(spatial_index: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for door in spatial_index.get("doors", []):
        grouped.setdefault(door.get("wall_id"), []).append(door)
    return grouped


def _target_payload(walls: list[dict], windows_by_wall: dict[str, list[dict]], reason: str) -> list[dict]:
    targets = []
    for wall in walls:
        wall_windows = windows_by_wall.get(wall["id"], [])
        targets.append(
            {
                "wall_id": wall["id"],
                "surface_type": "wall",
                "orientation": wall.get("orientation"),
                "is_external": wall.get("is_external", False),
                "estimated_area_m2": wall.get("estimated_area_m2"),
                "window_ids": [window["id"] for window in wall_windows],
                "window_area_m2": round(
                    sum(float(window.get("estimated_area_m2", 0) or 0) for window in wall_windows),
                    3,
                ),
                "assignment_reason": reason,
            }
        )
    return targets


def _action_payload(problem_type: str, spatial_targets: list[dict]) -> dict:
    action = PROBLEM_ACTIONS[problem_type]
    target_labels = []
    for target in spatial_targets:
        if target.get("wall_id"):
            label = target["wall_id"]
            if target.get("orientation"):
                label = f"{label} ({target['orientation']})"
            target_labels.append(label)
        elif target.get("surface_id"):
            target_labels.append(target["surface_id"])
    return {
        "plain_action": action["plain_action"],
        "surface_instruction": action["surface_instruction"],
        "target_surfaces": _unique(target_labels),
        "candidate_strategy_ids": action["suggested_strategy_ids"],
    }


def _solar_problem_targets(diagnosis_result: dict, spatial_index: dict) -> tuple[list[str], list[dict]]:
    walls = spatial_index.get("walls", [])
    windows_by_wall = _windows_by_wall(spatial_index)
    primary_orientation = (
        diagnosis_result.get("calculation_details", {})
        .get("solar_gain", {})
        .get("primary_orientation")
    )
    target_walls = [
        wall
        for wall in walls
        if wall.get("orientation") == primary_orientation and wall.get("is_external", False)
    ]
    if not target_walls:
        target_walls = [wall for wall in walls if wall.get("orientation") == primary_orientation]
    if not target_walls:
        target_walls = [wall for wall in walls if wall.get("orientation") in HIGH_SOLAR_ORIENTATIONS]
    reason = "primary EPW-adjusted solar orientation from diagnosis"
    wall_ids = [wall["id"] for wall in target_walls]
    window_ids = [window["id"] for wall_id in wall_ids for window in windows_by_wall.get(wall_id, [])]
    fallback_window_ids = []
    if not window_ids:
        fallback_window_ids = [window["id"] for window in spatial_index.get("windows", [])]
        window_ids = fallback_window_ids
    targets = _target_payload(target_walls, windows_by_wall, reason)
    if fallback_window_ids:
        for target in targets:
            target["fallback_window_ids"] = fallback_window_ids
            target["fallback_reason"] = (
                "Detected windows were not geometrically assigned to the primary solar wall; "
                "they remain contributors because the solar calculation used total detected glazing."
            )
    return _unique(wall_ids + window_ids), targets


def _night_problem_targets(spatial_index: dict) -> tuple[list[str], list[dict]]:
    walls = spatial_index.get("walls", [])
    windows_by_wall = _windows_by_wall(spatial_index)
    target_walls = [wall for wall in walls if wall.get("is_external", False)]
    if not target_walls:
        target_walls = [wall for wall in walls if wall.get("orientation") in HIGH_SOLAR_ORIENTATIONS]
    contributors = [wall["id"] for wall in target_walls]
    contributors.extend(window["id"] for wall in target_walls for window in windows_by_wall.get(wall["id"], []))
    targets = _target_payload(target_walls, windows_by_wall, "external/top-floor heat-retention surface")
    room = spatial_index.get("room", {})
    if room.get("is_top_floor"):
        targets.append(
            {
                "surface_id": spatial_index.get("ceiling", {}).get("id", f"{room.get('id', 'ROOM')}_CEILING"),
                "surface_type": "ceiling",
                "assignment_reason": "top-floor roof/ceiling exposure from building_info",
            }
        )
    return _unique(contributors), targets


def _ventilation_problem_targets(spatial_index: dict) -> tuple[list[str], list[dict]]:
    walls = spatial_index.get("walls", [])
    windows_by_wall = _windows_by_wall(spatial_index)
    doors_by_wall = _doors_by_wall(spatial_index)
    target_walls = [wall for wall in walls if wall.get("is_external", False)]
    if not target_walls:
        target_walls = walls[:1]
    contributors = [spatial_index["room"]["id"]]
    contributors.extend(wall["id"] for wall in target_walls)
    for wall in target_walls:
        contributors.extend(window["id"] for window in windows_by_wall.get(wall["id"], []))
        contributors.extend(door["id"] for door in doors_by_wall.get(wall["id"], []))
    targets = _target_payload(target_walls, windows_by_wall, "single-sided ventilation limiting ACH")
    for target in targets:
        target["door_ids"] = [door["id"] for door in doors_by_wall.get(target["wall_id"], [])]
    return _unique(contributors), targets


def _problem(
    room_id: str,
    problem_type: str,
    severity: float,
    primary_cause: str,
    contributors: list[str],
    spatial_targets: list[dict],
) -> dict:
    action = _action_payload(problem_type, spatial_targets)
    return {
        "id": f"{room_id}_PROBLEM_{problem_type.upper()}",
        "problem_type": problem_type,
        "severity": severity,
        "primary_cause": primary_cause,
        "contributors": contributors,
        "spatial_targets": spatial_targets,
        "suggested_action": action["plain_action"],
        "suggested_actions": [
            {
                "action_type": "retrofit_or_operation",
                "description": action["plain_action"],
                "surface_instruction": action["surface_instruction"],
                "target_surfaces": action["target_surfaces"],
                "candidate_strategy_ids": action["candidate_strategy_ids"],
            }
        ],
    }


def build_problem_map(diagnosis_result: dict, spatial_index: dict) -> dict:
    room_id = diagnosis_result["room_id"]
    scores = diagnosis_result["component_scores"]

    problems = []
    if scores["solar_gain"] >= 0.6:
        contributors, spatial_targets = _solar_problem_targets(diagnosis_result, spatial_index)
        problems.append(
            _problem(
                room_id,
                "excess_solar_gain",
                scores["solar_gain"],
                "high-solar orientation and unshaded glazing",
                contributors,
                spatial_targets,
            )
        )
    if scores["nocturnal_recovery"] >= 0.6:
        contributors, spatial_targets = _night_problem_targets(spatial_index)
        problems.append(
            _problem(
                room_id,
                "poor_nocturnal_recovery",
                scores["nocturnal_recovery"],
                "top-floor exposure and retained heat",
                contributors,
                spatial_targets,
            )
        )
    if scores["ventilation_deficit"] >= 0.5:
        contributors, spatial_targets = _ventilation_problem_targets(spatial_index)
        problems.append(
            _problem(
                room_id,
                "ventilation_deficit",
                scores["ventilation_deficit"],
                "single-sided ventilation and low estimated ACH against heat-risk target",
                contributors,
                spatial_targets,
            )
        )
    if scores.get("envelope", 0) >= 0.7:
        contributors, spatial_targets = _night_problem_targets(spatial_index)
        problems.append(
            _problem(
                room_id,
                "envelope_heat_transfer",
                scores["envelope"],
                "weak opaque envelope or roof exposure increasing heat transfer",
                contributors,
                spatial_targets,
            )
        )

    action_ids = _unique(
        strategy_id
        for problem in problems
        for action in problem.get("suggested_actions", [])
        for strategy_id in action.get("candidate_strategy_ids", [])
    )

    return {
        "case_id": diagnosis_result["case_id"],
        "room_id": room_id,
        "risk_level": diagnosis_result["risk_level"],
        "summary": f"{diagnosis_result['risk_level']} heat-risk room with {len(problems)} mapped problem(s).",
        "suggested_action_summary": (
            "Prioritise a combined package: improve safe night ventilation, reduce roof/ceiling heat retention, "
            "and treat the confirmed external wall/opening before relying on a single behavioural measure."
            if problems
            else "No mapped high-severity problem requires retrofit action."
        ),
        "suggested_strategy_ids": action_ids,
        "problems": problems,
    }
