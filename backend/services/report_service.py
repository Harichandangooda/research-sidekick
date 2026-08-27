from __future__ import annotations

from backend.storage import session_store


def list_session_reports(session_id: str) -> list[dict]:
    return session_store.get_reports(session_id)


def get_saved_report(report_id: int) -> dict | None:
    return session_store.get_report(report_id)


def get_saved_report_for_user(report_id: int, user_id: int) -> dict | None:
    return session_store.get_report_for_user(report_id, user_id)
