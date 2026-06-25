from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.config import CHECKPOINT_DIR
from utils.file_io import write_json

from .kg_sync import build_kg_update_summary
from .llm_checkpoint import build_llm_review_prompt
from .viewer_sync import build_viewer_update_summary


def _json_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _default_user_decision(stage: str, stage_result: dict) -> dict:
    if stage == "spatial_vv":
        return {
            "stage": stage,
            "status": "waiting_for_user",
            "action": None,
            "reason": "",
            "spatial_overrides_path": "data/intermediate/spatial_user_overrides.json",
            "rerun_from_stage": None,
            "allowed_actions": ["confirm_orientation", "continue", "export_overrides", "rerun_spatial", "stop"],
        }

    if stage == "strategy_validation":
        recommended_id = stage_result.get("recommended_package_id") or stage_result.get("recommended_option_id")
        return {
            "stage": stage,
            "status": "waiting_for_user",
            "action": None,
            "selected_package_ids": [recommended_id] if recommended_id else [],
            "selected_strategy_ids": [recommended_id] if recommended_id else [],
            "combine_strategy_ids": [],
            "intent_revision": "",
            "spatial_overrides_path": "data/intermediate/spatial_user_overrides.json",
            "reason": "",
            "rerun_from_stage": None,
            "allowed_actions": stage_result.get("checkpoint_guidance", {}).get("allowed_actions", []),
        }

    return {
        "stage": stage,
        "status": "waiting_for_user",
        "action": None,
        "reason": "",
        "rerun_from_stage": None,
        "allowed_actions": [],
    }


def _rerun_policy(stage: str) -> dict[str, Any]:
    if stage == "spatial_vv":
        return {
            "confirm_orientation": {
                "writes": ["data/intermediate/spatial_user_overrides.json"],
                "rerun_from_stage": "diagnosis",
                "then_continue": ["risk_map", "spatial_graph", "diagnosis", "problem_map", "strategy_validation_checkpoint"],
            },
            "continue": {
                "writes": ["data/intermediate/spatial_index_with_overrides.json"],
                "rerun_from_stage": "diagnosis",
                "then_continue": ["problem_map", "strategy_ranking", "strategy_validation_checkpoint"],
            },
            "export_overrides": {
                "writes": ["data/intermediate/spatial_user_overrides.json"],
                "rerun_from_stage": "diagnosis",
                "then_continue": ["problem_map", "strategy_ranking", "strategy_validation_checkpoint"],
            },
            "rerun_spatial": {
                "writes": [],
                "rerun_from_stage": "spatial_engine",
                "then_continue": ["spatial_vv_checkpoint"],
            },
            "stop": {
                "writes": ["data/intermediate/user_decision.json"],
                "rerun_from_stage": None,
                "then_continue": [],
            },
        }

    if stage == "strategy_validation":
        return {
            "choose_option": {
                "writes": ["data/intermediate/user_selection.json", "data/intermediate/retrofit_validation.json"],
                "rerun_from_stage": "selected_retrofit_validation",
                "then_continue": ["gemini_prompt", "gemini_result", "llm_review", "final_report"],
            },
            "combine_options": {
                "writes": [
                    "data/intermediate/user_selection.json",
                    "data/intermediate/retrofit_validation.json",
                    "data/intermediate/combined_strategy_request.json",
                ],
                "rerun_from_stage": "retrofit_validation_options",
                "then_continue": ["gemini_prompt", "gemini_result", "llm_review", "final_report"],
            },
            "revise_intent": {
                "writes": ["data/intermediate/user_intent_revision.json"],
                "rerun_from_stage": "strategy_ranking",
                "then_continue": [
                    "retrofit_validation_options",
                    "strategy_validation_checkpoint",
                    "user_selection",
                ],
            },
            "rerun_strategy_ranking": {
                "writes": [],
                "rerun_from_stage": "strategy_ranking",
                "then_continue": ["retrofit_validation_options", "strategy_validation_checkpoint"],
            },
            "accept_partial_pass": {
                "writes": ["data/intermediate/user_selection.json", "data/intermediate/retrofit_validation.json"],
                "rerun_from_stage": "selected_retrofit_validation",
                "then_continue": ["gemini_prompt", "gemini_result", "llm_review", "final_report"],
            },
            "stop": {
                "writes": ["data/intermediate/user_decision.json"],
                "rerun_from_stage": None,
                "then_continue": [],
            },
            "future_spatial_correction": {
                "writes": ["data/intermediate/spatial_user_overrides.json"],
                "rerun_from_stage": "diagnosis",
                "then_continue": [
                    "problem_map",
                    "manual_check",
                    "strategy_ranking",
                    "retrofit_validation_options",
                    "strategy_validation_checkpoint",
                ],
            },
        }
    return {}


