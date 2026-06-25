from __future__ import annotations


def build_llm_review_prompt(stage: str, stage_result: dict, context: dict | None = None) -> dict:
    context = context or {}
    if stage == "spatial_vv":
        return {
            "stage": stage,
            "llm_task": "Guide the user through spatial verification before calculations continue.",
            "system_instruction": (
                "Ask the user to verify walls, surface textures, and detected components in room_3d_view.html. "
                "If anything is wrong, instruct them to export spatial_user_overrides.json and rerun from diagnosis."
            ),
            "review_questions": [
                "Do the wall count, floor/ceiling shape, and room orientation look correct?",
                "Are any windows, doors, or furniture detections false positives?",
                "Should any component be excluded before thermal calculations?",
            ],
            "allowed_user_actions": ["continue", "export_overrides", "rerun_spatial", "stop"],
            "required_response_schema": {
                "action": "continue | export_overrides | rerun_spatial | stop",
                "reason": "",
                "rerun_from_stage": "",
            },
            "context_files": {
                "spatial_index": context.get("spatial_index_path", "data/intermediate/spatial_index.json"),
                "room_3d_view": context.get("room_3d_view", "data/output/spatial/room_3d_view.html"),
            },
        }

    if stage == "strategy_validation":
        packages = stage_result.get("packages") or stage_result.get("phase3_strategy_packages", {}).get("packages", [])
        compact_options = []
        if packages:
            for index, package in enumerate(packages, start=1):
                visual = package.get("visual_generation", {})
                compact_options.append(
                    {
                        "validation_rank": index,
                        "package_id": package.get("package_id"),
                        "strategy_id": package.get("package_id"),
                        "strategy_name": package.get("package_name"),
                        "benchmark_status": package.get("benchmark_status"),
                        "confidence": package.get("confidence_level"),
                        "recommendation": package.get("user_label"),
                        "selected_strategy_ids": package.get("selected_strategy_ids", []),
                        "component_ids": visual.get("component_ids", []),
                        "before_after": package.get("before_after", {}),
                        "optimizer_score": package.get("optimizer_score"),
                    }
                )
        else:
            options = stage_result.get("validated_options", [])
            for option in options:
                strategy = option.get("strategy", {})
                compact_options.append(
                    {
                        "validation_rank": option.get("validation_rank"),
                        "strategy_id": strategy.get("strategy_id"),
                        "strategy_name": strategy.get("strategy_name"),
                        "benchmark_status": option.get("benchmark_result", {}).get("overall"),
                        "confidence": option.get("confidence", {}).get("level"),
                        "recommendation": option.get("recommendation"),
                        "numerical_comparison": option.get("numerical_comparison", []),
                    }
                )

        return {
            "stage": stage,
            "llm_task": "Guide the user through a validation checkpoint before final retrofit selection.",
            "system_instruction": (
                "You are an evidence-checking retrofit assistant. Explain benchmark results plainly, "
                "ask the user to choose, combine, revise, or rerun, and preserve traceability to JSON outputs."
            ),
            "review_questions": [
                "Does the recommended strategy reduce the baseline thermal risk enough?",
                "Should the user choose one option, combine options, or revise the retrofit intent?",
                "Are confidence warnings serious enough to rerun an earlier stage?",
                "Does the requested change require strategy ranking, validation, Gemini, or report regeneration?",
            ],
            "allowed_user_actions": stage_result.get("checkpoint_guidance", {}).get("allowed_actions", []),
            "options_for_user": compact_options,
            "required_response_schema": {
                "action": "choose_option | combine_options | revise_intent | rerun_strategy_ranking | accept_partial_pass | stop",
                "selected_package_ids": [],
                "selected_strategy_ids": [],
                "intent_revision": "",
                "reason": "",
                "rerun_from_stage": "",
            },
            "context_files": {
                "validation_options": context.get(
                    "validation_options_path",
                    "data/intermediate/retrofit_validation_options.json",
                ),
                "problem_map": context.get("problem_map_path", "data/intermediate/problem_map.json"),
                "spatial_index": context.get("spatial_index_path", "data/intermediate/spatial_index.json"),
            },
        }

    return {
        "stage": stage,
        "llm_task": "Review checkpoint result.",
        "allowed_user_actions": [],
        "required_response_schema": {},
    }
