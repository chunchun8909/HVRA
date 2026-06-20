from __future__ import annotations

import math


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def classify_risk(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "moderate"
    return "safe"


def score_from_range(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return clamp((value - low) / (high - low))


def calculate_window_to_wall_ratio(window_area: float, wall_area: float) -> float:
    if wall_area <= 0:
        return 0.0
    return clamp(window_area / wall_area)


def orientation_to_degrees(orientation: str) -> float:
    mapping = {
        "N": 0.0,
        "NE": 45.0,
        "E": 90.0,
        "SE": 135.0,
        "S": 180.0,
        "SW": 225.0,
        "W": 270.0,
        "NW": 315.0,
    }
    return mapping.get(str(orientation).upper(), 225.0)


def smallest_angle_between(a_deg: float, b_deg: float) -> float:
    return abs((a_deg - b_deg + 180.0) % 360.0 - 180.0)


def orientation_solar_factor(orientation: str) -> float:
    factors = {
        "N": 0.25,
        "NE": 0.45,
        "E": 0.65,
        "SE": 0.82,
        "S": 0.90,
        "SW": 0.92,
        "W": 0.88,
        "NW": 0.55,
    }
    return factors.get(str(orientation).upper(), 0.75)


def glazing_shgc(glazing_type: str | None) -> float:
    mapping = {
        "single_glazing": 0.86,
        "double_glazing": 0.70,
        "double_low_e": 0.50,
        "triple_glazing": 0.45,
        "solar_control": 0.35,
    }
    return mapping.get(str(glazing_type or "").lower(), 0.75)


def calculate_solar_gain(
    solar_radiation: float,
    window_area: float,
    shgc: float = 0.86,
    shading_factor: float = 0.0,
) -> float:
    return solar_radiation * window_area * shgc * (1.0 - clamp(shading_factor))


def calculate_solar_gain_score(solar_gain: float, threshold: float = 600.0) -> float:
    if threshold <= 0:
        return 0.0
    return clamp(solar_gain / threshold)


def check_cross_ventilation(
    external_facades: int,
    orientation_angle: float = 0.0,
    min_angle_for_cross_vent: float = 45.0,
) -> bool:
    if external_facades < 2:
        return False
    return orientation_angle >= min_angle_for_cross_vent


def estimate_ach(
    external_facades: int,
    has_openable_windows: bool = True,
    orientation_angle: float = 0.0,
    hvac_system: str = "none",
    wind_speed_m_s: float = 0.0,
) -> float:
    if not has_openable_windows:
        return 0.1
    if hvac_system == "active":
        return 2.0
    wind_boost = min(max(wind_speed_m_s, 0.0) * 0.15, 0.6)
    if hvac_system == "passive":
        return round(1.3 + wind_boost, 3)
    if check_cross_ventilation(external_facades, orientation_angle):
        return round(1.5 + wind_boost, 3)
    if external_facades >= 2:
        return round(0.75 + wind_boost * 0.5, 3)
    return round(0.35 + wind_boost * 0.25, 3)


def calculate_ventilation_deficit(ach: float, target_ach: float = 4.0) -> float:
    if target_ach <= 0:
        return 0.0
    return clamp(1.0 - ach / target_ach)


def calculate_envelope_score(
    construction_era: str,
    wall_u_value: float | None = None,
    roof_u_value: float | None = None,
    roof_exposed: bool = False,
) -> float:
    era_scores = {
        "pre_1960": 0.85,
        "1960_1979": 0.68,
        "1980_2000": 0.48,
        "2000_2010": 0.30,
        "2010_plus": 0.18,
    }
    score = era_scores.get(construction_era, 0.55)
    if wall_u_value is not None and wall_u_value > 1.2:
        score += 0.12
    if roof_u_value is not None and roof_u_value > 1.5:
        score += 0.12
    if roof_exposed:
        score += 0.10
    return clamp(score)


def calculate_operative_temperature(t_air: float, t_mrt: float) -> float:
    return (t_air + t_mrt) / 2.0


def calculate_wet_bulb_temperature(t_dry: float, rh: float) -> float:
    rh_pct = rh if rh > 1 else rh * 100
    rh_pct = max(1.0, min(100.0, rh_pct))
    return (
        t_dry * math.atan(0.151977 * (rh_pct + 8.313659) ** 0.5)
        + math.atan(t_dry + rh_pct)
        - math.atan(rh_pct - 1.676331)
        + 0.00391838 * rh_pct ** 1.5 * math.atan(0.023101 * rh_pct)
        - 4.686035
    )


def calculate_wbgt(t_air: float, rh: float, solar_radiation: float = 0.0) -> float:
    t_wet = calculate_wet_bulb_temperature(t_air, rh)
    if solar_radiation > 100:
        t_mrt = t_air + solar_radiation / 150.0
        return 0.7 * t_wet + 0.2 * t_mrt + 0.1 * t_air
    return 0.7 * t_wet + 0.3 * t_air


def calculate_nocturnal_recovery_score(night_temperature_at_3am: float, age_group: str = "adult") -> float:
    thresholds = {
        "adult": 28.0,
        "65_75": 26.0,
        "elderly_65_75": 26.0,
        "75_plus": 25.0,
        "elderly_75_plus": 25.0,
    }
    threshold = thresholds.get(age_group, 28.0)
    return score_from_range(night_temperature_at_3am, threshold - 2.0, threshold + 2.0)


def calculate_overheating_hours(
    hourly_temperatures: list[float],
    age_group: str = "adult",
    vulnerability_multiplier: float = 1.0,
) -> dict:
    thresholds = {
        "adult": 28.0,
        "65_75": 26.0,
        "elderly_65_75": 26.0,
        "75_plus": 25.0,
        "elderly_75_plus": 25.0,
    }
    threshold = thresholds.get(age_group, 28.0)
    hours_over = sum(1 for temp in hourly_temperatures if temp > threshold)
    total_hours = len(hourly_temperatures)
    percentage = hours_over / total_hours * 100.0 if total_hours else 0.0
    return {
        "threshold_c": threshold,
        "hours_over_threshold": hours_over,
        "total_hours": total_hours,
        "overheating_percentage": round(percentage, 2),
        "weighted_hours": round(hours_over * vulnerability_multiplier, 1),
    }


def vulnerability_score_from_profile(profile: dict) -> float:
    score = 0.25
    if profile.get("age_group") in {"65_75", "65_plus"}:
        score += 0.25
    if profile.get("age_group") == "75_plus":
        score += 0.40
    if profile.get("has_ac") is False:
        score += 0.15
    if profile.get("mobility_level") in {"limited", "low"}:
        score += 0.10
    if profile.get("time_spent_at_home") in {"most_of_day", "all_day"}:
        score += 0.05
    if profile.get("sleep_sensitivity") == "high":
        score += 0.05
    return clamp(score)


def vulnerability_modifier_from_score(score: float) -> float:
    return 1.0 + clamp(score) * 0.35


def calculate_composite_risk_score(
    solar_score: float,
    ventilation_score: float,
    envelope_score: float,
    vulnerability_score: float,
    weights: dict | None = None,
) -> float:
    weights = weights or {
        "solar_gain": 0.40,
        "ventilation_deficit": 0.35,
        "envelope": 0.15,
        "occupant_vulnerability": 0.10,
    }
    return clamp(
        solar_score * weights.get("solar_gain", 0.40)
        + ventilation_score * weights.get("ventilation_deficit", 0.35)
        + envelope_score * weights.get("envelope", 0.15)
        + vulnerability_score * weights.get("occupant_vulnerability", 0.10)
    )


def calculate_final_risk_score(
    composite_score: float,
    urban_context_modifier: float = 1.0,
    vulnerability_modifier: float = 1.0,
    nighttime_recovery_factor: float = 0.0,
) -> float:
    final_score = composite_score * urban_context_modifier * vulnerability_modifier
    if nighttime_recovery_factor > 0.5:
        final_score *= 1.0 + nighttime_recovery_factor * 0.2
    return clamp(final_score)
