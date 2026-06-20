from __future__ import annotations

from utils.config import Settings
from .ollama_client import generate_json
from .prompts import case_interpretation_prompt, review_prompt, strategy_ranking_prompt
from .schemas import validate_interpreted_case, validate_review, validate_strategy_options


def interpret_user_case(
    user_case: dict,
    building_info: dict,
    constraints: dict,
    settings: Settings,
) -> dict:
    if settings.use_mock_llm:
        profile = user_case.get("vulnerability_type") or "default"
        return {
            "case_id": user_case.get("case_id", "CASE_UNKNOWN"),
            "scenario": "nighttime_overheating_vulnerable_occupant",
            "diagnosis_profile": profile if profile in {"elderly_heat_risk", "renter_low_budget"} else "elderly_heat_risk",
            "priorities": user_case.get("priority", {}),
            "notes": [
                "Mock LLM interpretation used.",
                "Numerical diagnosis remains delegated to diagnosis_engine.",
            ],
        }

    return validate_interpreted_case(
        generate_json(settings, case_interpretation_prompt(user_case, building_info, constraints))
    )


def rank_retrofit_options(problem_map: dict, manual_check: dict, constraints: dict, settings: Settings) -> dict:
    if settings.use_mock_llm:
        return _rank_by_problem_actions(problem_map, manual_check)

    ranked_payload = validate_strategy_options(
        generate_json(settings, strategy_ranking_prompt(problem_map, manual_check, constraints))
    )
    return _dedupe_and_backfill_strategies(ranked_payload, manual_check, problem_map)


def _candidate_strategy_ids(problem_map: dict) -> list[str]:
    ids = []
    for strategy_id in problem_map.get("suggested_strategy_ids", []):
        if strategy_id not in ids:
            ids.append(strategy_id)
    for problem in problem_map.get("problems", []):
        for action in problem.get("suggested_actions", []):
            for strategy_id in action.get("candidate_strategy_ids", []):
                if strategy_id not in ids:
                    ids.append(strategy_id)
    return ids


def _problem_action_text(problem_map: dict, strategy_id: str) -> str:
    matched = []
    for problem in problem_map.get("problems", []):
        for action in problem.get("suggested_actions", []):
            if strategy_id in action.get("candidate_strategy_ids", []):
                matched.append(f"{problem.get('problem_type')}: {action.get('description')}")
    return " | ".join(matched)


def _rank_by_problem_actions(problem_map: dict, manual_check: dict) -> dict:
    eligible = {strategy.get("strategy_id"): strategy for strategy in manual_check.get("eligible_strategies", [])}
    ordered_ids = _candidate_strategy_ids(problem_map)
    ranked = []

    for strategy_id in ordered_ids:
        strategy = eligible.get(strategy_id)
        if not strategy:
            continue
        action_text = _problem_action_text(problem_map, strategy_id)
        ranked.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": strategy.get("strategy_name", strategy_id),
                "rank": len(ranked) + 1,
                "rationale": action_text or strategy.get("restriction") or strategy.get("evidence_snippet", ""),
                "constraints_fit": "selected because it directly responds to the mapped diagnosis action",
            }
        )

    for strategy in manual_check.get("eligible_strategies", []):
        strategy_id = strategy.get("strategy_id")
        if not strategy_id or any(item["strategy_id"] == strategy_id for item in ranked):
            continue
        ranked.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": strategy.get("strategy_name", strategy_id),
                "rank": len(ranked) + 1,
                "rationale": strategy.get("restriction") or strategy.get("evidence_snippet", ""),
                "constraints_fit": "eligible by manual/evidence check",
            }
        )

    return validate_strategy_options({"ranked_strategies": ranked})


def _dedupe_and_backfill_strategies(payload: dict, manual_check: dict, problem_map: dict) -> dict:
    seen = set()
    unique = []
    preferred_ids = _candidate_strategy_ids(problem_map)
    eligible = {strategy.get("strategy_id"): strategy for strategy in manual_check.get("eligible_strategies", [])}

    for strategy_id in preferred_ids:
        candidate = eligible.get(strategy_id)
        if not candidate or strategy_id in seen:
            continue
        seen.add(strategy_id)
        unique.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": candidate.get("strategy_name", strategy_id),
                "rank": len(unique) + 1,
                "rationale": _problem_action_text(problem_map, strategy_id) or candidate.get("restriction") or candidate.get("evidence_snippet", ""),
                "constraints_fit": "directly responds to mapped diagnosis action",
            }
        )

    for strategy in payload.get("ranked_strategies", []):
        strategy_id = strategy.get("strategy_id")
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        unique.append(strategy)

    for candidate in manual_check.get("eligible_strategies", []):
        strategy_id = candidate.get("strategy_id")
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        unique.append(
            {
                "strategy_id": strategy_id,
                "strategy_name": candidate.get("strategy_name", strategy_id),
                "rank": len(unique) + 1,
                "rationale": candidate.get("restriction") or candidate.get("evidence_snippet", ""),
                "constraints_fit": "eligible by manual/evidence check",
            }
        )

    for rank, strategy in enumerate(unique, start=1):
        strategy["rank"] = rank
    return validate_strategy_options({"ranked_strategies": unique})


def review_consistency(review_payload: dict, settings: Settings) -> dict:
    if settings.use_mock_llm:
        return validate_review({
            "consistency_status": "pass",
            "issues": [],
            "recommendations": [
                "Keep mock review available until real image generation and real graph writes are enabled."
            ],
        })

    return validate_review(generate_json(settings, review_prompt(review_payload)))

