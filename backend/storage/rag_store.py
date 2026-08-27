from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "paper_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_collection():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


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


def delete_session_chunks(session_id: str) -> None:
    get_collection().delete(where={"session_id": session_id})
