from __future__ import annotations

from backend.storage import rag_store


def index_paper_text(paper_id: int, session_id: str, raw_text: str, file_name: str) -> int:
    return rag_store.index_paper(paper_id, session_id, raw_text, file_name)


def delete_session_index(session_id: str) -> None:
    rag_store.delete_session_chunks(session_id)


def retrieve_relevant_chunks(paper_id: int, query: str, top_k: int = 5) -> list[str]:
    return rag_store.retrieve_chunks(paper_id, query, top_k)
