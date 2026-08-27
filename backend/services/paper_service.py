from __future__ import annotations

from backend.services.document_parser import extract_pdf_text
from backend.services.rag_service import index_paper_text
from backend.storage import session_store


def save_uploaded_pdf(session_id: str, file_name: str, file_bytes: bytes) -> dict:
    raw_text = extract_pdf_text(file_bytes)
    paper_context = {
        "file_name": file_name,
        "file_size": len(file_bytes),
        "raw_text": raw_text,
        "source": "uploaded_pdf",
    }
    paper_id = session_store.save_paper(session_id, paper_context)
    chunk_count = index_paper_text(paper_id, session_id, raw_text, file_name)

    return {
        "paper_id": paper_id,
        "file_name": file_name,
        "file_size": len(file_bytes),
        "chunk_count": chunk_count,
    }


def list_session_papers(session_id: str) -> list[dict]:
    return session_store.get_papers(session_id)


def get_paper_metadata(paper_id: int) -> dict | None:
    return session_store.get_paper(paper_id)


def get_paper_metadata_for_user(paper_id: int, user_id: int) -> dict | None:
    return session_store.get_paper_for_user(paper_id, user_id)
