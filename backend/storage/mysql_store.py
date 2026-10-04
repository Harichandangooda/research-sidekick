"""Small MySQL adapter for the existing parameterized storage queries."""
from __future__ import annotations

import os
import sqlite3

import pymysql


class Connection:
    def __init__(self):
        self.raw = pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.getenv("MYSQL_DATABASE", "research_sidekick"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=30,
            write_timeout=30,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.raw.rollback() if exc_type else self.raw.commit()

    def close(self):
        self.raw.close()

    def execute(self, sql, params=()):
        # The only explicit BEGINs in the existing store serialize writes to a
        # session. Lock that session in MySQL to preserve the same retry behavior.
        cursor = self.raw.cursor()
        try:
            if sql.strip() == "BEGIN IMMEDIATE":
                self.raw.begin()
            else:
                if sql.lstrip().startswith("SELECT") and (
                    "FROM chat_requests WHERE session_id" in sql
                    or "SELECT id, raw_text FROM papers WHERE session_id" in sql
                ):
                    cursor.execute("SELECT id FROM sessions WHERE id = %s FOR UPDATE", (params[0],))
                cursor.execute(sql.replace("?", "%s"), params)
        except pymysql.IntegrityError as exc:
            cursor.close()
            raise sqlite3.IntegrityError(str(exc)) from exc
        return cursor

    def executemany(self, sql, params):
        cursor = self.raw.cursor()
        cursor.executemany(sql.replace("?", "%s"), params)
        return cursor


def init_db():
    from contextlib import closing
    from pathlib import Path

    with closing(Connection()) as conn, conn:
        for statement in Path(__file__).with_name("mysql_schema.sql").read_text().split(";"):
            if statement.strip():
                conn.execute(statement)
