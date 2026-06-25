from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = ROOT / "data" / "intermediate" / "retrofit_generation_scenarios.json"
OUTPUT_PATH = ROOT / "data" / "intermediate" / "phase3_strategy_packages.json"

BASELINE = {
    "peak_indoor_operative_temperature_c": 33.014,
    "wbgt_peak_c": 26.936,
    "overheating_hours": 698.0,
    "estimated_indoor_3am_temp_c": 26.485,
    "composite_room_risk_score": 0.671,
    "final_score": 1.0,
}

STATUS_SCORE = {"pass": 3.0, "partial_pass": 1.5, "fail": 0.0}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _proposed_values(effect: dict[str, Any]) -> dict[str, float]:
    proposed_temp = BASELINE["peak_indoor_operative_temperature_c"] - _float(effect.get("operative_temp_reduction_c"))
    proposed_wbgt = BASELINE["wbgt_peak_c"] - _float(effect.get("wbgt_reduction_c"))
    proposed_hours = BASELINE["overheating_hours"] * _float(effect.get("overheating_hours_multiplier"), 1.0)
    proposed_night = BASELINE["estimated_indoor_3am_temp_c"] - _float(effect.get("operative_temp_reduction_c")) * 0.55
    proposed_risk = max(
        0.15,
        BASELINE["final_score"]
        * (
            _float(effect.get("overheating_hours_multiplier"), 1.0)
            + _float(effect.get("nocturnal_recovery_multiplier"), 1.0)
            + _float(effect.get("envelope_score_multiplier"), 1.0)
        )
        / 3,
    )
    return {
        "peak_operative_temperature": proposed_temp,
        "wbgt_heat_stress": proposed_wbgt,
        "overheating_hours": proposed_hours,
        "night_recovery_temperature": proposed_night,
        "composite_room_risk_score": proposed_risk,
    }


def _gate_status(value: float, pass_threshold: float, partial_threshold: float) -> str:
    if value <= pass_threshold:
        return "pass"
    if value <= partial_threshold:
        return "partial_pass"
    return "fail"


def _benchmark_gates(effect: dict[str, Any]) -> dict[str, dict[str, Any]]:
    proposed = _proposed_values(effect)
    baseline_hours = BASELINE["overheating_hours"]
    hours_reduction_pct = 0.0
    if baseline_hours > 0:
        hours_reduction_pct = (baseline_hours - proposed["overheating_hours"]) / baseline_hours * 100.0
    if proposed["overheating_hours"] <= 32 or hours_reduction_pct >= 50:
        overheating_status = "pass"
    elif hours_reduction_pct >= 25:
        overheating_status = "partial_pass"
    else:
        overheating_status = "fail"
    return {
        "peak_operative_temperature": {
            "value": round(proposed["peak_operative_temperature"], 3),
            "unit": "C",
            "status": _gate_status(proposed["peak_operative_temperature"], 28.0, 30.0),
            "partial_threshold": "<= 30 C",
        },
        "wbgt_heat_stress": {
            "value": round(proposed["wbgt_heat_stress"], 3),
            "unit": "C-WBGT",
            "status": _gate_status(proposed["wbgt_heat_stress"], 26.0, 28.0),
            "partial_threshold": "<= 28 C-WBGT",
        },
        "overheating_hours": {
            "value": round(proposed["overheating_hours"], 3),
            "unit": "h",
            "reduction_pct": round(hours_reduction_pct, 3),
            "status": overheating_status,
            "partial_threshold": ">= 25% reduction",
        },
        "night_recovery_temperature": {
            "value": round(proposed["night_recovery_temperature"], 3),
            "unit": "C",
            "status": _gate_status(proposed["night_recovery_temperature"], 25.0, 27.0),
            "partial_threshold": "<= 27 C for vulnerable resident screening",
        },
        "composite_room_risk_score": {
            "value": round(proposed["composite_room_risk_score"], 3),
            "status": _gate_status(proposed["composite_room_risk_score"], 0.4, 0.65),
            "partial_threshold": "< 0.65",
        },
    }


