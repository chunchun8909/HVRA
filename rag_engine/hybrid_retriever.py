from __future__ import annotations

from .keyword_retriever import retrieve as keyword_retrieve
from .vector_retriever import retrieve as vector_retrieve


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    keyword_results = keyword_retrieve(query, top_k=top_k * 2)
    vector_results = []
    vector_error = None

    try:
        vector_results = vector_retrieve(query, top_k=top_k * 2)
    except RuntimeError as error:
        vector_error = str(error)

    merged: dict[str, dict] = {}
    max_keyword_score = max([result["score"] for result in keyword_results], default=1)

    for result in keyword_results:
        key = result["id"]
        normalized_score = result["score"] / max_keyword_score
        merged[key] = {
            **result,
            "keyword_score": normalized_score,
            "vector_score": 0.0,
            "hybrid_score": normalized_score * 0.45,
            "retrieval_mode": "keyword",
        }

    for result in vector_results:
        key = result["id"]
        vector_score = float(result.get("score", 0.0))
        if key in merged:
            merged[key]["vector_score"] = vector_score
            merged[key]["hybrid_score"] += vector_score * 0.55
            merged[key]["retrieval_mode"] = "hybrid"
        else:
            merged[key] = {
                **result,
                "keyword_score": 0.0,
                "vector_score": vector_score,
                "hybrid_score": vector_score * 0.55,
                "retrieval_mode": "vector",
            }

    results = sorted(merged.values(), key=lambda item: item["hybrid_score"], reverse=True)[:top_k]
    for result in results:
        if vector_error:
            result["vector_status"] = f"fallback: {vector_error}"
    return results
