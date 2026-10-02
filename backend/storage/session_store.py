from __future__ import annotations

import sqlite3
import json
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "sidekick.db"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        legacy_user_id = ensure_legacy_user(conn)

        legacy_table = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'session'
            """
        ).fetchone()
        if legacy_table is not None:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions(id, title, created_at)
                SELECT id, title, created_at
                FROM session
                """
            )

        ensure_sessions_user_id(conn, legacy_user_id)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_requests (
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                response TEXT NOT NULL,
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                PRIMARY KEY (session_id, request_id)
            )
        """)


def ensure_legacy_user(conn: sqlite3.Connection) -> int:
    legacy_user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        ("legacy@local",),
    ).fetchone()
    if legacy_user is not None:
        return int(legacy_user["id"])

    cursor = conn.execute(
        """
        INSERT INTO users(email, password_hash, created_at)
        VALUES (?, ?, ?)
        """,
        ("legacy@local", "legacy-migrated-account", utc_now()),
    )
    return int(cursor.lastrowid)


def ensure_sessions_user_id(conn: sqlite3.Connection, legacy_user_id: int) -> None:
    columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
    column_names = {column["name"] for column in columns}
    if "user_id" not in column_names:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
    conn.execute(
        """
        UPDATE sessions
        SET user_id = ?
        WHERE user_id IS NULL
        """,
        (legacy_user_id,),
    )


def create_user(email: str, password_hash: str) -> dict[str, Any]:
    created_at = utc_now()
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            INSERT INTO users(email, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (email, password_hash, created_at),
        )
        return {"id": int(cursor.lastrowid), "email": email, "created_at": created_at}


def get_user_with_password(email: str) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, email, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_session(user_id: int, session_id: str, title: str) -> dict[str, Any]:
    created_at = utc_now()
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO sessions(id, user_id, title, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, title, created_at),
        )
    return {"id": session_id, "title": title, "created_at": created_at}


def list_sessions(user_id: int) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at
            FROM sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: str, user_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, title, created_at
            FROM sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def update_session_title(
    session_id: str, user_id: int, title: str
) -> dict[str, Any] | None:
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET title = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, session_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            """
            SELECT id, title, created_at
            FROM sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def set_initial_session_title(session_id: str, title: str) -> bool:
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET title = ?
            WHERE id = ?
              AND title = 'New Research Session'
              AND NOT EXISTS (
                  SELECT 1 FROM messages WHERE messages.session_id = sessions.id
              )
            """,
            (title, session_id),
        )
    return cursor.rowcount > 0


def delete_session(session_id: str, user_id: int) -> bool:
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            DELETE FROM sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        )
    return cursor.rowcount > 0


def save_message(session_id: str, role: str, content: str) -> dict[str, Any]:
    created_at = utc_now()
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO messages(session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, created_at),
        )
    return {"role": role, "content": content, "created_at": created_at}


def get_messages(session_id: str) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent_messages(session_id: str, limit: int = 6) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_paper(session_id: str, paper_context: dict[str, Any]) -> int:
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            INSERT INTO papers (
                session_id, file_name, file_size, raw_text, source, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                paper_context["file_name"],
                paper_context["file_size"],
                paper_context["raw_text"],
                paper_context["source"],
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def get_papers(session_id: str) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, file_name, file_size, source, created_at,
                   CASE WHEN source = 'online_discovery' THEN raw_text END AS discovery_json
            FROM papers
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    return [paper_metadata(row) for row in rows]


def paper_metadata(row: sqlite3.Row) -> dict[str, Any]:
    paper = dict(row)
    text = paper.pop("discovery_json", None)
    if text:
        try:
            metadata = json.loads(text)
            if isinstance(metadata, dict):
                for key in ("title", "authors", "year", "summary", "url", "relevance", "relevance_reason"):
                    if key in metadata:
                        paper[key] = metadata[key]
        except (ValueError, TypeError):
            pass
    return paper


def save_discovered_paper(session_id: str, metadata: dict[str, Any]) -> int:
    """Reuse paper URLs within a session, including records from older versions."""
    text = json.dumps(metadata)
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, raw_text FROM papers WHERE session_id = ? AND source = 'online_discovery'",
            (session_id,),
        ).fetchall()
        for row in rows:
            try:
                existing = json.loads(row["raw_text"])
            except (ValueError, TypeError):
                continue
            if isinstance(existing, dict) and existing.get("url") == metadata["url"]:
                conn.execute("UPDATE papers SET file_name = ?, file_size = ?, raw_text = ? WHERE id = ?",
                             (metadata["title"], len(text.encode()), text, row["id"]))
                return int(row["id"])
        cursor = conn.execute(
            "INSERT INTO papers(session_id, file_name, file_size, raw_text, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, metadata["title"], len(text.encode()), text, "online_discovery", utc_now()),
        )
        return int(cursor.lastrowid)


def delete_paper(paper_id: int) -> None:
    with closing(get_connection()) as conn, conn:
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))


def get_paper(paper_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT papers.id, papers.session_id, papers.file_name, papers.file_size, papers.source, papers.created_at,
                   CASE WHEN papers.source = 'online_discovery' THEN papers.raw_text END AS discovery_json
            FROM papers
            WHERE papers.id = ?
            """,
            (paper_id,),
        ).fetchone()
    return paper_metadata(row) if row else None