def _status(effect: dict[str, Any]) -> str:
    statuses = [gate["status"] for gate in _benchmark_gates(effect).values()]
    if all(status == "pass" for status in statuses):
        return "pass"
    if any(status == "pass" for status in statuses) or any(status == "partial_pass" for status in statuses):
        return "partial_pass"
    return "fail"


def _failed_gate_count(effect: dict[str, Any]) -> int:
    return sum(1 for gate in _benchmark_gates(effect).values() if gate["status"] == "fail")
def _comparison(effect: dict[str, Any]) -> list[dict[str, Any]]:
    temp_after = BASELINE["peak_indoor_operative_temperature_c"] - _float(effect.get("operative_temp_reduction_c"))
    wbgt_after = BASELINE["wbgt_peak_c"] - _float(effect.get("wbgt_reduction_c"))
    hours_after = BASELINE["overheating_hours"] * _float(effect.get("overheating_hours_multiplier"), 1.0)
    night_after = BASELINE["estimated_indoor_3am_temp_c"] - _float(effect.get("operative_temp_reduction_c")) * 0.55
    return [
        {"indicator": "peak operative temperature", "before": round(BASELINE["peak_indoor_operative_temperature_c"], 3), "after": round(temp_after, 3), "unit": "C"},
        {"indicator": "WBGT heat stress", "before": round(BASELINE["wbgt_peak_c"], 3), "after": round(wbgt_after, 3), "unit": "C"},
        {"indicator": "overheating hours", "before": round(BASELINE["overheating_hours"], 3), "after": round(hours_after, 3), "unit": "h"},
        {"indicator": "night recovery temperature", "before": round(BASELINE["estimated_indoor_3am_temp_c"], 3), "after": round(night_after, 3), "unit": "C"},
    ]


def _has_balanced_biophilic_anchors(visual: dict[str, Any]) -> bool:
    placement = visual.get("placement_logic", {})
    return bool(placement.get("left_side")) and bool(placement.get("right_side"))


