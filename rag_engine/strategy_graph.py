from __future__ import annotations

import json
import re
from pathlib import Path

from utils.config import DATA_DIR, ROOT_DIR


CATALOGUE_PATH = DATA_DIR / "input" / "strategy_catalogue.json"
EVIDENCE_MAP_PATH = DATA_DIR / "input" / "strategy_evidence_map.json"
SOURCE_METADATA_PATH = DATA_DIR / "source_metadata.json"


FALLBACK_TOPICS = {
    "shading": ["shading", "solar", "glazing", "window", "overheating", "external blind"],
    "ventilation": ["ventilation", "night purge", "cross ventilation", "airflow", "ACH"],
    "envelope": ["insulation", "U-value", "thermal bridge", "wall", "roof", "facade"],
    "thermal_comfort": ["operative temperature", "WBGT", "ASHRAE 55", "adaptive comfort"],
    "biophilic": ["green", "vegetation", "tree", "canopy", "biophilic", "plant"],
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(token) > 2}


def _load_strategies() -> dict[str, dict]:
    raw = _read_json(CATALOGUE_PATH)
    return {item.get("strategy_id", ""): item for item in raw.get("strategies", []) if item.get("strategy_id")}


def _load_evidence() -> dict[str, dict]:
    raw = _read_json(EVIDENCE_MAP_PATH)
    return raw.get("strategies", {})


def _load_sources() -> dict[str, dict]:
    raw = _read_json(SOURCE_METADATA_PATH)
    return {entry.get("source_id", ""): {"filename": filename, **entry} for filename, entry in raw.items()}


def infer_topic(query: str) -> str:
    query_tokens = _tokens(query)
    scores = {}
    for topic, keywords in FALLBACK_TOPICS.items():
        score = sum(1 for keyword in keywords if _tokens(keyword) & query_tokens or keyword in query.lower())
        if score:
            scores[topic] = score
    if scores:
        return max(scores.items(), key=lambda item: item[1])[0]
    return "general"


def infer_strategy(query: str) -> str | None:
    query_lower = query.lower()
    query_tokens = _tokens(query)
    strategies = _load_strategies()
    best_id = None
    best_score = 0.0

    for strategy_id, strategy in strategies.items():
        keywords = set(strategy.get("keywords", []))
        keywords.update(str(strategy.get("strategy_name", "")).split())
        keywords.update(str(strategy.get("user_facing_name", "")).split())
        keywords.update([strategy.get("category", ""), strategy_id.replace("_", " ")])
        score = 0.0
        for keyword in keywords:
            keyword = str(keyword).strip().lower()
            if not keyword:
                continue
            if keyword in query_lower:
                score += max(1.0, len(keyword.split()) * 0.8)
            else:
                score += 0.25 * len(_tokens(keyword) & query_tokens)
        if score > best_score:
            best_score = score
            best_id = strategy_id

    return best_id if best_score >= 1.0 else None


def graph_context_for_query(query: str) -> dict:
    strategies = _load_strategies()
    evidence_map = _load_evidence()
    sources = _load_sources()
    strategy_id = infer_strategy(query)
    topic = infer_topic(query)

    nodes = []
    edges = []
    retrieval_terms = [query, topic]
    literature_sources = []

    if strategy_id and strategy_id in strategies:
        strategy = strategies[strategy_id]
        evidence = evidence_map.get(strategy_id, {})
        nodes.append(
            {
                "id": strategy_id,
                "type": "strategy",
                "label": strategy.get("user_facing_name") or strategy.get("strategy_name", strategy_id),
                "category": strategy.get("category", ""),
                "evidence_level": evidence.get("evidence_level", strategy.get("evidence_confidence", "")),
            }
        )
        retrieval_terms.extend(strategy.get("keywords", []))
        retrieval_terms.extend(
            [
                strategy.get("strategy_name", ""),
                strategy.get("user_facing_name", ""),
                strategy.get("category", ""),
                strategy.get("notes", ""),
            ]
        )
        for source_id in evidence.get("primary_source_ids", []):
            source = sources.get(source_id, {"source_id": source_id, "source_title": source_id})
            literature_sources.append(source_id)
            nodes.append(
                {
                    "id": source_id,
                    "type": "source",
                    "label": source.get("source_title", source_id),
                    "filename": source.get("filename", ""),
                }
            )
            edges.append({"source": strategy_id, "target": source_id, "relation": "supported_by"})
    else:
        for strategy_id_candidate, strategy in strategies.items():
            if strategy.get("category", "") == topic:
                retrieval_terms.extend(strategy.get("keywords", [])[:5])

    return {
        "topic": topic,
        "strategy": strategy_id,
        "nodes": nodes,
        "edges": edges,
        "literature_sources": literature_sources,
        "retrieval_terms": sorted({str(term).strip() for term in retrieval_terms if str(term).strip()}),
    }


def graph_context_for_strategy(strategy_id: str) -> dict:
    strategy = _load_strategies().get(strategy_id)
    if not strategy:
        return graph_context_for_query(strategy_id.replace("_", " "))
    return graph_context_for_query(" ".join([strategy_id, strategy.get("strategy_name", ""), " ".join(strategy.get("keywords", []))]))
