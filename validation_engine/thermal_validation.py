from __future__ import annotations

from diagnosis_engine.formulas import calculate_final_risk_score, classify_risk, clamp

from .benchmarks import (
    BENCHMARK_SOURCES,
    evaluate_nocturnal_recovery,
    evaluate_envelope_score,
    evaluate_overheating_reduction,
    evaluate_peak_operative_temperature,
    evaluate_risk_score,
    evaluate_ventilation_deficit,
    evaluate_wbgt,
    overall_status,
)
from .confidence_gate import build_confidence_gate
from .combo_effects import THERMAL_COMBO_METHOD
from .retrofit_effects import infer_effect_profile


def _weighted_score(scores: dict, weights: dict) -> float:
    return clamp(sum(float(scores[key]) * float(weights[key]) for key in weights))


def _baseline_indicators(diagnosis_result: dict) -> dict:
    details = diagnosis_result.get("calculation_details", {})
    room = diagnosis_result.get("room_diagnosis", {})
    return {
        "peak_indoor_operative_temperature_c": room.get(
            "T_op_peak_C", details.get("operative_temperature", {}).get("t_op_peak_c")
        ),
        "wbgt_peak_c": room.get("WBGT_peak_C", details.get("wbgt", {}).get("wbgt_peak_c")),
        "overheating_hours": details.get("overheating_hours", {}).get(
            "weighted_hours", room.get("health_risk_hours")
        ),
        "nocturnal_recovery_score": diagnosis_result.get("component_scores", {}).get("nocturnal_recovery"),
        "estimated_indoor_3am_temp_c": details.get("nocturnal_recovery", {}).get("estimated_indoor_3am_temp_c"),
        "composite_room_risk_score": diagnosis_result.get("composite_room_risk_score"),
        "final_score": diagnosis_result.get("composite_risk_score_with_urban_context"),
        "risk_level": diagnosis_result.get("risk_level"),
    }


def _proposed_indicators(diagnosis_result: dict, effect_profile: dict) -> dict:
    baseline = _baseline_indicators(diagnosis_result)
    baseline_scores = diagnosis_result.get("component_scores", {})
    proposed_scores = {
        "solar_gain": clamp(
            baseline_scores.get("solar_gain", 0.0) * effect_profile["solar_gain_multiplier"]
        ),
        "ventilation_deficit": clamp(
            baseline_scores.get("ventilation_deficit", 0.0)
            * effect_profile["ventilation_deficit_multiplier"]
        ),
        "envelope": clamp(
            baseline_scores.get("envelope", 0.0) * effect_profile["envelope_score_multiplier"]
        ),
        "nocturnal_recovery": clamp(
            baseline_scores.get("nocturnal_recovery", 0.0)
            * effect_profile["nocturnal_recovery_multiplier"]
        ),
        "occupant_vulnerability": baseline_scores.get("occupant_vulnerability", 0.0),
    }
    weights = diagnosis_result.get("weights", {})
    room_score = _weighted_score(proposed_scores, weights)
    final_score = calculate_final_risk_score(
        room_score,
        urban_context_modifier=diagnosis_result.get("urban_modifier", 1.0),
        vulnerability_modifier=diagnosis_result.get("vulnerability_modifier", 1.0),
        nighttime_recovery_factor=proposed_scores["nocturnal_recovery"],
    )

    proposed_3am = max(
        0.0,
        float(baseline.get("estimated_indoor_3am_temp_c") or 0.0)
        - (1.0 - effect_profile["nocturnal_recovery_multiplier"]) * 5.0,
    )
    proposed = {
        "peak_indoor_operative_temperature_c": round(
            max(
                0.0,
                float(baseline.get("peak_indoor_operative_temperature_c") or 0.0)
                - effect_profile["operative_temp_reduction_c"],
            ),
            3,
        ),
        "wbgt_peak_c": round(
            max(0.0, float(baseline.get("wbgt_peak_c") or 0.0) - effect_profile["wbgt_reduction_c"]),
            3,
        ),
        "overheating_hours": round(
            max(0.0, float(baseline.get("overheating_hours") or 0.0) * effect_profile["overheating_hours_multiplier"]),
            3,
        ),
        "nocturnal_recovery_score": round(proposed_scores["nocturnal_recovery"], 3),
        "estimated_indoor_3am_temp_c": round(proposed_3am, 3),
        "component_scores": {key: round(value, 3) for key, value in proposed_scores.items()},
        "composite_room_risk_score": round(room_score, 3),
        "final_score": round(final_score, 3),
        "risk_level": classify_risk(final_score),
    }
    return proposed


