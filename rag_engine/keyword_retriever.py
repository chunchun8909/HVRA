from __future__ import annotations

import math
import re
from collections import Counter

from utils.config import RAG_CHUNKS_JSONL, RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE
from .chunker import chunk_pages
from .document_loader import extract_pages, read_jsonl
from .source_catalog import discover_sources


STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "these",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9]+(?:[-_/][a-zA-Z0-9]+)?", text.lower())
        if len(token) > 1 and token not in STOPWORDS
    ]


def _load_chunks() -> list[dict]:
    chunks = read_jsonl(RAG_CHUNKS_JSONL)
    if chunks:
        return chunks

    pages = []
    for source in discover_sources():
        pages.extend(extract_pages(source))
    return chunk_pages(pages, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, mode="semantic")


def _normalize_chunk(raw: dict) -> dict:
    metadata = raw.get("metadata", {})
    return {
        "id": raw.get("id", ""),
        "source": metadata.get("source", raw.get("source", "")),
        "metadata": metadata,
        "score": raw.get("score", 0.0),
        "text": raw.get("text", ""),
        "retriever": raw.get("retriever", "keyword"),
    }


def _build_idf(chunks: list[dict]) -> dict[str, float]:
    frequencies = Counter()
    for chunk in chunks:
        frequencies.update(set(tokenize(chunk.get("text", ""))))
    total = max(len(chunks), 1)
    return {
        token: math.log((total + 1) / (frequency + 1)) + 1.0
        for token, frequency in frequencies.items()
    }


def bm25_retrieve(query: str, top_k: int = 10) -> list[dict]:
    chunks = [_normalize_chunk(chunk) for chunk in _load_chunks()]
    query_terms = tokenize(query)
    idf = _build_idf(chunks)
    avg_len = sum(len(tokenize(chunk["text"])) for chunk in chunks) / max(len(chunks), 1)
    k1 = 1.5
    b = 0.75
    query_counts = Counter(query_terms)
    scored = []

    for chunk in chunks:
        terms = tokenize(chunk["text"])
        counts = Counter(terms)
        doc_len = max(len(terms), 1)
        score = 0.0
        for term, query_count in query_counts.items():
            tf = counts.get(term, 0)
            if not tf:
                continue
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_len / max(avg_len, 1))
            score += idf.get(term, 1.0) * numerator / denominator * query_count
        if score > 0:
            scored.append({**chunk, "score": score, "bm25_score": score, "retriever": "keyword"})

    return sorted(scored, key=lambda item: item["bm25_score"], reverse=True)[:top_k]


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    return bm25_retrieve(query, top_k=top_k)
