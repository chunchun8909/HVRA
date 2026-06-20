from __future__ import annotations


def confidence_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def build_confidence_gate(effect_profile: dict, diagnosis_result: dict, spatial_index: dict) -> dict:
    score = float(effect_profile.get("confidence_score", 0.45))
    reasons = list(effect_profile.get("confidence_reasons", []))

    if spatial_index.get("scale_source") and "image" in str(spatial_index.get("scale_source")):
        score -= 0.05
        reasons.append("Room geometry uses image-derived estimation.")
    if diagnosis_result.get("climate_context_source") == "EPW":
        score += 0.08
        reasons.append("Climate indicators are extracted from real EPW weather data.")
    else:
        score -= 0.10
        reasons.append("Climate indicators are fallback estimates rather than EPW-derived.")

    score = max(0.0, min(1.0, score))
    return {
        "score": round(score, 3),
        "level": confidence_level(score),
        "reasons": reasons,
        "limitations": [
            "This is a deterministic screening validation, not a dynamic thermal simulation.",
            "Retrofit effects are strategy-level assumptions until product data or simulation is added.",
            "Formal overheating compliance should be checked with the relevant local method and weather file.",
        ],
    }
