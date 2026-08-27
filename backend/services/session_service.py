from __future__ import annotations

import uuid

from backend.services.rag_service import delete_session_index
from backend.storage import session_store


def create_research_session(user_id: int, title: str = "New Research Session") -> dict:
    return session_store.create_session(user_id, str(uuid.uuid4()), title)


def list_research_sessions(user_id: int) -> list[dict]:
    return session_store.list_sessions(user_id)


def get_research_session(session_id: str, user_id: int) -> dict | None:
    return session_store.get_session(session_id, user_id)


def rename_research_session(session_id: str, user_id: int, title: str) -> dict | None:
    return session_store.update_session_title(session_id, user_id, title)


def delete_research_session(session_id: str, user_id: int) -> bool:
    if session_store.get_session(session_id, user_id) is None:
        return False
    delete_session_index(session_id)
    return session_store.delete_session(session_id, user_id)


def get_chat_history(session_id: str) -> list[dict]:
    return session_store.get_messages(session_id)
