from __future__ import annotations

import logging

from backend.services.document_parser import extract_pdf_text
from backend.limits import MAX_UPLOAD_BYTES, MAX_PAPER_CHARACTERS
from backend.services.rag_service import index_paper_text
from backend.storage import session_store

logger = logging.getLogger(__name__)


def save_uploaded_pdf(session_id: str, file_name: str, file_bytes: bytes) -> dict:
    if not file_bytes:
        raise ValueError("The PDF is empty")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("PDF uploads must be 20 MB or smaller")
    if not file_bytes.lstrip().startswith(b"%PDF-"):
        raise ValueError("The file is not a valid PDF")
    try:
        raw_text = extract_pdf_text(file_bytes)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF is corrupt or unreadable") from exc
    if not raw_text.strip():
        raise ValueError("The PDF contains no extractable text")
    if len(raw_text) > MAX_PAPER_CHARACTERS:
        raise ValueError("The PDF contains too much text to process")
    paper_context = {
        "file_name": file_name,
        "file_size": len(file_bytes),
        "raw_text": raw_text,
        "source": "uploaded_pdf",
    }
    paper_id = session_store.save_paper(session_id, paper_context)
    try:
        chunk_count = index_paper_text(paper_id, session_id, raw_text, file_name)
        if chunk_count < 1:
            raise ValueError("The PDF could not be indexed")
    except Exception:
        session_store.delete_paper(paper_id)
        from backend.storage.rag_store import delete_paper_chunks
        try:
            delete_paper_chunks(paper_id)
        except Exception:
            logger.exception("Could not clean failed paper index: paper_id=%s session_id=%s", paper_id, session_id)
        raise

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