def create_checkpoint_package(
    stage: str,
    stage_result: dict,
    checkpoint_name: str,
    *,
    context: dict | None = None,
    checkpoint_root: Path = CHECKPOINT_DIR,
) -> dict:
    context = context or {}
    package_dir = checkpoint_root / checkpoint_name
    package_dir.mkdir(parents=True, exist_ok=True)

    kg_summary = build_kg_update_summary(stage, stage_result, context)
    viewer_summary = build_viewer_update_summary(stage, stage_result, context)
    llm_prompt = build_llm_review_prompt(stage, stage_result, context)
    user_decision = _default_user_decision(stage, stage_result)

    files = {
        "stage_result": package_dir / "stage_result.json",
        "kg_update_summary": package_dir / "kg_update_summary.json",
        "viewer_update_summary": package_dir / "viewer_update_summary.json",
        "llm_review_prompt": package_dir / "llm_review_prompt.json",
        "user_decision": package_dir / "user_decision.json",
        "checkpoint": package_dir / "checkpoint.json",
    }

    checkpoint = {
        "stage": stage,
        "checkpoint_name": checkpoint_name,
        "status": "waiting_for_user",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_source": context.get("canonical_source"),
        "primary_output": context.get("primary_output"),
        "files": {key: _json_path(path, checkpoint_root.parent) for key, path in files.items()},
        "review_targets": {
            "json": [context.get("primary_output")],
            "neo4j": kg_summary.get("recommended_future_write", []),
            "room_3d_view": viewer_summary.get("recommended_future_overlays", []),
            "llm_agent": llm_prompt.get("review_questions", []),
        },
        "allowed_actions": user_decision.get("allowed_actions", []),
        "rerun_policy": _rerun_policy(stage),
        "notes": [
            "JSON remains the canonical source of truth.",
            "Neo4j and room_3d_view.html are generated views from checkpoint-approved JSON.",
            "The user decision file is intentionally editable before continuation.",
        ],
    }

    write_json(files["stage_result"], stage_result)
    write_json(files["kg_update_summary"], kg_summary)
    write_json(files["viewer_update_summary"], viewer_summary)
    write_json(files["llm_review_prompt"], llm_prompt)
    write_json(files["user_decision"], user_decision)
    write_json(files["checkpoint"], checkpoint)
    return checkpoint


def create_strategy_validation_checkpoint(retrofit_validation_options: dict) -> dict:
    has_packages = bool(
        retrofit_validation_options.get("packages")
        or retrofit_validation_options.get("phase3_strategy_packages", {}).get("packages")
    )
    canonical_source = (
        "data/intermediate/phase3_strategy_packages.json"
        if has_packages
        else "data/intermediate/retrofit_validation_options.json"
    )
    return create_checkpoint_package(
        "strategy_validation",
        retrofit_validation_options,
        "08_strategy_validation",
        context={
            "canonical_source": canonical_source,
            "primary_output": canonical_source,
            "package_options_path": "data/intermediate/phase3_strategy_packages.json",
            "validation_options_path": "data/intermediate/retrofit_validation_options.json",
            "problem_map_path": "data/intermediate/problem_map.json",
            "spatial_index_path": "data/intermediate/spatial_index.json",
            "room_3d_view": "data/output/spatial/room_3d_view.html",
        },
    )


def create_spatial_vv_checkpoint(spatial_index: dict) -> dict:
    return create_checkpoint_package(
        "spatial_vv",
        spatial_index,
        "01_spatial_vv",
        context={
            "canonical_source": "data/intermediate/spatial_index.json",
            "primary_output": "data/intermediate/spatial_index.json",
            "spatial_index_path": "data/intermediate/spatial_index.json",
            "room_3d_view": "data/output/spatial/room_3d_view.html",
        },
    )
