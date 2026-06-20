from __future__ import annotations


# Literature-informed screening weights from the HVRA reference methodology.
# The source explicitly frames solar gain and ventilation as the primary
# Mediterranean indoor-overheating drivers, with envelope condition and
# occupant vulnerability as secondary modifiers. Nocturnal recovery is kept
# outside the base composite and applied in the final risk modifier/benchmarks.
ACADEMIC_SOURCE_WEIGHT_RATIONALE = {
    "source": "risk_map/dataset/HVRA_build_reference_4.md, Stage 2d composite_score",
    "supporting_references": [
        "Samuelson et al. (2020), Housing as a Critical Determinant of Heat Vulnerability and Health",
        "Public Health England / UKHSA heat-health evidence and indoor temperature guidance",
        "WHO (2011), Heat and Health",
        "ISO 7243:2017 WBGT heat-stress screening",
        "ASHRAE 55 / EN ISO 7726 operative-temperature framing",
        "UPC Barcelona heat-vulnerability study for Mediterranean driver emphasis",
    ],
    "notes": [
        "The exact composite weights are a documented screening assumption, not an official regulatory coefficient.",
        "Solar gain and ventilation receive the largest shares because they dominate summer overheating risk in the reference methodology.",
        "Nocturnal recovery is calculated as a separate health-relevant KPI and applied downstream in final risk and validation checks.",
    ],
}

ACADEMIC_SOURCE_WEIGHTS = {
    "solar_gain": 0.40,
    "ventilation_deficit": 0.35,
    "envelope": 0.15,
    "nocturnal_recovery": 0.00,
    "occupant_vulnerability": 0.10,
}

WEIGHT_PROFILES = {
    "elderly_heat_risk": ACADEMIC_SOURCE_WEIGHTS,
    "renter_low_budget": ACADEMIC_SOURCE_WEIGHTS,
    "default": ACADEMIC_SOURCE_WEIGHTS,
}


def get_profile(name: str) -> dict:
    return dict(WEIGHT_PROFILES.get(name, WEIGHT_PROFILES["default"]))


def get_profile_rationale() -> dict:
    return ACADEMIC_SOURCE_WEIGHT_RATIONALE