def get_paper_text(paper_id: int) -> str | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT raw_text
            FROM papers
            WHERE id = ?
            """,
            (paper_id,),
        ).fetchone()
    return str(row["raw_text"]) if row else None


def save_report(session_id: str, title: str, content: str) -> int:
    with closing(get_connection()) as conn, conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (session_id, title, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, title, content, utc_now()),
        )
        return int(cursor.lastrowid)


def get_reports(session_id: str) -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, title, content, created_at
            FROM reports
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report(report_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, session_id, title, content, created_at
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        ).fetchone()
    return dict(row) if row else None


def get_paper_for_user(paper_id: int, user_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT papers.id, papers.session_id, papers.file_name, papers.file_size, papers.source, papers.created_at,
                   CASE WHEN papers.source = 'online_discovery' THEN papers.raw_text END AS discovery_json
            FROM papers
            JOIN sessions ON sessions.id = papers.session_id
            WHERE papers.id = ? AND sessions.user_id = ?
            """,
            (paper_id, user_id),
        ).fetchone()
    return paper_metadata(row) if row else None


def get_chat_request(session_id: str, request_id: str, fingerprint: str) -> dict | None:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM chat_requests WHERE session_id = ? AND request_id = ?",
                           (session_id, request_id)).fetchone()
    if row is None:
        return None
    if row["fingerprint"] != fingerprint:
        raise ValueError("This request ID was already used for different input")
    return {"response": row["response"], "report_id": row["report_id"]}


def save_chat_result(session_id: str, prompt: str, response: str, title: str,
                     request_id: str | None, fingerprint: str) -> dict:
    """Commit a completed turn, its report, and retry record together."""
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if request_id:
            row = conn.execute("SELECT * FROM chat_requests WHERE session_id = ? AND request_id = ?",
                               (session_id, request_id)).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise ValueError("This request ID was already used for different input")
                return {"response": row["response"], "report_id": row["report_id"]}
        conn.execute("""UPDATE sessions SET title = ? WHERE id = ? AND title = 'New Research Session'
                        AND NOT EXISTS (SELECT 1 FROM messages WHERE session_id = ?)""",
                     (title, session_id, session_id))
        created_at = utc_now()
        conn.executemany("INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                         [(session_id, "user", prompt, created_at), (session_id, "assistant", response, created_at)])
        cursor = conn.execute("INSERT INTO reports(session_id, title, content, created_at) VALUES (?, ?, ?, ?)",
                              (session_id, prompt[:80], response, created_at))
        report_id = int(cursor.lastrowid)
        if request_id:
            conn.execute("INSERT INTO chat_requests VALUES (?, ?, ?, ?, ?)",
                         (session_id, request_id, fingerprint, response, report_id))
    return {"response": response, "report_id": report_id}


def get_report_for_user(report_id: int, user_id: int) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT reports.id, reports.session_id, reports.title, reports.content, reports.created_at
            FROM reports
            JOIN sessions ON sessions.id = reports.session_id
            WHERE reports.id = ? AND sessions.user_id = ?
            """,
            (report_id, user_id),
        ).fetchone()
    return dict(row) if row else None
