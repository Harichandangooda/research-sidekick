from __future__ import annotations

from functools import lru_cache
import os
from threading import Lock
from typing import Any, TYPE_CHECKING

import chromadb
if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "paper_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_embedding_model_lock = Lock()


@lru_cache(maxsize=1)
def get_client():
    return chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST", "localhost"),
        port=int(os.getenv("CHROMA_PORT", "8001")),
    )


@lru_cache(maxsize=1)
def get_collection():
    return get_client().get_or_create_collection(name=COLLECTION_NAME)


@lru_cache(maxsize=1)
def _load_embedding_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def get_embedding_model() -> SentenceTransformer:
    # lru_cache alone permits concurrent cache misses to initialize several
    # heavyweight models when a user uploads multiple PDFs for the first time.
    with _embedding_model_lock:
        return _load_embedding_model()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def index_paper(paper_id: int, session_id: str, raw_text: str, file_name: str) -> int:
    chunks = chunk_text(raw_text)
    if not chunks:
        return 0

    model = get_embedding_model()
    embeddings = model.encode(chunks).tolist()
    ids = [f"paper_{paper_id}_chunk_{index}" for index, _ in enumerate(chunks)]
    metadatas: list[dict[str, Any]] = [
        {
            "paper_id": paper_id,
            "session_id": session_id,
            "file_name": file_name,
            "chunk_index": index,
        }
        for index, _ in enumerate(chunks)
    ]

    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def retrieve_chunks(paper_id: int, query: str, top_k: int = 5) -> list[str]:
    model = get_embedding_model()
    query_embedding = model.encode(query).tolist()
    results = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"paper_id": paper_id},
    )
    return results.get("documents", [[]])[0]


def retrieve_session_chunks(session_id: str, query: str, paper_ids: list[int], top_k: int = 5) -> list[dict]:
    """Rank chunks together across the session's successfully ingested papers."""
    if not paper_ids:
        return []
    query_embedding = get_embedding_model().encode(query).tolist()
    results = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"$and": [{"session_id": session_id}, {"paper_id": {"$in": paper_ids}}]},
        include=["documents", "metadatas"],
    )
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    return [{"paper_id": metadata["paper_id"], "text": document}
            for document, metadata in zip(documents, metadatas)
            if document and metadata and "paper_id" in metadata]


def delete_session_chunks(session_id: str) -> None:
    get_collection().delete(where={"session_id": session_id})


def delete_paper_chunks(paper_id: int) -> None:
    get_collection().delete(where={"paper_id": paper_id})
