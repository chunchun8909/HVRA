from __future__ import annotations

from utils.config import SPATIAL_OUTPUT_DIR
from utils.file_io import write_json


def build_viewer_update_summary(stage: str, stage_result: dict, context: dict | None = None) -> dict:
    context = context or {}
    if stage == "spatial_vv":
        return {
            "stage": stage,
            "viewer_updated": True,
            "mode": "interactive_html",
            "current_viewer": context.get("room_3d_view", "data/output/spatial/room_3d_view.html"),
            "recommended_future_overlays": [
                "surface/component include-exclude controls",
                "exportable spatial_user_overrides.json",
            ],
            "interactive_spatial_vv_contract": {
                "writes_to": "data/intermediate/spatial_user_overrides.json",
                "rerun_from_stage": "diagnosis",
                "review_items": {
                    "walls": len(stage_result.get("walls", [])),
                    "components": len(stage_result.get("components", [])),
                },
            },
        }

    if stage == "strategy_validation":
        options = stage_result.get("validated_options", [])
        viewer_state = {
            "stage": stage,
            "room_id": stage_result.get("room_id"),
            "recommended_option_id": stage_result.get("recommended_option_id"),
            "legend": {
                "pass": "#2f7d4f",
                "partial_pass": "#b7791f",
                "fail": "#b83232",
            },
            "strategy_badges": [
                {
                    "strategy_id": option.get("strategy", {}).get("strategy_id"),
                    "strategy_name": option.get("strategy", {}).get("strategy_name"),
                    "validation_rank": option.get("validation_rank"),
                    "benchmark_status": option.get("benchmark_result", {}).get("overall"),
                    "confidence": option.get("confidence", {}).get("level"),
                    "target_problem_ids": list(option.get("problem_targets", {}).keys()),
                }
                for option in options
            ],
        }
        state_path = SPATIAL_OUTPUT_DIR / "viewer_checkpoint_state.json"
        write_json(state_path, viewer_state)
        return {
            "stage": stage,
            "viewer_updated": True,
            "mode": "checkpoint_state_json",
            "state_path": "data/output/spatial/viewer_checkpoint_state.json",
            "reason": "The 3D viewer can load checkpoint status badges from viewer_checkpoint_state.json.",
            "current_viewer": context.get("room_3d_view", "data/output/spatial/room_3d_view.html"),
            "recommended_future_overlays": [
                "baseline heat-risk overlay by target wall or room surface",
                "validated strategy preview overlay",
                "benchmark pass/partial/fail badges",
                "confidence gate badge",
            ],
            "candidate_option_overlays": [
                {
                    "strategy_id": option.get("strategy", {}).get("strategy_id"),
                    "strategy_name": option.get("strategy", {}).get("strategy_name"),
                    "benchmark_status": option.get("benchmark_result", {}).get("overall"),
                    "target_problem_ids": list(option.get("problem_targets", {}).keys()),
                }
                for option in options
            ],
            "interactive_spatial_vv_contract": {
                "purpose": (
                    "Before diagnosis calculations, the user can confirm/deselect uncertain segmentation "
                    "or surface assignments in the HTML viewer."
                ),
                "writes_to": "data/intermediate/spatial_user_overrides.json",
                "example_override": {
                    "component_id": "ROOM_001_WINDOW_01",
                    "include_in_calculation": False,
                    "reason": "user marked as false positive in viewer",
                    "checkpoint_stage": "spatial_vv",
                },
                "rerun_from_stage": "diagnosis",
            },
        }

    return {
        "stage": stage,
        "viewer_updated": False,
        "mode": "summary_only",
        "recommended_future_overlays": [],
    }