def _improvements(baseline: dict, proposed: dict) -> dict:
    baseline_hours = float(baseline.get("overheating_hours") or 0.0)
    proposed_hours = float(proposed.get("overheating_hours") or 0.0)
    baseline_final = float(baseline.get("final_score") or 0.0)
    proposed_final = float(proposed.get("final_score") or 0.0)
    return {
        "operative_temperature_reduction_c": round(
            float(baseline.get("peak_indoor_operative_temperature_c") or 0.0)
            - float(proposed.get("peak_indoor_operative_temperature_c") or 0.0),
            3,
        ),
        "wbgt_reduction_c": round(
            float(baseline.get("wbgt_peak_c") or 0.0) - float(proposed.get("wbgt_peak_c") or 0.0),
            3,
        ),
        "overheating_hours_reduction_pct": round(
            ((baseline_hours - proposed_hours) / baseline_hours * 100.0) if baseline_hours else 0.0,
            3,
        ),
        "risk_score_reduction_pct": round(
            ((baseline_final - proposed_final) / baseline_final * 100.0) if baseline_final else 0.0,
            3,
        ),
    }


def _numerical_comparison(baseline: dict, proposed: dict, improvements: dict) -> list[dict]:
    rows = [
        (
            "Peak Indoor Operative Temperature",
            "C",
            baseline.get("peak_indoor_operative_temperature_c"),
            proposed.get("peak_indoor_operative_temperature_c"),
            improvements.get("operative_temperature_reduction_c"),
        ),
        (
            "Heat Stress WBGT",
            "C-WBGT",
            baseline.get("wbgt_peak_c"),
            proposed.get("wbgt_peak_c"),
            improvements.get("wbgt_reduction_c"),
        ),
        (
            "Overheating Hours",
            "weighted hours",
            baseline.get("overheating_hours"),
            proposed.get("overheating_hours"),
            f"{improvements.get('overheating_hours_reduction_pct')}%",
        ),
        (
            "Nocturnal Recovery Score",
            "0-1 risk",
            baseline.get("nocturnal_recovery_score"),
            proposed.get("nocturnal_recovery_score"),
            None,
        ),
        (
            "Composite Room Risk Score",
            "0-1 risk",
            baseline.get("composite_room_risk_score"),
            proposed.get("composite_room_risk_score"),
            None,
        ),
        (
            "Final Risk Score",
            "0-1 risk",
            baseline.get("final_score"),
            proposed.get("final_score"),
            f"{improvements.get('risk_score_reduction_pct')}%",
        ),
    ]
    comparison = []
    for label, unit, base, prop, delta in rows:
        comparison.append(
            {
                "indicator": label,
                "unit": unit,
                "baseline": base,
                "proposed": prop,
                "change": delta if delta is not None else round(float(base or 0) - float(prop or 0), 3),
            }
        )
    return comparison


def _benchmark_result(baseline: dict, proposed: dict, diagnosis_result: dict) -> dict:
    age_group = (
        diagnosis_result.get("calculation_details", {})
        .get("nocturnal_recovery", {})
        .get("age_group", "adult")
    )
    checks = {
        "thermal_comfort": evaluate_peak_operative_temperature(
            float(proposed.get("peak_indoor_operative_temperature_c") or 0.0)
        ),
        "heat_stress": evaluate_wbgt(float(proposed.get("wbgt_peak_c") or 0.0)),
        "night_recovery": evaluate_nocturnal_recovery(
            float(proposed.get("estimated_indoor_3am_temp_c") or 0.0), age_group
        ),
        "overheating_hours": evaluate_overheating_reduction(
            float(baseline.get("overheating_hours") or 0.0),
            float(proposed.get("overheating_hours") or 0.0),
        ),
        "envelope": evaluate_envelope_score(
            float(proposed.get("component_scores", {}).get("envelope", 0.0))
        ),
        "ventilation": evaluate_ventilation_deficit(
            float(proposed.get("component_scores", {}).get("ventilation_deficit", 0.0))
        ),
        "risk_reduction": evaluate_risk_score(float(proposed.get("final_score") or 0.0)),
    }
    return {
        "overall": overall_status(checks),
        "checks": checks,
        "benchmark_sources": BENCHMARK_SOURCES,
    }


def _recommendation(benchmark_result: dict, confidence: dict) -> str:
    overall = benchmark_result["overall"]
    if overall == "pass" and confidence["level"] in {"medium", "high"}:
        return "Proceed to checkpoint review; the selected retrofit passes the screening benchmark."
    if overall == "partial_pass":
        return "Proceed only as a partial improvement; consider combining with ventilation or external shading measures."
    return "Do not treat the selected retrofit as sufficient; choose a stronger or combined strategy before final approval."


