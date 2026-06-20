from __future__ import annotations

import re

from utils.config import RAG_CHUNKS_JSONL, RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE
from .chunker import chunk_pages
from .document_loader import extract_pages, read_jsonl
from .source_catalog import discover_sources


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "room",
    "risk",
    "heat",
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", text.lower()) if token not in STOPWORDS}


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    query_tokens = _tokens(query)
    results = []

    chunks = read_jsonl(RAG_CHUNKS_JSONL)
    if not chunks:
        pages = []
        for source in discover_sources():
            pages.extend(extract_pages(source))
        chunks = chunk_pages(pages, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP)

    for chunk in chunks:
        chunk_tokens = _tokens(chunk["text"])
        raw_score = len(query_tokens & chunk_tokens)
        if raw_score:
            metadata = chunk.get("metadata", {})
            results.append(
                {
                    "id": chunk["id"],
                    "source": metadata.get("source", ""),
                    "metadata": metadata,
                    "score": raw_score,
                    "text": chunk["text"],
                    "retriever": "keyword",
                }
            )

    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
