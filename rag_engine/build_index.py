from __future__ import annotations

from utils.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_CHUNKS_JSONL, RAG_PAGES_JSONL
from .chunker import chunk_pages
from .document_loader import extract_pages, write_jsonl
from .source_catalog import discover_sources
from .vector_retriever import index_chunks


def build_index() -> dict:
    sources = discover_sources()
    pages = []
    source_errors = []
    for source in sources:
        try:
            pages.extend(extract_pages(source))
        except Exception as error:
            source_errors.append(
                {
                    "source": source.get("source", ""),
                    "error": str(error),
                }
            )

    chunks = chunk_pages(pages, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP)
    write_jsonl(pages, RAG_PAGES_JSONL)
    write_jsonl(chunks, RAG_CHUNKS_JSONL)

    indexed_count = 0
    vector_status = "skipped_no_chunks"
    if chunks:
        try:
            indexed_count = index_chunks(chunks, reset=True)
            vector_status = "indexed"
        except RuntimeError as error:
            vector_status = f"vector_unavailable: {error}"

    return {
        "sources": len(sources),
        "pages": len(pages),
        "chunks": len(chunks),
        "indexed_chunks": indexed_count,
        "vector_status": vector_status,
        "source_errors": source_errors,
    }


def main() -> None:
    result = build_index()
    print(result)


if __name__ == "__main__":
    main()
