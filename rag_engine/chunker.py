from __future__ import annotations

from collections.abc import Iterable


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


def chunk_pages(pages: Iterable[dict], chunk_size: int, overlap: int) -> list[dict]:
    chunks = []

    for page in pages:
        for chunk_index, text in enumerate(chunk_text(page["text"], chunk_size, overlap)):
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
                    },
                }
            )

    return chunks
