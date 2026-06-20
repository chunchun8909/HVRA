from __future__ import annotations

import json

from utils.config import INPUT_DIR
from .hybrid_retriever import retrieve


CATALOGUE_PATH = INPUT_DIR / "strategy_catalogue.json"


def load_strategy_catalogue() -> list[dict]:
    if not CATALOGUE_PATH.exists():
        return []
    with CATALOGUE_PATH.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return payload.get("strategies", [])


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


def _restriction_reason(strategy: dict, constraints: dict) -> str | None:
    strategy_id = strategy.get("strategy_id", "")
    tags = set(strategy.get("constraint_tags", []))
    excluded = set(constraints.get("excluded_strategy_type", []))
    preferred = set(constraints.get("preferred_strategy_type", []))
    facade_allowed = bool(constraints.get("facade_modification_allowed", False))
    heritage = str(constraints.get("heritage_restriction", "unknown")).lower()

    if strategy_id in excluded or tags.intersection(excluded):
        return "Excluded by current user constraints."
    if "portfolio_only" in tags or strategy.get("scope") in {"portfolio", "urban_context"}:
        return "Not a direct room retrofit; keep as contextual or portfolio-level option."
    if "facade_modification" in tags and not facade_allowed:
        return "Facade modification is not currently allowed."
    if heritage in {"yes", "true", "protected"} and "facade_modification" in tags:
        return "Heritage or facade restrictions may block this option."
    if preferred and tags and not tags.intersection(preferred) and "higher_cost" in tags:
        return "Lower priority because it does not match preferred low-cost/reversible constraints."
    return None


def _with_public_fields(strategy: dict) -> dict:
    keys = [
        "strategy_id",
        "strategy_name",
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
        "keywords",
    ]
    return {key: strategy.get(key) for key in keys if key in strategy}


def check_manuals(problem_map: dict, constraints: dict) -> dict:
    query = _query_from_problem_map(problem_map) or "heat retrofit shading ventilation envelope"
    strategies = load_strategy_catalogue()

    eligible = []
    restricted = []
    for strategy in strategies:
        evidence = retrieve(_strategy_query(query, strategy), top_k=4)
        formatted_evidence = _format_evidence(evidence)
        base = _with_public_fields(strategy)
        reason = _restriction_reason(strategy, constraints)

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

