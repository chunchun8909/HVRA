from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.config import CHECKPOINT_DIR, INTERMEDIATE_DIR
from utils.file_io import read_json, write_json


def _packages(stage_result: dict) -> list[dict]:
    return stage_result.get("packages") or stage_result.get("phase3_strategy_packages", {}).get("packages", [])


def _find_package(stage_result: dict, package_id: str | None) -> dict | None:
    if not package_id:
        return None
    for package in _packages(stage_result):
        if package.get("package_id") == package_id:
            return package
    return None


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


def _package_validation_payload(stage_result: dict, package: dict) -> dict:
    strategy = {
        "strategy_id": package.get("package_id"),
        "strategy_name": package.get("package_name"),
        "strategy_type": "strategy_package",
        "source_strategy_ids": package.get("selected_strategy_ids", []),
        "source_strategy_names": package.get("selected_strategy_names", []),
    }
    visual = package.get("visual_generation", {})
    return {
        "case_id": stage_result.get("case_id") or package.get("case_id"),
        "room_id": stage_result.get("room_id") or package.get("room_id"),
        "selected_package_id": package.get("package_id"),
        "selected_package": package,
        "selected_strategy_ids": package.get("selected_strategy_ids", []),
        "selected_strategy": strategy,
        "strategy": strategy,
        "baseline": stage_result.get("baseline", {}),
        "numerical_comparison": package.get("before_after", []),
        "package_before_after": package.get("before_after", []),
        "benchmark_result": {
            "overall": package.get("benchmark_status"),
            "source": "phase3_strategy_package_optimizer",
            "optimizer_score": package.get("optimizer_score", {}),
        },
        "confidence": {"level": package.get("confidence_level")},
        "recommendation": package.get("user_label"),
        "effect_profile": package.get("combined_effect_profile", {}),
        "combined_effect_profile": package.get("combined_effect_profile", {}),
        "visual_generation": visual,
        "component_ids": visual.get("component_ids", []),
        "relationship_links": package.get("relationship_links", {}),
        "target": package.get("target", {}),
        "selection_method": package.get("selection_method"),
    }


def _choose_package(stage_result: dict, package: dict, user_decision: dict, action: str) -> dict[str, Any]:
    validation_payload = _package_validation_payload(stage_result, package)
    user_selection = {
        "id": f"{stage_result.get('case_id', 'CASE')}_SELECTION_001",
        "case_id": stage_result.get("case_id"),
        "selected_package_id": package.get("package_id"),
        "selected_package": package,
        "selected_strategy": validation_payload["selected_strategy"],
        "selected_strategy_ids": package.get("selected_strategy_ids", []),
        "component_ids": validation_payload.get("component_ids", []),
        "responds_to_problem_ids": package.get("relationship_links", {}).get("target_problem_ids", []),
        "selection_mode": f"checkpoint_{action}",
        "checkpoint_decision": user_decision,
    }
    write_json(INTERMEDIATE_DIR / "user_selection.json", user_selection)
    write_json(INTERMEDIATE_DIR / "retrofit_validation.json", validation_payload)
    write_json(INTERMEDIATE_DIR / "user_decision.json", user_decision)
    return {
        "status": "applied",
        "action": action,
        "selected_package_id": package.get("package_id"),
        "selected_strategy_ids": package.get("selected_strategy_ids", []),
        "rerun_from_stage": "gemini_prompt",
        "then_continue": ["gemini_result", "llm_review", "final_report"],
        "written": [
            "data/intermediate/user_selection.json",
            "data/intermediate/retrofit_validation.json",
            "data/intermediate/user_decision.json",
        ],
    }


def _choose_option(stage_result: dict, user_decision: dict, action: str) -> dict[str, Any]:
    selected_ids = (
        user_decision.get("selected_package_ids")
        or user_decision.get("selected_strategy_ids")
        or [stage_result.get("recommended_package_id") or stage_result.get("recommended_option_id")]
    )
    selected_id = selected_ids[0] if selected_ids else None
    package = _find_package(stage_result, selected_id)
    if package is not None:
        return _choose_package(stage_result, package, user_decision, action)

    option = _find_option(stage_result, selected_id)
    if option is None:
        raise ValueError(f"Selected package or strategy was not found in validation options: {selected_id}")

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
        selected_ids = (
            user_decision.get("combine_package_ids")
            or user_decision.get("combine_strategy_ids")
            or user_decision.get("selected_package_ids")
            or user_decision.get("selected_strategy_ids", [])
        )
        if len(selected_ids) < 2:
            raise ValueError("combine_options requires at least two option ids.")
        payload = {
            "case_id": stage_result.get("case_id"),
            "room_id": stage_result.get("room_id"),
            "option_ids": selected_ids,
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
