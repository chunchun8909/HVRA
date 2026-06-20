from __future__ import annotations


INTERPRETED_CASE_KEYS = ["case_id", "scenario", "diagnosis_profile", "priorities"]
STRATEGY_OPTION_KEYS = ["strategy_id", "strategy_name", "rank", "rationale", "constraints_fit"]
REVIEW_KEYS = ["consistency_status", "issues", "recommendations"]


def _require_keys(payload: dict, keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ValueError(f"{label} missing required keys: {', '.join(missing)}")


def validate_interpreted_case(payload: dict) -> dict:
    _require_keys(payload, INTERPRETED_CASE_KEYS, "interpreted_case")
    if payload["diagnosis_profile"] not in {"elderly_heat_risk", "renter_low_budget", "default"}:
        payload["diagnosis_profile"] = "default"
    payload.setdefault("notes", [])
    return payload


def validate_strategy_options(payload: dict) -> dict:
    _require_keys(payload, ["ranked_strategies"], "strategy_options")
    if not isinstance(payload["ranked_strategies"], list):
        raise ValueError("strategy_options.ranked_strategies must be a list")

    for index, strategy in enumerate(payload["ranked_strategies"], start=1):
        _require_keys(strategy, STRATEGY_OPTION_KEYS, f"ranked_strategies[{index}]")
        strategy["rank"] = int(strategy["rank"])
    payload["ranked_strategies"] = sorted(payload["ranked_strategies"], key=lambda item: item["rank"])
    return payload


def validate_review(payload: dict) -> dict:
    _require_keys(payload, REVIEW_KEYS, "llm_review")
    if not isinstance(payload["issues"], list):
        payload["issues"] = [str(payload["issues"])]
    if not isinstance(payload["recommendations"], list):
        payload["recommendations"] = [str(payload["recommendations"])]
    return payload
