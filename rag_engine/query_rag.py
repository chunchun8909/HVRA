from __future__ import annotations

import argparse
import json
import sys

from .hybrid_retriever import retrieve


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Query the HVRA RAG retriever.")
    parser.add_argument("query", help="Question or search query.")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    print(json.dumps(retrieve(args.query, top_k=args.top_k), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
