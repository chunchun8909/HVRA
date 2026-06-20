from __future__ import annotations


def route_for_case(interpreted_case: dict) -> list[str]:
    return [
        "spatial_engine",
        "knowledge_graph",
        "diagnosis_engine",
        "rag_engine",
        "gemini_engine",
        "report_engine",
    ]

