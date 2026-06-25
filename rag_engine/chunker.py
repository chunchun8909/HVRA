from __future__ import annotations

from collections.abc import Iterable
import math
import re


def word_count(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap

    return chunks


def split_text_units(text: str) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", text)
        if paragraph.strip()
    ]
    if len(paragraphs) <= 1:
        paragraphs = [text.strip()]

    units = []
    for paragraph in paragraphs:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph)
            if sentence.strip()
        ]
        if len(sentences) <= 1:
            sentences = [paragraph]

        buffer = []
        for sentence in sentences:
            buffer.append(sentence)
            if word_count(" ".join(buffer)) >= 80:
                units.append(" ".join(buffer))
                buffer = []
        if buffer:
            units.append(" ".join(buffer))

    return [unit for unit in units if unit.strip()]


def lexical_vector(text: str) -> dict[str, float]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    counts: dict[str, float] = {}
    for token in tokens:
        if len(token) <= 2:
            continue
        counts[token] = counts.get(token, 0.0) + 1.0
    return counts


def cosine_sparse(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(token, 0.0) for token, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def adjacent_similarities(units: list[str]) -> list[float]:
    if len(units) < 2:
        return []
    vectors = [lexical_vector(unit) for unit in units]
    return [
        cosine_sparse(vectors[index], vectors[index + 1])
        for index in range(len(vectors) - 1)
    ]


def semantic_chunk_text(
    text: str,
    max_words: int,
    overlap_words: int,
    min_words: int = 220,
    break_percentile: int = 30,
) -> list[str]:
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")

    units = split_text_units(text)
    if len(units) <= 1:
        return chunk_text(text, max_words, overlap_words)

    similarities = adjacent_similarities(units)
    threshold = percentile(similarities, break_percentile)
    chunks = []
    current: list[str] = []

    for index, unit in enumerate(units):
        current.append(unit)
        current_words = word_count(" ".join(current))
        next_similarity = similarities[index] if index < len(similarities) else 1.0
        should_break = current_words >= max_words or (
            current_words >= min_words and next_similarity <= threshold
        )
        if should_break:
            chunk = " ".join(current).strip()
            if chunk:
                chunks.append(chunk)

            overlap_units = []
            overlap_total = 0
            for previous_unit in reversed(current):
                previous_words = word_count(previous_unit)
                if overlap_total + previous_words > overlap_words:
                    break
                overlap_units.insert(0, previous_unit)
                overlap_total += previous_words
            current = overlap_units

    final_chunk = " ".join(current).strip()
    if final_chunk and (not chunks or final_chunk != chunks[-1]):
        chunks.append(final_chunk)
    return chunks


def make_chunks_for_text(
    text: str,
    chunk_size: int,
    overlap: int,
    mode: str = "semantic",
    min_words: int = 220,
    break_percentile: int = 30,
) -> list[str]:
    if mode == "semantic":
        return semantic_chunk_text(
            text,
            max_words=chunk_size,
            overlap_words=overlap,
            min_words=min_words,
            break_percentile=break_percentile,
        )
    if mode == "overlap":
        return chunk_text(text, chunk_size, overlap)
    raise ValueError(f"Unsupported chunking mode: {mode}")


def chunk_pages(
    pages: Iterable[dict],
    chunk_size: int,
    overlap: int,
    mode: str = "semantic",
    min_words: int = 220,
    break_percentile: int = 30,
) -> list[dict]:
    chunks = []

    for page in pages:
        page_chunks = make_chunks_for_text(
            page["text"],
            chunk_size=chunk_size,
            overlap=overlap,
            mode=mode,
            min_words=min_words,
            break_percentile=break_percentile,
        )
        for chunk_index, text in enumerate(page_chunks):
            if not text.strip():
                continue
            chunks.append(
                {
                    "id": f"{page['source']}:page-{page['page']}:chunk-{chunk_index}",
                    "text": text,
                    "metadata": {
                        "source": page["source"],
                        "source_id": page["source_id"],
                        "source_title": page["source_title"],
                        "authors": page.get("authors", ""),
                        "year": page.get("year", ""),
                        "document_type": page.get("document_type", ""),
                        "citation": page.get("citation", ""),
                        "doi_or_url": page.get("doi_or_url", ""),
                        "format": page.get("format", ""),
                        "page": page["page"],
                        "chunk_index": chunk_index,
                        "chunking_mode": mode,
                        "chunk_words": word_count(text),
                    },
                }
            )

    return chunks
