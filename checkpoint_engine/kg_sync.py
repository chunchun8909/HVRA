from __future__ import annotations


def build_kg_update_summary(stage: str, stage_result: dict, context: dict | None = None) -> dict:
    context = context or {}
    if stage == "spatial_vv":
        return {
            "stage": stage,
            "kg_updated": False,
            "mode": "summary_only",
            "reason": "Spatial V&V waits for user confirmation before graph writes should be treated as calculation-ready.",
            "recommended_future_write": [
                "Room -> HAS_WALL -> Wall",
                "Wall -> HAS_WINDOW/HAS_DOOR/HAS_FURNITURE -> Component",
                "Component -> HAS_USER_VERIFICATION -> SpatialOverride",
            ],
            "candidate_nodes": {
                "room": stage_result.get("room", {}).get("id"),
                "wall_count": len(stage_result.get("walls", [])),
                "component_count": len(stage_result.get("components", [])),
            },
            "traceability_targets": {
                "spatial_index": context.get("spatial_index_path", "data/intermediate/spatial_index.json"),
                "spatial_overrides": "data/intermediate/spatial_user_overrides.json",
            },
        }

    if stage == "strategy_validation":
        options = stage_result.get("validated_options", [])
        return {
            "stage": stage,
            "kg_updated": False,
            "mode": "summary_only",
            "reason": "Checkpoint package is generated before the user chooses whether to continue, edit, or rerun.",
            "recommended_future_write": [
                "Room -> HAS_BASELINE_RISK -> BaselineIndicator",
                "Strategy -> HAS_VALIDATION_RESULT -> BenchmarkResult",
                "Strategy -> IMPROVES -> Indicator",
                "Strategy -> HAS_CONFIDENCE_GATE -> ConfidenceGate",
                "UserDecision -> SELECTS_OR_REVISES -> Strategy",
            ],
            "candidate_nodes": {
                "room": stage_result.get("room_id"),
                "strategies": [
                    {
                        "id": option.get("strategy", {}).get("strategy_id"),
                        "name": option.get("strategy", {}).get("strategy_name"),
                        "benchmark_status": option.get("benchmark_result", {}).get("overall"),
                        "confidence": option.get("confidence", {}).get("level"),
                    }
                    for option in options
                ],
            },
            "traceability_targets": {
                "problem_map": context.get("problem_map_path", "data/intermediate/problem_map.json"),
                "spatial_index": context.get("spatial_index_path", "data/intermediate/spatial_index.json"),
                "validation_options": context.get(
                    "validation_options_path",
                    "data/intermediate/retrofit_validation_options.json",
                ),
            },
        }

    return {
        "stage": stage,
        "kg_updated": False,
        "mode": "summary_only",
        "candidate_nodes": {},
        "recommended_future_write": [],
    }
