from __future__ import annotations

import json
import re
from pathlib import Path

from utils.config import RAG_DOCUMENTS_DIR, RAG_RAW_PDF_DIR, RAG_SOURCE_METADATA_JSON


def make_source_id(path: Path) -> str:
    source_id = re.sub(r"[^a-zA-Z0-9]+", "_", path.stem).strip("_")
    return source_id.upper() or "SOURCE"


def make_source_title(path: Path) -> str:
    title = re.sub(r"[_-]+", " ", path.stem)
    title = re.sub(r"\s+", " ", title).strip()
    return title.title() or path.name


def load_source_metadata() -> dict[str, dict]:
    if not RAG_SOURCE_METADATA_JSON.exists():
        return {}

    metadata = json.loads(RAG_SOURCE_METADATA_JSON.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError(f"{RAG_SOURCE_METADATA_JSON} must contain an object keyed by filename.")
    return metadata


def build_source_record(path: Path, metadata: dict) -> dict:
    return {
        "path": path,
        "source": path.name,
        "source_id": metadata.get("source_id") or make_source_id(path),
        "source_title": metadata.get("source_title") or metadata.get("title") or make_source_title(path),
        "authors": metadata.get("authors", ""),
        "year": metadata.get("year", ""),
        "document_type": metadata.get("document_type") or metadata.get("type", ""),
        "citation": metadata.get("citation", ""),
        "doi_or_url": metadata.get("doi_or_url") or metadata.get("url", ""),
        "format": path.suffix.lower().lstrip("."),
    }


def discover_sources() -> list[dict]:
    metadata_by_filename = load_source_metadata()
    pdf_paths = sorted(RAG_RAW_PDF_DIR.glob("*.pdf"))
    markdown_paths = sorted(RAG_DOCUMENTS_DIR.glob("*.md"))
    paths = [*pdf_paths, *markdown_paths]

    return [
        build_source_record(path, metadata_by_filename.get(path.name, {}))
        for path in paths
    ]

