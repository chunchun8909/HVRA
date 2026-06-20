from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.config import CHECKPOINT_DIR, INTERMEDIATE_DIR
from utils.file_io import read_json, write_json


def _find_option(stage_result: dict, strategy_id: str | None) -> dict | None:
    if not strategy_id:
        return None
    for option in stage_result.get("validated_options", []):
        if option.get("strategy", {}).get("strategy_id") == strategy_id:
            return option
    return None


def _selected_validation_payload(stage_result: dict, option: dict) -> dict:
    problem_targets = option.get("problem_targets", {})
    return {
        "case_id": stage_result.get("case_id"),
        "room_id": stage_result.get("room_id"),
        "selected_strategy": option.get("strategy", {}),
        "responds_to_problem_ids": list(problem_targets.keys()),
        "strategy": option.get("strategy", {}),
        "effect_profile": option.get("effect_profile", {}),
        "expected_retrofit_impact": option.get("expected_retrofit_impact", {}),
        "effect_assumption_use": option.get("effect_assumption_use", {}),
        "problem_targets": problem_targets,
        "baseline": option.get("baseline", stage_result.get("baseline", {})),
        "proposed": option.get("proposed", {}),
        "numerical_comparison": option.get("numerical_comparison", []),
        "improvements": option.get("improvements", {}),
        "benchmark_result": option.get("benchmark_result", {}),
        "confidence": option.get("confidence", {}),
        "recommendation": option.get("recommendation"),
    }


def _choose_option(stage_result: dict, user_decision: dict, action: str) -> dict[str, Any]:
    selected_ids = user_decision.get("selected_strategy_ids") or [stage_result.get("recommended_option_id")]
    selected_id = selected_ids[0] if selected_ids else None
    option = _find_option(stage_result, selected_id)
    if option is None:
        raise ValueError(f"Selected strategy was not found in validated options: {selected_id}")

    validation_payload = _selected_validation_payload(stage_result, option)
    user_selection = {
        "id": f"{stage_result.get('case_id', 'CASE')}_SELECTION_001",
        "case_id": stage_result.get("case_id"),
        "selected_strategy": option.get("strategy", {}),
        "responds_to_problem_ids": validation_payload["responds_to_problem_ids"],
        "selection_mode": f"checkpoint_{action}",
        "checkpoint_decision": user_decision,
    }
    write_json(INTERMEDIATE_DIR / "user_selection.json", user_selection)
    write_json(INTERMEDIATE_DIR / "retrofit_validation.json", validation_payload)
    write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
    return {
        "status": "applied",
        "action": action,
        "selected_strategy_id": selected_id,
        "rerun_from_stage": "gemini_prompt",
        "then_continue": ["gemini_result", "llm_review", "final_report"],
        "written": [
            "data/intermediate/user_selection.json",
            "data/intermediate/retrofit_validation.json",
            "data/intermediate/user_decision.json",
        ],
    }


def _mark_checkpoint_status(package_dir: Path, status: str, route: dict[str, Any]) -> None:
    checkpoint_path = package_dir / "checkpoint.json"
    checkpoint = read_json(checkpoint_path)
    checkpoint["status"] = status
    checkpoint["last_route"] = route
    write_json(checkpoint_path, checkpoint)


def apply_checkpoint_decision(
    checkpoint_name: str = "08_strategy_validation",
    *,
    checkpoint_root: Path = CHECKPOINT_DIR,
) -> dict[str, Any]:
    package_dir = checkpoint_root / checkpoint_name
    stage_result = read_json(package_dir / "stage_result.json")
    user_decision = read_json(package_dir / "user_decision.json")
    action = user_decision.get("action")

    if action in {"choose_option", "accept_partial_pass"}:
        route = _choose_option(stage_result, user_decision, action)
        _mark_checkpoint_status(package_dir, "decision_applied", route)
        return route

    if action == "combine_options":
        selected_ids = user_decision.get("combine_strategy_ids") or user_decision.get("selected_strategy_ids", [])
        if len(selected_ids) < 2:
            raise ValueError("combine_options requires at least two strategy ids.")
        payload = {
            "case_id": stage_result.get("case_id"),
            "room_id": stage_result.get("room_id"),
            "strategy_ids": selected_ids,
            "reason": user_decision.get("reason", ""),
            "source_checkpoint": checkpoint_name,
            "status": "needs_validation_rerun",
        }
        write_json(INTERMEDIATE_DIR / "combined_strategy_request.json", payload)
        write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
        route = {
            "status": "routed",
            "action": action,
            "rerun_from_stage": "retrofit_validation_options",
            "written": [
                "data/intermediate/combined_strategy_request.json",
                "data/intermediate/user_decision.json",
            ],
        }
        _mark_checkpoint_status(package_dir, "decision_routed", route)
        return route

    if action == "revise_intent":
        payload = {
            "case_id": stage_result.get("case_id"),
            "room_id": stage_result.get("room_id"),
            "intent_revision": user_decision.get("intent_revision", ""),
            "reason": user_decision.get("reason", ""),
            "source_checkpoint": checkpoint_name,
            "status": "needs_strategy_rerank",
        }
        write_json(INTERMEDIATE_DIR / "user_intent_revision.json", payload)
        write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
        route = {
            "status": "routed",
            "action": action,
            "rerun_from_stage": "strategy_ranking",
            "written": [
                "data/intermediate/user_intent_revision.json",
                "data/intermediate/user_decision.json",
            ],
        }
        _mark_checkpoint_status(package_dir, "decision_routed", route)
        return route

    if action == "rerun_strategy_ranking":
        write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
        route = {
            "status": "routed",
            "action": action,
            "rerun_from_stage": "strategy_ranking",
            "written": ["data/intermediate/user_decision.json"],
        }
        _mark_checkpoint_status(package_dir, "decision_routed", route)
        return route

    if action == "stop":
        write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
        route = {
            "status": "stopped",
            "action": action,
            "rerun_from_stage": None,
            "written": ["data/intermediate/user_decision.json"],
        }
        _mark_checkpoint_status(package_dir, "stopped", route)
        return route

    return {
        "status": "waiting_for_user",
        "action": action,
        "message": "Edit user_decision.json with an allowed action before applying the checkpoint.",
        "user_decision_path": str(package_dir / "user_decision.json"),
    }
