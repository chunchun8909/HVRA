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


def _selected_package_and_option(payload: dict) -> tuple[dict, dict]:
    packages = payload.get("phase3_strategy_packages", {}).get("packages", [])
    validation_options = payload.get("retrofit_validation_options", {}).get("validated_options", [])
    selected_id = payload["user_selection"].get("selected_package_id") or payload["user_selection"].get("selected_strategy", {}).get("strategy_id")
    selected_package = next((package for package in packages if package.get("package_id") == selected_id), packages[0] if packages else {})
    selected_option = next(
        (option for option in validation_options if option.get("strategy", {}).get("strategy_id") == selected_id),
        validation_options[0] if validation_options else {},
    )
    return selected_package, selected_option


def _comparison_pair(item: dict) -> tuple[object, object]:
    before = item.get("before", item.get("baseline"))
    after = item.get("after", item.get("proposed"))
    return before, after


def _build_summary(payload: dict) -> str:
    base_summary = payload["problem_map"].get("summary", "")
    diagnosis = payload["diagnosis_result"]
    selected_package, selected_option = _selected_package_and_option(payload)
    strategy = selected_option.get("strategy", payload["user_selection"].get("selected_strategy", {}))
    if selected_package:
        strategy = {"strategy_name": selected_package.get("package_name"), "strategy_id": selected_package.get("package_id")}
    benchmark = selected_option.get("benchmark_result", {})
    confidence = selected_option.get("confidence", {})
    temp = _comparison_lookup(selected_option, "Operative Temperature")
    overheating = _comparison_lookup(selected_option, "Overheating Hours")
    walls = _target_wall_labels(selected_option)
    if selected_package:
        before_after = selected_package.get("before_after", [])
        temp = next((item for item in before_after if "operative" in str(item.get("indicator", "")).lower()), {})
        overheating = next((item for item in before_after if "overheating" in str(item.get("indicator", "")).lower()), {})
        benchmark = {"overall": selected_package.get("benchmark_status")}
        confidence = {"level": selected_package.get("confidence_level")}
        walls = selected_package.get("target_policy", {}).get("target_wall", walls)

    sentences = _sentences(base_summary)
    sentences.append(
        f"The baseline diagnosis classifies this room as {str(diagnosis.get('risk_level', 'unknown')).replace('_', ' ')} with a composite room risk score of {_display_value(diagnosis.get('composite_room_risk_score'))}."
    )
    if strategy:
        sentences.append(
            f"The currently selected option is {strategy.get('strategy_name', 'the selected retrofit')}, mapped to {walls} in the room view."
        )
    if temp or overheating:
        temp_before, temp_after = _comparison_pair(temp)
        heat_before, heat_after = _comparison_pair(overheating)
        unit = temp.get("unit", "C") if temp else "C"
        heat_unit = overheating.get("unit", "") if overheating else ""
        temp_text = f"peak operative temperature changes from {_display_value(temp_before)} to {_display_value(temp_after)} {unit}" if temp else "peak temperature change is pending"
        heat_text = f"overheating hours change from {_display_value(heat_before)} to {_display_value(heat_after)} {heat_unit}" if overheating else "overheating-hour change is pending"
        sentences.append(f"The screening comparison estimates that {temp_text}, while {heat_text}.")
    sentences.append(
        f"The benchmark result is {str(benchmark.get('overall', 'pending')).replace('_', ' ')} with {confidence.get('level', 'pending')} confidence, so the user should review whether the option is acceptable or ask the LLM agent to revise or combine strategies."
    )

    deduped = []
    for sentence in sentences:
        if sentence and sentence not in deduped:
            deduped.append(sentence)
    return " ".join(deduped[:5])



def _curated_report_details(payload: dict, selected_package: dict) -> dict:
    validation = payload.get("retrofit_validation", {})
    packages = payload.get("phase3_strategy_packages", {}).get("packages", [])
    selected_id = selected_package.get("package_id") or payload.get("user_selection", {}).get("selected_package_id")
    preview_src = f"/static-views/spatial/room_3d_component_view.html?strategy_id={selected_id}" if selected_id else "/static-views/spatial/room_3d_component_view.html"
    return {
        "case": payload.get("interpreted_case", {}),
        "diagnosis": {
            "risk_level": payload.get("diagnosis_result", {}).get("risk_level"),
            "composite_room_risk_score": payload.get("diagnosis_result", {}).get("composite_room_risk_score"),
            "component_scores": payload.get("diagnosis_result", {}).get("component_scores", {}),
        },
        "problem_map": {
            "summary": payload.get("problem_map", {}).get("summary"),
            "suggested_action_summary": payload.get("problem_map", {}).get("suggested_action_summary"),
            "problem_count": len(payload.get("problem_map", {}).get("problems", [])),
            "problems": payload.get("problem_map", {}).get("problems", [])[:6],
        },
        "selected_package": selected_package,
        "top_packages": packages[:3],
        "selected_validation": validation,
        "visual_preview": {
            "type": "3d_room_component_preview",
            "src": preview_src,
            "static_screenshot_path": validation.get("visual_preview_screenshot_path"),
            "static_capture_status": "pending" if not validation.get("visual_preview_screenshot_path") else "available",
            "note": "The current report visual uses the selected Phase 3 3D room/component preview. A static screenshot can be captured from this view for export later.",
        },
        "llm_review": payload.get("llm_review", {}),
    }

def compile_report(payload: dict) -> dict:
    selected_package, _ = _selected_package_and_option(payload)
    details = _curated_report_details(payload, selected_package)
    return {
        "case_id": payload["interpreted_case"]["case_id"],
        "risk_level": payload["diagnosis_result"]["risk_level"],
        "composite_room_risk_score": payload["diagnosis_result"].get("composite_room_risk_score"),
        "selected_strategy": payload["user_selection"].get("selected_strategy", {}),
        "selected_package": selected_package,
        "summary": _build_summary(payload),
        "visual_preview": details["visual_preview"],
        "details": details,
    }

