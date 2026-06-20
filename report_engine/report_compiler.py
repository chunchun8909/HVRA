from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP



def _display_value(value) -> str:
    if isinstance(value, bool) or value is None:
        return "not available" if value is None else ("yes" if value else "no")
    text = str(value)
    suffix = "%" if text.endswith("%") else ""
    number_text = text[:-1] if suffix else text
    try:
        number = Decimal(number_text)
    except Exception:
        return text
    if number == 0:
        return f"0{suffix}"
    exponent = Decimal("1e{}".format(number.adjusted() - 2))
    rounded = number.quantize(exponent, rounding=ROUND_HALF_UP)
    formatted = format(rounded.normalize(), "f")
    return f"{formatted}{suffix}"

def _sentences(text: str) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return []
    parts = []
    start = 0
    for index, char in enumerate(normalized):
        if char in ".!?":
            sentence = normalized[start : index + 1].strip()
            if sentence:
                parts.append(sentence)
            start = index + 1
    tail = normalized[start:].strip()
    if tail:
        parts.append(tail if tail.endswith(('.', '!', '?')) else f"{tail}.")
    return parts


def _target_wall_labels(option: dict) -> str:
    wall_ids = []
    for targets in option.get("problem_targets", {}).values():
        for target in targets:
            wall_id = target.get("wall_id")
            if wall_id and wall_id not in wall_ids:
                wall_ids.append(wall_id)
    labels = []
    for wall_id in wall_ids:
        try:
            labels.append("W" + str(int(wall_id.rsplit("_", 1)[1]) + 1).zfill(2))
        except (ValueError, IndexError):
            labels.append(wall_id)
    return ", ".join(labels) or "room-wide"


def _comparison_lookup(option: dict, indicator: str) -> dict:
    for item in option.get("numerical_comparison", []):
        if indicator.lower() in str(item.get("indicator", "")).lower():
            return item
    return {}


def _build_summary(payload: dict) -> str:
    base_summary = payload["problem_map"].get("summary", "")
    diagnosis = payload["diagnosis_result"]
    validation_options = payload.get("retrofit_validation_options", {}).get("validated_options", [])
    selected_id = payload["user_selection"].get("selected_strategy", {}).get("strategy_id")
    selected_option = next(
        (option for option in validation_options if option.get("strategy", {}).get("strategy_id") == selected_id),
        validation_options[0] if validation_options else {},
    )
    strategy = selected_option.get("strategy", payload["user_selection"].get("selected_strategy", {}))
    benchmark = selected_option.get("benchmark_result", {})
    confidence = selected_option.get("confidence", {})
    temp = _comparison_lookup(selected_option, "Operative Temperature")
    overheating = _comparison_lookup(selected_option, "Overheating Hours")
    walls = _target_wall_labels(selected_option)

    sentences = _sentences(base_summary)
    sentences.append(
        f"The baseline diagnosis classifies this room as {str(diagnosis.get('risk_level', 'unknown')).replace('_', ' ')} with a composite room risk score of {_display_value(diagnosis.get('composite_room_risk_score'))}.")
    if strategy:
        sentences.append(
            f"The currently selected option is {strategy.get('strategy_name', 'the selected retrofit')}, mapped to {walls} in the room view.")
    if temp or overheating:
        temp_text = f"peak operative temperature changes from {_display_value(temp.get('baseline'))} to {_display_value(temp.get('proposed'))} C" if temp else "peak temperature change is pending"
        heat_text = f"overheating hours change from {_display_value(overheating.get('baseline'))} to {_display_value(overheating.get('proposed'))}" if overheating else "overheating-hour change is pending"
        sentences.append(f"The screening comparison estimates that {temp_text}, while {heat_text}.")
    sentences.append(
        f"The benchmark result is {str(benchmark.get('overall', 'pending')).replace('_', ' ')} with {confidence.get('level', 'pending')} confidence, so the user should review whether the option is acceptable or ask the LLM agent to revise or combine strategies.")

    deduped = []
    for sentence in sentences:
        if sentence and sentence not in deduped:
            deduped.append(sentence)
    return " ".join(deduped[:5])


def compile_report(payload: dict) -> dict:
    return {
        "case_id": payload["interpreted_case"]["case_id"],
        "risk_level": payload["diagnosis_result"]["risk_level"],
        "composite_room_risk_score": payload["diagnosis_result"]["composite_room_risk_score"],
        "selected_strategy": payload["user_selection"]["selected_strategy"],
        "summary": _build_summary(payload),
        "details": payload,
    }








