from __future__ import annotations

import argparse
import shutil

from utils.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_CHUNKS_JSONL, RAG_PAGES_JSONL, RAG_VECTOR_DB_DIR
from .chunker import chunk_pages
from .document_loader import extract_pages, write_jsonl
from .source_catalog import discover_sources
from .vector_retriever import index_chunks


DEFAULT_CHUNKING_MODE = "semantic"
DEFAULT_SEMANTIC_MIN_WORDS = 220
DEFAULT_SEMANTIC_BREAK_PERCENTILE = 30


def clean_generated_rag_outputs() -> list[str]:
    removed = []
    for path in [RAG_PAGES_JSONL, RAG_CHUNKS_JSONL]:
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if RAG_VECTOR_DB_DIR.exists():
        shutil.rmtree(RAG_VECTOR_DB_DIR)
        removed.append(str(RAG_VECTOR_DB_DIR))
    RAG_PAGES_JSONL.parent.mkdir(parents=True, exist_ok=True)
    RAG_VECTOR_DB_DIR.parent.mkdir(parents=True, exist_ok=True)
    return removed


def build_index(
    chunking_mode: str = DEFAULT_CHUNKING_MODE,
    semantic_min_words: int = DEFAULT_SEMANTIC_MIN_WORDS,
    semantic_break_percentile: int = DEFAULT_SEMANTIC_BREAK_PERCENTILE,
    clean: bool = False,
) -> dict:
    removed = clean_generated_rag_outputs() if clean else []
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

    chunks = chunk_pages(
        pages,
        RAG_CHUNK_SIZE,
        RAG_CHUNK_OVERLAP,
        mode=chunking_mode,
        min_words=semantic_min_words,
        break_percentile=semantic_break_percentile,
    )
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
        "chunking_mode": chunking_mode,
        "semantic_min_words": semantic_min_words,
        "semantic_break_percentile": semantic_break_percentile,
        "removed_generated_outputs": removed,
        "source_errors": source_errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the HVRA RAG semantic index.")
    parser.add_argument("--clean", action="store_true", help="Delete generated pages/chunks/vector DB before rebuilding.")
    parser.add_argument("--chunking-mode", choices=["semantic", "overlap"], default=DEFAULT_CHUNKING_MODE)
    parser.add_argument("--semantic-min-words", type=int, default=DEFAULT_SEMANTIC_MIN_WORDS)
    parser.add_argument("--semantic-break-percentile", type=int, default=DEFAULT_SEMANTIC_BREAK_PERCENTILE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_index(
        chunking_mode=args.chunking_mode,
        semantic_min_words=args.semantic_min_words,
        semantic_break_percentile=args.semantic_break_percentile,
        clean=args.clean,
    )
    print(result)


if __name__ == "__main__":
    main()
