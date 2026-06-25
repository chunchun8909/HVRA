from __future__ import annotations

import json
from pathlib import Path

from utils.config import INPUT_DIR


def _load_visual_rule(strategy_id: str) -> dict:
    path = INPUT_DIR / "visual_retrofit_catalogue.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return payload.get("strategies", {}).get(strategy_id, {})


def build_visual_prompt(
    interpreted_case: dict,
    problem_map: dict,
    user_selection: dict,
    spatial_index: dict,
) -> dict:
    selected = user_selection["selected_strategy"]
    room = spatial_index["room"]
    visual_rule = _load_visual_rule(selected["strategy_id"])
    prompt = (
        "Create a clear before-and-after retrofit visualization prompt for a heat-vulnerable "
        f"{room.get('room_type', 'room')}. Show the selected intervention: "
        f"{selected['strategy_name']}. Use this placement rule: "
        f"{visual_rule.get('placement_rule', 'attach intervention to the mapped target surface')}. "
        f"Represent it as {visual_rule.get('visual_asset_type', 'a realistic retrofit element')} on "
        f"{visual_rule.get('target_surface_type', selected.get('target_components', []))}. "
        "Keep the output realistic, technically plausible, and consistent with the selected room surfaces."
    )
    return {
        "case_id": interpreted_case["case_id"],
        "room_id": room["id"],
        "selected_strategy_id": selected["strategy_id"],
        "prompt": prompt,
        "visual_rule": visual_rule,
        "problem_summary": problem_map.get("summary", ""),
    }

