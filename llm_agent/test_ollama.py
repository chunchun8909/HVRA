from __future__ import annotations

import argparse
import json
import sys

from utils.config import load_settings
from .agent import interpret_user_case, rank_retrofit_options, review_consistency
from .ollama_client import check_model_available


def _sample_payloads() -> tuple[dict, dict, dict, dict, dict]:
    user_case = {
        "case_id": "OLLAMA_TEST_CASE",
        "vulnerability_type": "elderly_heat_risk",
        "user_intention": "Reduce bedroom overheating at night with low-cost reversible measures.",
        "occupant_profile": {"age_group": "75_plus", "has_ac": False},
        "priority": {"main_goal": "reduce_night_heat_risk", "secondary_goal": "low_cost"},
    }
    building_info = {
        "building_id": "TEST_BLD",
        "room_id": "TEST_ROOM",
        "room_type": "bedroom",
        "facing_direction": "SW",
        "is_top_floor": True,
        "has_external_shading": False,
    }
    constraints = {
        "budget_level": "low",
        "disruption_tolerance": "low",
        "ownership_status": "renter",
        "facade_modification_allowed": False,
        "excluded_strategy_type": ["major_structural_change"],
    }
    problem_map = {
        "room_id": "TEST_ROOM",
        "risk_level": "moderate",
        "problems": [
            {
                "id": "TEST_PROBLEM_SOLAR",
                "problem_type": "excess_solar_gain",
                "primary_cause": "unshaded west-facing glazing",
            }
        ],
    }
    manual_check = {
        "eligible_strategies": [
            {
                "strategy_id": "internal_blinds",
                "strategy_name": "Internal reflective blinds",
                "evidence_snippet": "Internal blinds are low cost and reversible.",
            },
            {
                "strategy_id": "temporary_window_film",
                "strategy_name": "Temporary solar-control window film",
                "evidence_snippet": "Window film can reduce solar transmission.",
            },
        ]
    }
    return user_case, building_info, constraints, problem_map, manual_check


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Test the HVRA Ollama integration.")
    parser.add_argument("--run", action="store_true", help="Run sample interpretation, ranking, and review calls.")
    args = parser.parse_args()

    settings = load_settings()
    status = check_model_available(settings)
    print(json.dumps({"ollama_status": status}, indent=2, ensure_ascii=False))

    if not args.run:
        return

    user_case, building_info, constraints, problem_map, manual_check = _sample_payloads()
    interpreted = interpret_user_case(user_case, building_info, constraints, settings)
    ranked = rank_retrofit_options(problem_map, manual_check, constraints, settings)
    review = review_consistency(
        {"problem_map": problem_map, "user_selection": {"selected_strategy": ranked["ranked_strategies"][0]}},
        settings,
    )

    print(json.dumps(
        {
            "interpreted_case": interpreted,
            "strategy_options": ranked,
            "review": review,
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()

