from __future__ import annotations


def build_visual_prompt(
    interpreted_case: dict,
    problem_map: dict,
    user_selection: dict,
    spatial_index: dict,
) -> dict:
    selected = user_selection["selected_strategy"]
    room = spatial_index["room"]
    prompt = (
        "Create a clear before-and-after retrofit visualization prompt for a heat-vulnerable "
        f"{room.get('room_type', 'room')}. Show the selected intervention: "
        f"{selected['strategy_name']}. Emphasize reduced solar gain, night comfort, and low-disruption "
        "renter-friendly changes. Keep the output realistic and technically plausible."
    )
    return {
        "case_id": interpreted_case["case_id"],
        "room_id": room["id"],
        "selected_strategy_id": selected["strategy_id"],
        "prompt": prompt,
        "problem_summary": problem_map.get("summary", ""),
    }

