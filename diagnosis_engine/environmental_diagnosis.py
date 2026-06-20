from __future__ import annotations

from .formulas import (
    calculate_envelope_score,
    calculate_final_risk_score,
    calculate_nocturnal_recovery_score,
    calculate_operative_temperature,
    calculate_overheating_hours,
    calculate_solar_gain,
    calculate_solar_gain_score,
    calculate_ventilation_deficit,
    calculate_wbgt,
    calculate_window_to_wall_ratio,
    check_cross_ventilation,
    classify_risk,
    clamp,
    estimate_ach,
    glazing_shgc,
    orientation_solar_factor,
    orientation_to_degrees,
    score_from_range,
    smallest_angle_between,
    vulnerability_modifier_from_score,
    vulnerability_score_from_profile,
)
from .weight_profiles import get_profile, get_profile_rationale


def _risk_map_context(context: dict | None) -> tuple[dict, dict, float]:
    if not context:
        return {}, {}, 1.0
    if "climate_context" in context or "composite_urban_modifier" in context:
        urban_metrics = context.get("urban_context", {})
        climate_context = dict(context.get("climate_context", {}))
        infrared_context = context.get("infrared_city_context", {})
        if infrared_context.get("available"):
            climate_context["infrared_city"] = infrared_context.get("climate_updates", {})
            climate_context["infrared_city_source"] = infrared_context.get("source")
        modifier = context.get("composite_urban_modifier", context.get("urban_context_modifier", 1.0))
        return urban_metrics, climate_context, modifier
    return context, context.get("climate_context", {}), context.get("urban_context_modifier", 1.0)


def _window_area(spatial_index: dict, building_info: dict) -> float:
    windows = spatial_index.get("windows", [])
    calculated = sum(float(window.get("estimated_area_m2", 0.0) or 0.0) for window in windows)
    if calculated > 0:
        return calculated
    return float(building_info.get("window_area_m2") or 0.0)


def _wall_area(spatial_index: dict, building_info: dict) -> float:
    walls = spatial_index.get("walls", [])
    calculated = sum(float(wall.get("estimated_area_m2", 0.0) or 0.0) for wall in walls)
    if calculated > 0:
        return calculated
    return float(building_info.get("wall_area_m2") or 1.0)


def _orientation_angle(spatial_index: dict, building_info: dict) -> tuple[float, list[str]]:
    orientations = []
    for wall in spatial_index.get("walls", []):
        if wall.get("is_external"):
            orientations.append(str(wall.get("orientation") or building_info.get("facing_direction", "SW")).upper())
    if not orientations:
        orientations = [str(building_info.get("facing_direction", "SW")).upper()]
    if len(orientations) < 2:
        return 0.0, orientations
    degrees = [orientation_to_degrees(orientation) for orientation in orientations]
    angles = [
        smallest_angle_between(degrees[i], degrees[j])
        for i in range(len(degrees))
        for j in range(i + 1, len(degrees))
    ]
    return max(angles) if angles else 0.0, orientations


def _climate_defaults(climate_context: dict) -> dict:
    infrared_city = climate_context.get("infrared_city", {})
    if climate_context.get("available"):
        peak_temp_record = climate_context.get("peak_temperature_record", {})
        peak_solar_record = climate_context.get("peak_solar_record", {})
        night_record = climate_context.get("night_reference_record", {})
        return {
            "peak_air_temp_c": float(climate_context.get("peak_dry_bulb_c") or peak_temp_record.get("dry_bulb_c") or 32.0),
            "peak_rh_pct": float(peak_temp_record.get("relative_humidity_pct") or climate_context.get("mean_hot_season_relative_humidity_pct") or 55.0),
            "peak_solar_w_m2": float(climate_context.get("peak_global_horizontal_radiation_w_m2") or peak_solar_record.get("global_horizontal_radiation_w_m2") or 700.0),
            "mean_wind_speed_m_s": float(climate_context.get("mean_hot_season_wind_speed_m_s") or 1.0),
            "night_3am_temp_c": float(climate_context.get("night_reference_temperature_3am_c") or night_record.get("dry_bulb_c") or 26.0),
            "hourly_temperatures": [
                float(temp) for temp in climate_context.get("hourly_hot_season_temperatures_c", [])
            ],
            "source": "epw",
        }
    if infrared_city:
        return {
            "peak_air_temp_c": 32.0,
            "peak_rh_pct": 55.0,
            "peak_solar_w_m2": float(infrared_city.get("infrared_city_solar_radiation_max") or 700.0),
            "mean_wind_speed_m_s": float(infrared_city.get("infrared_city_mean_wind_speed_m_s") or 1.0),
            "night_3am_temp_c": 26.0,
            "hourly_temperatures": [],
            "source": "infrared_city_partial",
        }
    return {
        "peak_air_temp_c": 32.0,
        "peak_rh_pct": 55.0,
        "peak_solar_w_m2": 700.0,
        "mean_wind_speed_m_s": 1.0,
        "night_3am_temp_c": 26.0,
        "hourly_temperatures": [],
        "source": "fallback_no_epw",
    }


