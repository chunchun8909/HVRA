from __future__ import annotations

import json

from utils.config import INPUT_DIR
from .hybrid_retriever import retrieve


CATALOGUE_PATH = INPUT_DIR / "strategy_catalogue.json"
EVIDENCE_MAP_PATH = INPUT_DIR / "strategy_evidence_map.json"
BUILDING_INFO_PATH = INPUT_DIR / "building_info.json"


def load_strategy_catalogue() -> list[dict]:
    if not CATALOGUE_PATH.exists():
        return []
    with CATALOGUE_PATH.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return payload.get("strategies", [])




def load_building_info() -> dict:
    if not BUILDING_INFO_PATH.exists():
        return {}
    with BUILDING_INFO_PATH.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _era_start_year(construction_era: str) -> int | None:
    digits = "".join(char if char.isdigit() else " " for char in str(construction_era)).split()
    if not digits:
        return None
    try:
        return int(digits[0])
    except ValueError:
        return None


def _old_building_flag(building_info: dict) -> bool:
    year = _era_start_year(building_info.get("construction_era", ""))
    return bool(year and year < 1980)

def load_strategy_evidence_map() -> dict:
    if not EVIDENCE_MAP_PATH.exists():
        return {}
    with EVIDENCE_MAP_PATH.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return payload.get("strategies", {})


def _query_from_problem_map(problem_map: dict) -> str:
    parts = [problem.get("problem_type", "") for problem in problem_map.get("problems", [])]
    parts.extend(problem.get("primary_cause", "") for problem in problem_map.get("problems", []))
    return " ".join(parts)


def _strategy_query(base_query: str, strategy: dict) -> str:
    return " ".join([base_query, strategy["strategy_name"], strategy.get("category", ""), *strategy.get("keywords", [])])


def _format_evidence(evidence: list[dict]) -> list[dict]:
    formatted = []
    for item in evidence:
        metadata = item.get("metadata", {})
        formatted.append(
            {
                "source": metadata.get("source") or item.get("source", ""),
                "source_title": metadata.get("source_title", ""),
                "page": metadata.get("page"),
                "citation": metadata.get("citation", ""),
                "retrieval_mode": item.get("retrieval_mode") or item.get("retriever", ""),
                "score": round(float(item.get("hybrid_score", item.get("score", 0.0))), 4),
                "snippet": item.get("text", "")[:420],
            }
        )
    return formatted


def _restriction_reason(strategy: dict, constraints: dict, building_info: dict) -> str | None:
    strategy_id = strategy.get("strategy_id", "")
    tags = set(strategy.get("constraint_tags", []))
    target_components = set(strategy.get("target_components", []))
    excluded = set(constraints.get("excluded_strategy_type", []))
    preferred = set(constraints.get("preferred_strategy_type", []))
    facade_allowed = bool(constraints.get("facade_modification_allowed", False))
    heritage = str(constraints.get("heritage_restriction", "unknown")).lower()
    ownership = str(constraints.get("ownership_status", "unknown")).lower()
    permission_required = bool(constraints.get("construction_permission_required", False))
    is_top_floor = bool(building_info.get("is_top_floor", False))
    roof_exposed = bool(building_info.get("roof_exposed", False))
    has_balcony = bool(building_info.get("has_balcony", False))
    old_building = _old_building_flag(building_info)

    if strategy_id in excluded or tags.intersection(excluded):
        return "Excluded by current user constraints."
    if "portfolio_only" in tags or strategy.get("scope") in {"portfolio", "urban_context"}:
        return "Not a direct room retrofit; keep as contextual or portfolio-level option."
    if ("roof" in target_components or "roof_work" in tags) and not (is_top_floor and roof_exposed):
        return "Roof or ceiling-roof retrofit is only applicable when the unit is top-floor and roof-exposed."
    if ("roof" in target_components or "roof_work" in tags) and ownership == "renter":
        return "Roof work normally requires owner/building approval; keep as conditional, not an immediate unit-level retrofit."
    if "balcony" in target_components and not has_balcony:
        return "Balcony-based retrofit is not applicable because no balcony is confirmed."
    if "facade_modification" in tags and not facade_allowed:
        return "Facade modification is not currently allowed."
    if heritage in {"yes", "true", "protected"} and "facade_modification" in tags:
        return "Heritage or facade restrictions may block this option."
    if old_building and ("major_structural_change" in tags or "full_window_replacement" in tags):
        return "Older-building retrofit boundary: structural/window replacement needs detailed feasibility and permission review."
    if old_building and permission_required and "facade_modification" in tags:
        return "Older-building retrofit boundary: external facade changes require permission and building-physics review."
    if preferred and tags and not tags.intersection(preferred) and "higher_cost" in tags:
        return "Lower priority because it does not match preferred low-cost/reversible constraints."
    return None


def _with_public_fields(strategy: dict) -> dict:
    keys = [
        "strategy_id",
        "strategy_name",
        "user_facing_name",
        "category",
        "scope",
        "target_components",
        "applicable_facades",
        "delta_t_min_c",
        "delta_t_max_c",
        "cost_eur_m2_min",
        "cost_eur_m2_max",
        "carbon_kgco2e_m2_min",
        "carbon_kgco2e_m2_max",
        "applicability_conditions",
        "constraint_tags",
        "restriction",
        "notes",
        "literature_source",
        "effect_profile_id",
        "evidence_profile_id",
        "visual_profile_id",
        "effect_basis",
        "evidence_confidence",
        "keywords",
    ]
    return {key: strategy.get(key) for key in keys if key in strategy}


def check_manuals(problem_map: dict, constraints: dict) -> dict:
    query = _query_from_problem_map(problem_map) or "heat retrofit shading ventilation envelope"
    strategies = load_strategy_catalogue()
    evidence_map = load_strategy_evidence_map()
    building_info = load_building_info()

    eligible = []
    restricted = []
    for strategy in strategies:
        evidence = retrieve(_strategy_query(query, strategy), top_k=4)
        formatted_evidence = _format_evidence(evidence)
        base = _with_public_fields(strategy)
        catalogue_evidence = evidence_map.get(strategy.get("strategy_id", ""), {})
        if catalogue_evidence:
            base["catalogue_evidence"] = catalogue_evidence
        reason = _restriction_reason(strategy, constraints, building_info)

        if reason:
            restricted.append(
                {
                    **base,
                    "suitability": "restricted",
                    "restriction": reason,
                    "evidence": formatted_evidence,
                    "confidence": "medium" if formatted_evidence else "low",
                }
            )
            continue

        eligible.append(
            {
                **base,
                "suitability": "eligible",
                "source": formatted_evidence[0]["source"] if formatted_evidence else "strategy_catalogue.json",
                "evidence_snippet": formatted_evidence[0]["snippet"] if formatted_evidence else strategy.get("notes", "Strategy catalogue fallback."),
                "evidence": formatted_evidence,
                "confidence": "medium" if formatted_evidence else "low",
            }
        )

    return {
        "query": query,
        "retrieval_mode": "hybrid_with_keyword_fallback",
        "strategy_catalogue": str(CATALOGUE_PATH),
        "eligible_strategies": eligible,
        "restricted_strategies": restricted,
    }

