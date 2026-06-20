from __future__ import annotations

from utils.config import SPATIAL_OUTPUT_DIR
from utils.file_io import write_json


def _risk_label(severity: str | float | int | None, score: float | None) -> str:
    if isinstance(severity, str):
        return severity.replace("_", " ")
    if isinstance(severity, (int, float)):
        score = float(severity)
    if score is None:
        return "not assigned"
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.40:
        return "moderate"
    return "low"


def _factor_label(problem: dict) -> str:
    problem_type = str(problem.get("problem_type", "heat risk")).replace("_", " ")
    primary = problem.get("primary_cause")
    if primary:
        return f"{problem_type}: {str(primary).replace('_', ' ')}"
    drivers = problem.get("drivers") or []
    if drivers:
        first = str(drivers[0]).replace("_", " ")
        return f"{problem_type}: {first}"
    return problem_type


def _problem_action(problem: dict) -> dict:
    actions = problem.get("suggested_actions") or []
    if actions:
        first = actions[0]
        return {
            "description": first.get("description") or problem.get("suggested_action") or "review mapped heat-risk problem",
            "surface_instruction": first.get("surface_instruction"),
            "candidate_strategy_ids": first.get("candidate_strategy_ids", []),
        }
    return {
        "description": problem.get("suggested_action") or "review mapped heat-risk problem",
        "surface_instruction": None,
        "candidate_strategy_ids": [],
    }


def _empty_wall(wall_id: str | None) -> dict:
    return {
        "wall_id": wall_id,
        "risk_label": "not assigned",
        "top_factor": "no mapped problem",
        "suggested_action": "no selected fix mapped to this wall",
        "candidate_strategy_ids": [],
        "problem_ids": [],
        "problems": [],
    }


def build_wall_diagnosis_state(problem_map: dict, spatial_index: dict) -> dict:
    by_wall = {}
    for wall in spatial_index.get("walls", []):
        by_wall[wall.get("id")] = _empty_wall(wall.get("id"))

    for problem in problem_map.get("problems", []):
        score = problem.get("score")
        severity = float(problem.get("severity", score or 0) or 0)
        action = _problem_action(problem)
        for target in problem.get("spatial_targets", []):
            wall_id = target.get("wall_id")
            if not wall_id:
                continue
            existing = by_wall.setdefault(wall_id, _empty_wall(wall_id))
            existing["problem_ids"].append(problem.get("id"))
            existing["problems"].append(
                {
                    "problem_id": problem.get("id"),
                    "problem_type": problem.get("problem_type"),
                    "severity": round(severity, 3),
                    "factor": _factor_label(problem),
                    "suggested_action": action["description"],
                    "surface_instruction": action["surface_instruction"],
                    "candidate_strategy_ids": action["candidate_strategy_ids"],
                }
            )

    for wall_state in by_wall.values():
        problems = sorted(wall_state["problems"], key=lambda item: item.get("severity", 0), reverse=True)
        wall_state["problems"] = problems
        if not problems:
            continue
        top = problems[0]
        wall_state["risk_label"] = _risk_label(top.get("severity"), None)
        wall_state["top_factor"] = top.get("factor") or "mapped heat-risk problem"
        wall_state["suggested_action"] = top.get("suggested_action") or "review mapped heat-risk problem"
        wall_state["candidate_strategy_ids"] = top.get("candidate_strategy_ids", [])

    return {
        "room_id": spatial_index.get("room", {}).get("id"),
        "suggested_action_summary": problem_map.get("suggested_action_summary"),
        "walls": by_wall,
    }


def export_wall_diagnosis_state(problem_map: dict, spatial_index: dict) -> dict:
    state = build_wall_diagnosis_state(problem_map, spatial_index)
    write_json(SPATIAL_OUTPUT_DIR / "wall_diagnosis_state.json", state)
    return state
