from __future__ import annotations

import json


SYSTEM_RULES = """You are the HVRA local LLM coordination layer.
Return one valid JSON object only. Do not wrap it in markdown.
Do not invent diagnostic numbers; deterministic engines calculate scores.
Use only the provided case, building, constraints, problem map, and manual evidence.
Prefer short strings and arrays. Do not include comments."""


def case_interpretation_prompt(user_case: dict, building_info: dict, constraints: dict) -> str:
    return "\n\n".join(
        [
            SYSTEM_RULES,
            "Task: interpret the heat-vulnerability retrofit case and select a diagnosis profile.",
            "Allowed diagnosis profiles: elderly_heat_risk, renter_low_budget, default.",
            f"user_case={json.dumps(user_case)}",
            f"building_info={json.dumps(building_info)}",
            f"constraints={json.dumps(constraints)}",
            """Return exactly this shape:
{
  "case_id": "string",
  "scenario": "string",
  "diagnosis_profile": "elderly_heat_risk | renter_low_budget | default",
  "priorities": {},
  "notes": ["string"]
}""",
        ]
    )


def strategy_ranking_prompt(problem_map: dict, manual_check: dict, constraints: dict) -> str:
    return "\n\n".join(
        [
            SYSTEM_RULES,
            "Task: rank suitable retrofit strategies using manual evidence, constraints, and the suggested actions in the problem map.",
            f"problem_map={json.dumps(problem_map)}",
            f"manual_check={json.dumps(manual_check)}",
            f"constraints={json.dumps(constraints)}",
            """Return exactly this shape:
{
  "ranked_strategies": [
    {
      "strategy_id": "string",
      "strategy_name": "string",
      "rank": 1,
      "rationale": "string",
      "constraints_fit": "string"
    }
  ]
}
Rank only strategies listed as eligible in manual_check. Prefer strategies listed in problem_map.suggested_strategy_ids or problem.suggested_actions[].candidate_strategy_ids when they are eligible. Rationale must explain which mapped problem and target surface the strategy responds to.""",
        ]
    )


def review_prompt(payload: dict) -> str:
    return "\n\n".join(
        [
            SYSTEM_RULES,
            "Task: review consistency between the problem map, selected strategy, Gemini result, and report.",
            f"payload={json.dumps(payload)}",
            """Return exactly this shape:
{
  "consistency_status": "pass | warning | fail",
  "issues": ["string"],
  "recommendations": ["string"]
}""",
        ]
    )

