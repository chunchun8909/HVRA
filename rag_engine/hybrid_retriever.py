from __future__ import annotations

import re

from .keyword_retriever import bm25_retrieve, tokenize
from .strategy_graph import graph_context_for_query
from .vector_retriever import retrieve as vector_retrieve


def _key(result: dict) -> str:
    return result.get("id") or ":".join(
        [
            str(result.get("metadata", {}).get("source", "")),
            str(result.get("metadata", {}).get("page", "")),
            str(result.get("metadata", {}).get("chunk_index", "")),
        ]
    )


def _reciprocal_rank(rank: int | None) -> float:
    if rank is None:
        return 0.0
    return 1.0 / (rank + 1)


def _graph_boost(graph_context: dict, result: dict) -> float:
    haystack = f"{result.get('text', '')} {' '.join(str(value) for value in result.get('metadata', {}).values())}".lower()
    terms = []
    terms.extend(graph_context.get("retrieval_terms", []))
    for node in graph_context.get("nodes", []):
        terms.append(str(node.get("id", "")).replace("_", " "))
        terms.append(str(node.get("label", "")))
    hits = sum(1 for term in terms if term and str(term).lower() in haystack)
    return min(hits / 6.0, 1.0)


def _source_boost(graph_context: dict, result: dict) -> float:
    source_id = str(result.get("metadata", {}).get("source_id", ""))
    source = str(result.get("metadata", {}).get("source", ""))
    sources = set(graph_context.get("literature_sources", []))
    if source_id in sources:
        return 1.0
    return 0.5 if any(item.lower() in source.lower() for item in sources) else 0.0


def _coverage(query: str, result: dict) -> float:
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    text = result.get("text", "").lower()
    return len([term for term in query_terms if term in text]) / max(len(query_terms), 1)


def _merge(vector_results: list[dict], bm25_results: list[dict]) -> list[dict]:
    merged = {}
    for rank, result in enumerate(vector_results, start=1):
        key = _key(result)
        merged[key] = {
            **result,
            "vector_rank": rank,
            "bm25_rank": None,
            "bm25_score": 0.0,
            "vector_score": float(result.get("score", 0.0)),
        }
    for rank, result in enumerate(bm25_results, start=1):
        key = _key(result)
        if key not in merged:
            merged[key] = {
                **result,
                "vector_rank": None,
                "bm25_rank": rank,
                "vector_score": 0.0,
                "bm25_score": float(result.get("bm25_score", result.get("score", 0.0))),
            }
        else:
            merged[key]["bm25_rank"] = rank
            merged[key]["bm25_score"] = float(result.get("bm25_score", result.get("score", 0.0)))
            merged[key]["retrieval_mode"] = "hybrid"
    return list(merged.values())


def _rerank(query: str, graph_context: dict, candidates: list[dict]) -> list[dict]:
    max_bm25 = max((candidate.get("bm25_score", 0.0) for candidate in candidates), default=1.0)
    for candidate in candidates:
        bm25_component = candidate.get("bm25_score", 0.0) / max(max_bm25, 1.0)
        vector_component = _reciprocal_rank(candidate.get("vector_rank"))
        bm25_rank_component = _reciprocal_rank(candidate.get("bm25_rank"))
        graph_component = _graph_boost(graph_context, candidate)
        source_component = _source_boost(graph_context, candidate)
        coverage_component = _coverage(query, candidate)
        candidate["hybrid_score"] = round(
            0.25 * vector_component
            + 0.22 * bm25_rank_component
            + 0.18 * bm25_component
            + 0.14 * graph_component
            + 0.13 * source_component
            + 0.08 * coverage_component,
            6,
        )
        candidate["graph_score"] = round(graph_component, 4)
        candidate["source_boost"] = round(source_component, 4)
        candidate["retrieval_mode"] = "hybrid_graphrag"
    return sorted(candidates, key=lambda item: item["hybrid_score"], reverse=True)


def _assess_sufficiency(graph_context: dict, results: list[dict]) -> dict:
    if not results:
        return {"sufficient": False, "reason": "No chunks were retrieved."}
    has_sources = any(result.get("metadata", {}).get("source_title") for result in results)
    has_graph = bool(graph_context.get("nodes") or graph_context.get("retrieval_terms"))
    graph_hit = any(result.get("graph_score", 0.0) > 0 for result in results)
    source_hit = any(result.get("source_boost", 0.0) > 0 for result in results)
    sufficient = has_sources and has_graph and (graph_hit or source_hit)
    return {
        "sufficient": sufficient,
        "has_source_evidence": has_sources,
        "has_graph_context": has_graph,
        "has_graph_or_source_hit": graph_hit or source_hit,
        "reason": "Graph and literature evidence are present." if sufficient else "Context may be missing strategy-specific source support.",
    }


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    graph_context = graph_context_for_query(query)
    graph_terms = " ".join(graph_context.get("retrieval_terms", []))
    retrieval_query = f"{query} {graph_terms}".strip()

    bm25_results = bm25_retrieve(retrieval_query, top_k=top_k * 4)
    vector_results = []
    vector_error = None
    try:
        vector_results = vector_retrieve(retrieval_query, top_k=top_k * 4)
    except RuntimeError as error:
        vector_error = str(error)

    ranked = _rerank(retrieval_query, graph_context, _merge(vector_results, bm25_results))[:top_k]
    sufficiency = _assess_sufficiency(graph_context, ranked)

    for result in ranked:
        result["graph_context"] = {
            "topic": graph_context.get("topic"),
            "strategy": graph_context.get("strategy"),
            "literature_sources": graph_context.get("literature_sources", []),
        }
        result["sufficiency"] = sufficiency
        if vector_error:
            result["vector_status"] = f"fallback: {vector_error}"
    return ranked