def _weighted_component_score(component_scores: dict, weights: dict) -> float:
    return clamp(sum(component_scores[key] * weights[key] for key in weights))


def compute_diagnosis(
    interpreted_case: dict,
    building_info: dict,
    spatial_index: dict,
    user_case: dict,
    urban_context: dict | None = None,
) -> dict:
    """
    Compute deterministic room-level heat vulnerability diagnosis.

    The output keeps the original component score keys used downstream while
    adding the full 13-calculation detail payload required by the spec.
    """
    profile_name = interpreted_case.get("diagnosis_profile", "default")
    weights = get_profile(profile_name)
    urban_metrics, climate_context, urban_modifier_raw = _risk_map_context(urban_context)
    climate = _climate_defaults(climate_context)

    room = spatial_index.get("room", {})
    room_area = float(room.get("area_m2") or building_info.get("room_area_m2") or 1.0)
    room_height = float(room.get("height_m") or building_info.get("room_height_m") or 2.7)
    room_volume = room_area * room_height

    window_area = _window_area(spatial_index, building_info)
    wall_area = _wall_area(spatial_index, building_info)
    window_ratio = calculate_window_to_wall_ratio(window_area, wall_area)

    orientation_angle, external_orientations = _orientation_angle(spatial_index, building_info)
    external_facades = max(int(building_info.get("external_facades") or 1), len(external_orientations))
    primary_orientation = external_orientations[0] if external_orientations else building_info.get("facing_direction", "SW")
    solar_radiation = climate["peak_solar_w_m2"] * orientation_solar_factor(primary_orientation)
    if urban_metrics.get("infrared_city_solar_radiation_mean"):
        solar_radiation = max(
            solar_radiation,
            float(urban_metrics.get("infrared_city_solar_radiation_mean") or 0.0),
        )
    shading_factor = 0.70 if building_info.get("has_external_shading") else 0.0
    shgc = glazing_shgc(building_info.get("glazing_type"))
    solar_gain_w = calculate_solar_gain(solar_radiation, window_area, shgc, shading_factor)
    solar_gain_score = calculate_solar_gain_score(solar_gain_w)

    has_openable_windows = bool(window_area > 0 and not building_info.get("fixed_windows", False))
    has_cross_ventilation = check_cross_ventilation(external_facades, orientation_angle)
    ach = estimate_ach(
        external_facades,
        has_openable_windows=has_openable_windows,
        orientation_angle=orientation_angle,
        hvac_system=str(building_info.get("hvac_system", "none")),
        wind_speed_m_s=climate["mean_wind_speed_m_s"],
    )
    ventilation_deficit = calculate_ventilation_deficit(ach)

    envelope_score = calculate_envelope_score(
        str(building_info.get("construction_era", "")),
        wall_u_value=building_info.get("wall_u_value"),
        roof_u_value=building_info.get("roof_u_value"),
        roof_exposed=bool(building_info.get("roof_exposed") or building_info.get("is_top_floor")),
    )

    solar_heat_density = solar_gain_w / max(room_area, 1.0)
    t_mrt_peak = climate["peak_air_temp_c"] + min(8.0, solar_heat_density / 55.0) + envelope_score * 2.0
    operative_temperature_peak = calculate_operative_temperature(climate["peak_air_temp_c"], t_mrt_peak)
    wbgt_peak = calculate_wbgt(climate["peak_air_temp_c"], climate["peak_rh_pct"], solar_radiation)
    age_group = user_case.get("occupant_profile", {}).get("age_group", "adult")
    indoor_night_temp = (
        climate["night_3am_temp_c"]
        + envelope_score * 2.0
        + (1.2 if building_info.get("is_top_floor") else 0.0)
        - min(1.5, ach * 0.35)
    )
    nocturnal_recovery = calculate_nocturnal_recovery_score(indoor_night_temp, age_group)
    vulnerability_score = vulnerability_score_from_profile(user_case.get("occupant_profile", {}))
    overheating = calculate_overheating_hours(
        climate["hourly_temperatures"],
        age_group=age_group,
        vulnerability_multiplier=vulnerability_modifier_from_score(vulnerability_score),
    )

    component_scores = {
        "solar_gain": round(solar_gain_score, 3),
        "ventilation_deficit": round(ventilation_deficit, 3),
        "envelope": round(envelope_score, 3),
        "nocturnal_recovery": round(nocturnal_recovery, 3),
        "occupant_vulnerability": round(vulnerability_score, 3),
    }
    composite = _weighted_component_score(component_scores, weights)
    urban_modifier = clamp(float(urban_modifier_raw or 1.0), minimum=0.8, maximum=2.0)
    vulnerability_modifier = vulnerability_modifier_from_score(vulnerability_score)
    final_score = calculate_final_risk_score(
        composite,
        urban_context_modifier=urban_modifier,
        vulnerability_modifier=vulnerability_modifier,
        nighttime_recovery_factor=nocturnal_recovery,
    )

    calculation_details = {
        "window_to_wall_ratio": {
            "window_area_m2": round(window_area, 3),
            "wall_area_m2": round(wall_area, 3),
            "wwr": round(window_ratio, 3),
        },
        "solar_gain": {
            "source": climate["source"],
            "primary_orientation": primary_orientation,
            "peak_epw_ghi_w_m2": round(climate["peak_solar_w_m2"], 3),
            "orientation_adjusted_radiation_w_m2": round(solar_radiation, 3),
            "shgc": round(shgc, 3),
            "shading_factor": round(shading_factor, 3),
            "solar_gain_w": round(solar_gain_w, 3),
            "score": component_scores["solar_gain"],
        },
        "cross_ventilation": {
            "external_facades": external_facades,
            "external_orientations": external_orientations,
            "orientation_angle_deg": round(orientation_angle, 3),
            "has_cross_ventilation": has_cross_ventilation,
        },
        "ach_estimation": {
            "room_volume_m3": round(room_volume, 3),
            "has_openable_windows": has_openable_windows,
            "mean_epw_wind_speed_m_s": round(climate["mean_wind_speed_m_s"], 3),
            "ach": round(ach, 3),
        },
        "ventilation_deficit": {
            "target_ach": 4.0,
            "score": component_scores["ventilation_deficit"],
        },
        "envelope": {
            "construction_era": building_info.get("construction_era"),
            "roof_exposed": bool(building_info.get("roof_exposed") or building_info.get("is_top_floor")),
            "score": component_scores["envelope"],
        },
        "operative_temperature": {
            "peak_air_temp_c": round(climate["peak_air_temp_c"], 3),
            "estimated_t_mrt_peak_c": round(t_mrt_peak, 3),
            "t_op_peak_c": round(operative_temperature_peak, 3),
            "score": round(score_from_range(operative_temperature_peak, 26.0, 34.0), 3),
        },
        "wbgt": {
            "peak_air_temp_c": round(climate["peak_air_temp_c"], 3),
            "relative_humidity_pct": round(climate["peak_rh_pct"], 3),
            "wbgt_peak_c": round(wbgt_peak, 3),
            "score": round(score_from_range(wbgt_peak, 24.0, 32.0), 3),
        },
        "nocturnal_recovery": {
            "epw_3am_reference_temp_c": round(climate["night_3am_temp_c"], 3),
            "estimated_indoor_3am_temp_c": round(indoor_night_temp, 3),
            "age_group": age_group,
            "score": component_scores["nocturnal_recovery"],
        },
        "overheating_hours": overheating,
        "occupant_vulnerability": {
            "occupant_profile": user_case.get("occupant_profile", {}),
            "score": component_scores["occupant_vulnerability"],
            "vulnerability_modifier": round(vulnerability_modifier, 3),
        },
        "composite_risk_score": {
            "weights": weights,
            "weight_rationale": get_profile_rationale(),
            "room_score": round(composite, 3),
        },
        "final_risk_score": {
            "urban_context_modifier": round(urban_modifier, 3),
            "vulnerability_modifier": round(vulnerability_modifier, 3),
            "nighttime_recovery_factor": round(nocturnal_recovery, 3),
            "final_score": round(final_score, 3),
        },
    }

    return {
        "case_id": interpreted_case["case_id"],
        "room_id": spatial_index["room"]["id"],
        "profile": profile_name,
        "weights": weights,
        "weight_rationale": get_profile_rationale(),
        "component_scores": component_scores,
        "calculation_details": calculation_details,
        "climate_context_source": climate_context.get("source", climate["source"]),
        "location_context": {
            "urban_context_modifier": round(urban_modifier, 3),
            "tree_canopy_percent": urban_metrics.get("tree_canopy_percent"),
            "hw_ratio": urban_metrics.get("hw_ratio"),
            "sky_view_factor": urban_metrics.get("sky_view_factor"),
            "mean_wind_speed_m_s": urban_metrics.get("mean_wind_speed_m_s"),
            "infrared_city_utci_mean_c": urban_metrics.get("infrared_city_utci_mean_c"),
            "cooling_refuge_distance_m": urban_metrics.get("cooling_refuge_distance_m"),
            "infrared_city_heat_score": (urban_context or {}).get("infrared_city_heat_exposure")
            if isinstance(urban_context, dict)
            else None,
        },
        "room_diagnosis": {
            "room_id": spatial_index["room"]["id"],
            "solar_gain_score": component_scores["solar_gain"],
            "vent_deficit_score": component_scores["ventilation_deficit"],
            "envelope_score": component_scores["envelope"],
            "T_op_peak_C": round(operative_temperature_peak, 3),
            "WBGT_peak_C": round(wbgt_peak, 3),
            "health_risk_hours": overheating["weighted_hours"],
            "nocturnal_recovery_fail": nocturnal_recovery >= 0.6,
            "final_score": round(final_score, 3),
            "risk_level": classify_risk(final_score),
        },
        "composite_room_risk_score": round(composite, 3),
        "urban_modifier": round(urban_modifier, 3),
        "vulnerability_modifier": round(vulnerability_modifier, 3),
        "composite_risk_score_with_urban_context": round(final_score, 3),
        "applied_urban_context": {
            "urban_context_modifier": round(urban_modifier, 3),
            "urban_metrics": urban_metrics,
        },
        "risk_level": classify_risk(final_score),
    }