def _expected_retrofit_impact(strategy: dict, effect_profile: dict, improvements: dict, benchmark_result: dict) -> dict:
    strategy_name = strategy.get("strategy_name", "this retrofit option")
    solar_reduction_pct = round((1.0 - float(effect_profile["solar_gain_multiplier"])) * 100.0, 1)
    overheating_reduction_pct = improvements.get("overheating_hours_reduction_pct")
    return {
        "plain_language_summary": (
            f"{strategy_name} is expected to reduce the relevant heat driver, but the benchmark result "
            f"is {benchmark_result['overall']} based on the current screening calculation."
        ),
        "estimated_changes": [
            {
                "indicator": "Solar heat through windows",
                "change": f"about {solar_reduction_pct}% lower",
            },
            {
                "indicator": "Peak indoor operative temperature",
                "change": f"about {improvements.get('operative_temperature_reduction_c')} C lower",
            },
            {
                "indicator": "Heat-stress WBGT",
                "change": f"about {improvements.get('wbgt_reduction_c')} C-WBGT lower",
            },
            {
                "indicator": "Overheating hours",
                "change": f"about {overheating_reduction_pct}% lower",
            },
        ],
        "important_note": (
            "These are estimated improvements from the retrofit type. They should be reviewed by the user "
            "and replaced with product data or simulation results when available."
        ),
    }


def _validation_for_strategy(
    diagnosis_result: dict,
    problem_map: dict,
    strategy: dict,
    spatial_index: dict,
) -> dict:
    effect_profile = infer_effect_profile(strategy)
    baseline = _baseline_indicators(diagnosis_result)
    proposed = _proposed_indicators(diagnosis_result, effect_profile)
    improvements = _improvements(baseline, proposed)
    numerical_comparison = _numerical_comparison(baseline, proposed, improvements)
    benchmark_result = _benchmark_result(baseline, proposed, diagnosis_result)
    confidence = build_confidence_gate(effect_profile, diagnosis_result, spatial_index)
    return {
        "strategy": strategy,
        "effect_profile": effect_profile,
        "expected_retrofit_impact": _expected_retrofit_impact(
            strategy, effect_profile, improvements, benchmark_result
        ),
        "effect_assumption_use": {
            "used_for_computation": True,
            "shown_to_user": True,
            "combo_method": THERMAL_COMBO_METHOD,
            "description": (
                "Retrofit effect assumptions are the rule-based multipliers/reductions used to estimate "
                "post-retrofit indicators. They are also exposed for user and reviewer validation before checkpoint approval."
            ),
        },
        "problem_targets": {
            problem["id"]: problem.get("spatial_targets", [])
            for problem in problem_map.get("problems", [])
        },
        "baseline": baseline,
        "proposed": proposed,
        "numerical_comparison": numerical_comparison,
        "improvements": improvements,
        "benchmark_result": benchmark_result,
        "confidence": confidence,
        "recommendation": _recommendation(benchmark_result, confidence),
    }


def _option_sort_key(option: dict) -> tuple[int, float, float, float, int]:
    status_rank = {"pass": 0, "partial_pass": 1, "fail": 2}
    overall = option["benchmark_result"]["overall"]
    final_score = float(option["proposed"].get("final_score", 1.0))
    room_score = float(option["proposed"].get("composite_room_risk_score", 1.0))
    confidence_score = float(option["confidence"].get("score", 0.0))
    rank = int(option["strategy"].get("rank", 999))
    return (status_rank.get(overall, 3), final_score, room_score, -confidence_score, rank)


def validate_retrofit_options(
    diagnosis_result: dict,
    problem_map: dict,
    strategy_options: dict,
    spatial_index: dict,
) -> dict:
    baseline = _baseline_indicators(diagnosis_result)
    seen = set()
    validated_options = []
    for strategy in strategy_options.get("ranked_strategies", []):
        strategy_id = strategy.get("strategy_id")
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        validated_options.append(_validation_for_strategy(diagnosis_result, problem_map, strategy, spatial_index))

    validated_options = sorted(validated_options, key=_option_sort_key)
    for rank, option in enumerate(validated_options, start=1):
        option["validation_rank"] = rank

    recommended = validated_options[0] if validated_options else None
    return {
        "case_id": diagnosis_result.get("case_id"),
        "room_id": diagnosis_result.get("room_id"),
        "baseline": baseline,
        "validated_options": validated_options,
        "recommended_option_id": recommended["strategy"].get("strategy_id") if recommended else None,
        "recommended_option_name": recommended["strategy"].get("strategy_name") if recommended else None,
        "checkpoint_guidance": {
            "question": "Which option should be carried forward, or should the user revise the retrofit intent?",
            "allowed_actions": [
                "choose_option",
                "combine_options",
                "revise_intent",
                "rerun_strategy_ranking",
                "accept_partial_pass",
                "stop",
            ],
        },
    }


def validate_retrofit(
    diagnosis_result: dict,
    problem_map: dict,
    user_selection: dict,
    spatial_index: dict,
) -> dict:
    selected_strategy = user_selection.get("selected_strategy", {})
    validation = _validation_for_strategy(diagnosis_result, problem_map, selected_strategy, spatial_index)
    return {
        "case_id": diagnosis_result.get("case_id"),
        "room_id": diagnosis_result.get("room_id"),
        "selected_strategy": selected_strategy,
        "responds_to_problem_ids": user_selection.get("responds_to_problem_ids", []),
        **validation,
    }



