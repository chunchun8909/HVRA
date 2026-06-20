from __future__ import annotations

from utils.config import RAG_COLLECTION_NAME, RAG_VECTOR_DB_DIR


def _chromadb():
    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    except ImportError as error:
        raise RuntimeError("Install chromadb to use vector retrieval: pip install -r requirements.txt") from error
    return chromadb, DefaultEmbeddingFunction


def get_collection():
    chromadb, default_embedding_function = _chromadb()
    RAG_VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(RAG_VECTOR_DB_DIR))
    return client.get_or_create_collection(
        name=RAG_COLLECTION_NAME,
        embedding_function=default_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    chromadb, _default_embedding_function = _chromadb()
    RAG_VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(RAG_VECTOR_DB_DIR))
    try:
        client.delete_collection(name=RAG_COLLECTION_NAME)
    except Exception:
        pass
    return get_collection()


def index_chunks(chunks: list[dict], reset: bool = True) -> int:
    collection = reset_collection() if reset else get_collection()
    if not chunks:
        return 0

    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return len(chunks)


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    collection = get_collection()
    try:
        results = collection.query(query_texts=[query], n_results=top_k)
    except Exception as error:
        raise RuntimeError("Vector collection is not ready. Run python -m rag_engine.build_index.") from error

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    return [
        {
            "id": chunk_id,
            "text": document,
            "metadata": metadata,
            "distance": distance,
            "score": max(0.0, 1.0 - float(distance)),
            "retriever": "vector",
        }
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances)
    ]
