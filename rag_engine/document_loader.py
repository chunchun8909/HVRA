from __future__ import annotations

import json
from pathlib import Path


def _base_page_record(source: dict, page: int, text: str) -> dict:
    return {
        "page": page,
        "source": source["source"],
        "source_id": source["source_id"],
        "source_title": source["source_title"],
        "authors": source.get("authors", ""),
        "year": source.get("year", ""),
        "document_type": source.get("document_type", ""),
        "citation": source.get("citation", ""),
        "doi_or_url": source.get("doi_or_url", ""),
        "format": source.get("format", ""),
        "text": " ".join(text.split()),
    }


def extract_markdown_pages(source: dict) -> list[dict]:
    text = source["path"].read_text(encoding="utf-8")
    return [_base_page_record(source, 1, text)]


def extract_pdf_pages(source: dict) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("Install pypdf to ingest raw PDFs: pip install -r requirements.txt") from error

    pdf_path = source["path"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append(_base_page_record(source, index, page.extract_text() or ""))
    return pages




def extract_pdf_pages_with_pdfminer(source: dict) -> list[dict]:
    try:
        from pdfminer.high_level import extract_text
    except ImportError as error:
        raise RuntimeError(
            "Install pdfminer.six to ingest PDFs that pypdf cannot parse: pip install -r requirements.txt"
        ) from error

    pdf_path = source["path"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = extract_text(str(pdf_path))
    if not text.strip():
        return [_base_page_record(source, 1, "")]

    pages = []
    for index, page_text in enumerate(text.split("\f"), start=1):
        if page_text.strip():
            pages.append(_base_page_record(source, index, page_text))
    return pages or [_base_page_record(source, 1, text)]

def extract_pages(source: dict) -> list[dict]:
    if source["format"] == "pdf":
        try:
            return extract_pdf_pages(source)
        except Exception:
            return extract_pdf_pages_with_pdfminer(source)
    if source["format"] == "md":
        return extract_markdown_pages(source)
    return []


def load_markdown_documents(documents_dir: Path) -> list[dict]:
    documents = []
    for path in sorted(documents_dir.glob("*.md")):
        documents.append({"source": path.name, "text": path.read_text(encoding="utf-8")})
    return documents


def write_jsonl(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]

