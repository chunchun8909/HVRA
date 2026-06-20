from __future__ import annotations

from diagnosis_engine.formulas import clamp


THERMAL_COMBO_METHOD = {
    "method_id": "heat_balance_taylor_screening_v1",
    "method_name": "First-order heat-balance screening for combined retrofit effects",
    "method_document": "docs/thermal_combo_screening.md",
    "standard_alignment": [
        "ISO 13790 / EN ISO 13790 5R1C heat-balance logic",
        "ISO 52016-1 hourly zone-temperature calculation logic",
        "EnergyPlus heat-balance simulation reference",
    ],
    "not_claimed_as": "official universal additive Delta T formula",
    "valid_use": "screening comparison of retrofit packages before simulation or detailed design",
    "caps": {
        "max_peak_temp_reduction_c": 5.0,
        "max_wbgt_reduction_c": 2.0,
        "max_overheating_hours_reduction_pct": 70.0,
        "min_final_risk_score": 0.15,
        "min_solar_multiplier": 0.25,
        "min_envelope_multiplier": 0.45,
        "min_ventilation_multiplier": 0.35,
        "min_nocturnal_multiplier": 0.35,
    },
}


def combine_effect_profiles(effect_profiles: list[dict]) -> dict:
    """Combine multiple screening profiles with conservative multiplicative driver caps."""
    if not effect_profiles:
        return {}

    caps = THERMAL_COMBO_METHOD["caps"]
    solar = 1.0
    ventilation = 1.0
    envelope = 1.0
    nocturnal = 1.0
    overheating = 1.0
    temp_reductions = []
    wbgt_reductions = []
    confidences = []
    reasons = []
    profile_ids = []

    for profile in effect_profiles:
        solar *= float(profile.get("solar_gain_multiplier", 1.0))
        ventilation *= float(profile.get("ventilation_deficit_multiplier", 1.0))
        envelope *= float(profile.get("envelope_score_multiplier", 1.0))
        nocturnal *= float(profile.get("nocturnal_recovery_multiplier", 1.0))
        overheating *= float(profile.get("overheating_hours_multiplier", 1.0))
        temp_reductions.append(float(profile.get("operative_temp_reduction_c", 0.0)))
        wbgt_reductions.append(float(profile.get("wbgt_reduction_c", 0.0)))
        confidences.append(float(profile.get("confidence_score", 0.0)))
        reasons.extend(profile.get("confidence_reasons", []))
        profile_ids.append(profile.get("effect_profile_id", "unknown"))

    sorted_temp = sorted(temp_reductions, reverse=True)
    sorted_wbgt = sorted(wbgt_reductions, reverse=True)

    def diminishing_sum(values: list[float]) -> float:
        weights = [1.0, 0.60, 0.35, 0.20]
        return sum(value * weights[min(index, len(weights) - 1)] for index, value in enumerate(values))

    extra_strategy_count = max(0, len(effect_profiles) - 1)
    confidence = (sum(confidences) / len(confidences)) - 0.05 * extra_strategy_count if confidences else 0.0

    return {
        "effect_profile_id": "combo_heat_balance_screening",
        "included_effect_profile_ids": profile_ids,
        "combo_method": THERMAL_COMBO_METHOD,
        "solar_gain_multiplier": max(caps["min_solar_multiplier"], solar),
        "ventilation_deficit_multiplier": max(caps["min_ventilation_multiplier"], ventilation),
        "envelope_score_multiplier": max(caps["min_envelope_multiplier"], envelope),
        "nocturnal_recovery_multiplier": max(caps["min_nocturnal_multiplier"], nocturnal),
        "operative_temp_reduction_c": min(caps["max_peak_temp_reduction_c"], diminishing_sum(sorted_temp)),
        "wbgt_reduction_c": min(caps["max_wbgt_reduction_c"], diminishing_sum(sorted_wbgt)),
        "overheating_hours_multiplier": max(1.0 - caps["max_overheating_hours_reduction_pct"] / 100.0, overheating),
        "confidence_score": clamp(confidence),
        "confidence_reasons": [
            "Combined effect estimated with first-order heat-balance screening, not naive additive Delta T.",
            "Driver multipliers are combined multiplicatively with conservative caps.",
            "Temperature reductions use diminishing returns and are capped before checkpoint review.",
            *reasons[:6],
        ],
    }

