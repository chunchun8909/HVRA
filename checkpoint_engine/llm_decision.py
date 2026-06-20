from __future__ import annotations

import json
from pathlib import Path

from llm_agent.ollama_client import generate_json
from utils.config import CHECKPOINT_DIR, Settings, load_settings
from utils.file_io import read_json, write_json


def _checkpoint_decision_prompt(llm_review_prompt: dict) -> str:
    return "\n\n".join(
        [
            "You are the HVRA checkpoint decision assistant.",
            "Return one valid JSON object only. Do not use markdown.",
            "Your job is to help route the retrofit validation checkpoint.",
            "Prefer choose_option if one option is clearly recommended; prefer revise_intent or combine_options when no option passes enough benchmarks.",
            f"checkpoint_review={json.dumps(llm_review_prompt, ensure_ascii=False)}",
            """Return exactly this shape:
{
  "stage": "strategy_validation",
  "status": "llm_recommended",
  "action": "choose_option | combine_options | revise_intent | rerun_strategy_ranking | accept_partial_pass | stop",
  "selected_strategy_ids": ["string"],
  "combine_strategy_ids": ["string"],
  "intent_revision": "string",
  "spatial_overrides_path": "data/intermediate/spatial_user_overrides.json",
  "reason": "string",
  "rerun_from_stage": "string",
  "allowed_actions": ["choose_option", "combine_options", "revise_intent", "rerun_strategy_ranking", "accept_partial_pass", "stop"]
}""",
        ]
    )


def _mock_decision(llm_review_prompt: dict) -> dict:
    options = llm_review_prompt.get("options_for_user", [])
    best = options[0] if options else {}
    selected_id = best.get("strategy_id")
    status = best.get("benchmark_status")
    action = "choose_option" if status == "pass" else "accept_partial_pass"
    return {
        "stage": "strategy_validation",
        "status": "llm_recommended_mock",
        "action": action,
        "selected_strategy_ids": [selected_id] if selected_id else [],
        "combine_strategy_ids": [],
        "intent_revision": "",
        "spatial_overrides_path": "data/intermediate/spatial_user_overrides.json",
        "reason": (
            "Mock checkpoint decision selected the highest-ranked validation option. "
            "The current result is partial, so the decision is marked as accept_partial_pass."
        ),
        "rerun_from_stage": "selected_retrofit_validation",
        "allowed_actions": llm_review_prompt.get("allowed_user_actions", []),
    }


def _normalize_decision(decision: dict, llm_review_prompt: dict) -> dict:
    allowed = llm_review_prompt.get("allowed_user_actions", [])
    action = decision.get("action")
    if action not in allowed:
        selected_ids = decision.get("selected_strategy_ids", [])
        combine_ids = decision.get("combine_strategy_ids", [])
        if len(combine_ids) > 1:
            decision["action"] = "combine_options"
            decision["status"] = "llm_action_repaired"
            decision["reason"] = (
                f"LLM returned an invalid action field ({action}); inferred combine_options "
                "from combine_strategy_ids."
            )
        elif selected_ids:
            selected_id = selected_ids[0]
            selected_option = next(
                (
                    option
                    for option in llm_review_prompt.get("options_for_user", [])
                    if option.get("strategy_id") == selected_id
                ),
                {},
            )
            benchmark_status = selected_option.get("benchmark_status")
            decision["action"] = "choose_option" if benchmark_status == "pass" else "accept_partial_pass"
            decision["status"] = "llm_action_repaired"
            decision["reason"] = (
                f"LLM returned an invalid action field ({action}); inferred {decision['action']} "
                f"from selected strategy {selected_id} with benchmark status {benchmark_status}."
            )
        else:
            decision["action"] = None
            decision["status"] = "invalid_llm_action_waiting_for_user"
            decision["reason"] = f"LLM returned an action outside the allowed set: {action}"
    decision.setdefault("stage", "strategy_validation")
    decision.setdefault("status", "llm_recommended")
    decision.setdefault("selected_strategy_ids", [])
    decision.setdefault("combine_strategy_ids", [])
    decision.setdefault("intent_revision", "")
    decision.setdefault("spatial_overrides_path", "data/intermediate/spatial_user_overrides.json")
    decision.setdefault("reason", "")
    decision.setdefault("rerun_from_stage", "")
    decision["allowed_actions"] = allowed
    return decision


def run_llm_checkpoint_decision(
    checkpoint_name: str = "08_strategy_validation",
    settings: Settings | None = None,
    *,
    checkpoint_root: Path = CHECKPOINT_DIR,
) -> dict:
    settings = settings or load_settings()
    package_dir = checkpoint_root / checkpoint_name
    llm_review_prompt = read_json(package_dir / "llm_review_prompt.json")
    if settings.use_mock_llm:
        decision = _mock_decision(llm_review_prompt)
    else:
        decision = generate_json(settings, _checkpoint_decision_prompt(llm_review_prompt))
    decision = _normalize_decision(decision, llm_review_prompt)
    write_json(package_dir / "user_decision.json", decision)
    return decision