def _score_scenario(scenario: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    effect = scenario.get("combined_effect_profile", {})
    visual = scenario.get("visual_generation", {})
    status = _status(effect)
    temp_reduction = min(5.0, _float(effect.get("operative_temp_reduction_c"))) / 5.0
    hours_reduction = 1.0 - _float(effect.get("overheating_hours_multiplier"), 1.0)
    priority = _float(scenario.get("priority_score"))
    confidence = _float(effect.get("confidence_score"), 0.25)
    component_count = len(visual.get("component_ids", []))
    visual_score = min(component_count / 6.0, 1.0)
    balance_bonus = 0.15 if _has_balanced_biophilic_anchors(visual) else 0.0
    benchmark_penalty = 1.25 if str(scenario.get("scenario_id", "")).startswith("benchmark_") else 0.0
    failed_gate_penalty = _failed_gate_count(effect) * 2.0
    score = (
        STATUS_SCORE[status]
        + priority * 1.8
        + temp_reduction * 1.4
        + max(0.0, hours_reduction) * 1.1
        + confidence * 0.9
        + visual_score * 0.45
        + balance_bonus
        - benchmark_penalty
        - failed_gate_penalty
    )
    details = {
        "benchmark_status_score": STATUS_SCORE[status],
        "diagnosis_priority_score": round(priority, 3),
        "temperature_reduction_score": round(temp_reduction, 3),
        "overheating_reduction_score": round(max(0.0, hours_reduction), 3),
        "confidence_score": round(confidence, 3),
        "visual_feasibility_score": round(visual_score + balance_bonus, 3),
        "benchmark_test_penalty": benchmark_penalty,
        "failed_benchmark_gate_penalty": failed_gate_penalty,
        "failed_benchmark_gate_count": _failed_gate_count(effect),
        "benchmark_gates": _benchmark_gates(effect),
        "total_score": round(score, 3),
    }
    return score, details


def _package_name(scenario: dict[str, Any]) -> str:
    name = str(scenario.get("scenario_name") or "Retrofit package").replace("Benchmark test: ", "")
    return name[:1].upper() + name[1:]


def _package_from_scenario(scenario: dict[str, Any], rank: int, score_details: dict[str, Any]) -> dict[str, Any]:
    effect = scenario.get("combined_effect_profile", {})
    status = _status(effect)
    package_id = f"top_package_{rank}_{scenario.get('scenario_id', f'scenario_{rank}')}"
    return {
        "package_id": package_id,
        "package_name": _package_name(scenario),
        "user_label": f"ranked option {rank} for this room diagnosis",
        "source_scenario_id": scenario.get("scenario_id"),
        "selection_method": "dynamic_rule_based_optimizer_v1",
        "optimizer_score": score_details,
        "target": {
            "room_id": scenario.get("room_id", "ROOM_001"),
            "target_wall_policy": "diagnosis_target_wall_or_main_window_wall",
            "target_opening_policy": "largest_confirmed_window_or_glass_door",
        },
        "selected_strategy_ids": scenario.get("selected_strategy_ids", []),
        "selected_strategy_names": scenario.get("selected_strategy_names", []),
        "visual_generation": scenario.get("visual_generation", {}),
        "combined_effect_profile": effect,
        "before_after": _comparison(effect),
        "benchmark_status": status,
        "benchmark_gates": _benchmark_gates(effect),
        "confidence_level": "screening",
        "relationship_links": {
            "package_to_strategy": scenario.get("selected_strategy_ids", []),
            "package_to_component": scenario.get("visual_generation", {}).get("component_ids", []),
            "component_to_location": scenario.get("visual_generation", {}).get("placement_logic", {}),
            "package_to_benchmark": status,
            "package_to_source_scenario": scenario.get("scenario_id"),
        },
    }


def build_packages() -> dict[str, Any]:
    scenarios_payload = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    scenarios = list(scenarios_payload.get("generated_scenarios", []))
    scored = []
    for scenario in scenarios:
        score, details = _score_scenario(scenario)
        scored.append((score, details, scenario))
    scored.sort(key=lambda item: item[0], reverse=True)
    no_failed_gate = [item for item in scored if item[1].get("failed_benchmark_gate_count", 0) == 0]
    fallback = [item for item in scored if item[1].get("failed_benchmark_gate_count", 0) != 0]
    ranked_pool = no_failed_gate + fallback

    selected = []
    seen_signatures: set[tuple[str, ...]] = set()
    for _, details, scenario in ranked_pool:
        signature = tuple(sorted(scenario.get("selected_strategy_ids", [])))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        selected.append((details, scenario))
        if len(selected) == 3:
            break

    packages = [_package_from_scenario(scenario, index, details) for index, (details, scenario) in enumerate(selected, start=1)]
    return {
        "case_id": scenarios_payload.get("case_id", "CASE_001"),
        "room_id": scenarios_payload.get("room_id", "ROOM_001"),
        "purpose": "Dynamic top-three Phase 3 retrofit packages for UI, 3D preview, validation, and report output.",
        "selection_method": {
            "method_id": "dynamic_rule_based_optimizer_v1",
            "description": "Ranks generated conditional scenarios by benchmark status, diagnosis priority, estimated thermal improvement, confidence, visual feasibility, and penalties for benchmark-only test scenarios.",
            "not_claimed_as": "final multi-objective optimisation or dynamic thermal simulation",
        },
        "package_count": len(packages),
        "packages": packages,
        "candidate_count": len(scored),
        "optimizer_guardrail": "Top packages prefer candidates with zero failed individual benchmark gates before considering weaker fallback candidates.",
    }


def main() -> None:
    payload = build_packages()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    for index, package in enumerate(payload["packages"], start=1):
        print(
            f"{index}. {package['package_name']} | {package['benchmark_status']} | "
            f"score={package['optimizer_score']['total_score']} | "
            f"{', '.join(package['visual_generation'].get('component_ids', []))}"
        )


if __name__ == "__main__":
    main()
