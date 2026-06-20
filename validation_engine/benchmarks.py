from __future__ import annotations


BENCHMARK_SOURCES = {
    "ashrae_55": {
        "name": "ANSI/ASHRAE Standard 55: Thermal Environmental Conditions for Human Occupancy",
        "url": "https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy",
        "notes": [
            "Thermal comfort standard for acceptable indoor environmental conditions.",
            "This V&V gate uses operative temperature as a screening indicator, not a full PMV/adaptive-comfort compliance calculation.",
        ],
    },
    "en_iso_7726": {
        "name": "EN ISO 7726: Ergonomics of the thermal environment - instruments for measuring and monitoring physical quantities",
        "url": "https://www.iso.org/standard/78238.html",
        "notes": [
            "Defines measurement and derived quantities for thermal-environment assessment, including operative temperature.",
            "Used here to document the operative-temperature indicator basis.",
        ],
    },
    "cibse_tm59": {
        "name": "CIBSE TM59: Design methodology for the assessment of overheating risk in homes",
        "url": "https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes/?id=a0q0O00000DVrTdQAL",
        "notes": [
            "Residential overheating assessment methodology for new and refurbished homes.",
            "CIBSE states that dynamic thermal modelling should be used for formal assessment.",
        ],
    },
    "cibse_tm59_bedroom_sleep": {
        "name": "CIBSE TM59 / CIBSE Guide A bedroom night criterion",
        "url": "https://www.cibsejournal.com/technical/using-tm59-to-assess-overheating-risk-in-homes/",
        "notes": [
            "Bedroom operative temperatures above 26 C at night are treated as a sleep-disruption risk.",
            "This engine uses the 26 C value as a rule-based nocturnal recovery screening threshold.",
        ],
    },
    "iso_7243_wbgt": {
        "name": "ISO 7243:2017 WBGT heat-stress screening",
        "url": "https://www.iso.org/standard/67188.html",
        "notes": [
            "ISO 7243 presents a WBGT screening method for evaluating heat stress.",
            "This residential tool uses WBGT as an indicative heat-stress flag, not an occupational exposure determination.",
        ],
    },
    "samuelson_2020_housing_heat_vulnerability": {
        "name": "Samuelson et al. (2020), Housing as a critical determinant of heat vulnerability and health",
        "url": "https://hero.epa.gov/reference/7725666/",
        "notes": [
            "Frames housing characteristics as determinants of indoor heat exposure and health vulnerability.",
            "Used here to justify vulnerable-occupant weighting and nocturnal recovery as health-relevant screening indicators.",
        ],
    },
    "ukhsa_phe_indoor_heat": {
        "name": "UKHSA / Public Health England heat-health evidence and indoor temperature guidance",
        "url": "https://researchportal.ukhsa.gov.uk/en/publications/defining-indoor-heat-thresholds-for-health-in-the-uk/",
        "notes": [
            "Indoor heat-threshold evidence highlights susceptible groups, sleep, heat-health alerts, and overheating risk in buildings.",
            "The former Heatwave Plan for England used 26 C as an upper limit for cool areas; this is used as a screening reference for night recovery.",
        ],
    },
    "cte_db_he": {
        "name": "Codigo Tecnico de la Edificacion DB-HE, HE1 thermal-envelope requirements",
        "url": "https://www.codigotecnico.org/",
        "notes": [
            "Spanish building energy code framework for limiting energy demand through thermal-envelope performance.",
            "Used here as the regulatory basis for envelope-threshold review; project-specific U-value compliance needs climate-zone data.",
        ],
    },
    "en_15242": {
        "name": "EN 15242: Ventilation for buildings - calculation methods for determining air flow rates including infiltration",
        "url": "https://webstore.ansi.org/standards/ds/dsen152422007",
        "notes": [
            "Describes calculation of ventilation air-flow rates for energy, comfort, cooling-load, and IAQ evaluation.",
            "Used here as the basis for treating ACH and cross-ventilation as screening ventilation indicators.",
        ],
    },
    "ashrae_62_1": {
        "name": "ANSI/ASHRAE Standard 62.1: Ventilation for Acceptable Indoor Air Quality",
        "url": "https://www.ashrae.org/resources--publications/bookstore/standards-62-1--62-2",
        "notes": [
            "Specifies minimum ventilation rates and related measures for acceptable indoor air quality.",
            "Residential systems may also reference ASHRAE 62.2; this gate uses 62.1/62.2 family logic as a ventilation benchmark basis.",
        ],
    },
}


def evaluate_peak_operative_temperature(value_c: float) -> dict:
    if value_c <= 28.0:
        status = "pass"
    elif value_c <= 30.0:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "peak_indoor_operative_temperature",
        "value": round(value_c, 3),
        "unit": "C",
        "status": status,
        "pass_threshold": "<= 28 C",
        "partial_threshold": "<= 30 C",
        "benchmark_basis": ["ashrae_55", "en_iso_7726", "cibse_tm59"],
        "note": "Screening proxy using operative temperature; formal comfort/overheating compliance requires the applicable full method.",
    }


def evaluate_wbgt(value_c: float) -> dict:
    if value_c <= 26.0:
        status = "pass"
    elif value_c <= 28.0:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "heat_stress_wbgt",
        "value": round(value_c, 3),
        "unit": "C-WBGT",
        "status": status,
        "pass_threshold": "<= 26 C-WBGT",
        "partial_threshold": "<= 28 C-WBGT",
        "benchmark_basis": ["iso_7243_wbgt"],
        "note": "Indicative residential screening threshold derived from WBGT heat-stress method use.",
    }


def evaluate_nocturnal_recovery(estimated_indoor_3am_c: float, age_group: str) -> dict:
    threshold = 25.0 if age_group == "75_plus" else 26.0
    if estimated_indoor_3am_c <= threshold:
        status = "pass"
    elif estimated_indoor_3am_c <= threshold + 2.0:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "nocturnal_recovery",
        "value": round(estimated_indoor_3am_c, 3),
        "unit": "C",
        "status": status,
        "pass_threshold": f"<= {threshold:g} C",
        "partial_threshold": f"<= {threshold + 2:g} C",
        "benchmark_basis": [
            "cibse_tm59_bedroom_sleep",
            "samuelson_2020_housing_heat_vulnerability",
            "ukhsa_phe_indoor_heat",
        ],
        "note": "Uses a vulnerable-occupant adjustment around bedroom sleep and indoor heat-health guidance.",
    }


def evaluate_overheating_reduction(baseline_hours: float, proposed_hours: float) -> dict:
    reduction_pct = 0.0
    if baseline_hours > 0:
        reduction_pct = (baseline_hours - proposed_hours) / baseline_hours * 100.0
    if proposed_hours <= 32 or reduction_pct >= 50.0:
        status = "pass"
    elif reduction_pct >= 25.0:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "overheating_hours",
        "baseline_hours": round(baseline_hours, 3),
        "proposed_hours": round(proposed_hours, 3),
        "reduction_pct": round(reduction_pct, 3),
        "status": status,
        "pass_threshold": "<= 32 annual bedroom night hours or >= 50% reduction",
        "partial_threshold": ">= 25% reduction",
        "benchmark_basis": [
            "cibse_tm59_bedroom_sleep",
            "samuelson_2020_housing_heat_vulnerability",
            "ukhsa_phe_indoor_heat",
        ],
        "note": "The 32-hour value corresponds to 1% of annual 10pm-7am bedroom hours; this engine uses hot-season proxy hours.",
    }


def evaluate_envelope_score(score: float) -> dict:
    if score <= 0.35:
        status = "pass"
    elif score <= 0.65:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "envelope_heat_risk_score",
        "value": round(score, 3),
        "status": status,
        "pass_threshold": "<= 0.35 envelope risk score",
        "partial_threshold": "<= 0.65 envelope risk score",
        "benchmark_basis": ["cte_db_he"],
        "note": "Screening proxy for envelope weakness; formal CTE DB-HE review requires climate zone, element U-values, and global K checks.",
    }


def evaluate_ventilation_deficit(score: float) -> dict:
    if score <= 0.35:
        status = "pass"
    elif score <= 0.65:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "ventilation_deficit_score",
        "value": round(score, 3),
        "status": status,
        "pass_threshold": "<= 0.35 ventilation deficit score",
        "partial_threshold": "<= 0.65 ventilation deficit score",
        "benchmark_basis": ["en_15242", "ashrae_62_1"],
        "note": "Screening proxy based on ACH and cross-ventilation; formal ventilation design requires airflow-rate calculation.",
    }


def evaluate_risk_score(final_score: float) -> dict:
    if final_score < 0.4:
        status = "pass"
    elif final_score < 0.65:
        status = "partial_pass"
    else:
        status = "fail"
    return {
        "indicator": "composite_room_risk_score",
        "value": round(final_score, 3),
        "status": status,
        "pass_threshold": "< 0.40",
        "partial_threshold": "< 0.65",
        "benchmark_basis": ["hvra_internal_risk_classification"],
        "note": "Internal HVRA classification aligned with diagnosis_engine.formulas.classify_risk.",
    }


def overall_status(checks: dict[str, dict]) -> str:
    statuses = [check["status"] for check in checks.values()]
    if any(status == "fail" for status in statuses):
        if any(status == "pass" for status in statuses) or any(status == "partial_pass" for status in statuses):
            return "partial_pass"
        return "fail"
    if any(status == "partial_pass" for status in statuses):
        return "partial_pass"
    return "pass"
