"""Checks for dependency isolation and the new network storage configuration."""
import os
import sqlite3
import unittest
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pymysql
from fastapi.testclient import TestClient

from backend.main import app
from backend.storage import rag_store, session_store
from backend.storage.mysql_store import Connection


class DeploymentTests(unittest.TestCase):
    def test_concurrent_first_uploads_initialize_one_embedding_model(self):
        rag_store._load_embedding_model.cache_clear()
        self.addCleanup(rag_store._load_embedding_model.cache_clear)
        start = Barrier(4)
        factory = MagicMock(side_effect=lambda name: (time.sleep(0.05), object())[1])
        def load(_):
            start.wait(timeout=5)
            return rag_store.get_embedding_model()
        with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=factory)}):
            with ThreadPoolExecutor(max_workers=4) as workers:
                models = list(workers.map(load, range(4)))
        factory.assert_called_once_with(rag_store.EMBEDDING_MODEL)
        self.assertTrue(all(model is models[0] for model in models))

    def test_liveness_does_not_contact_dependencies(self):
        with patch.object(session_store, 'get_connection') as database, patch('backend.main.requests.get') as chroma:
            response = TestClient(app).get('/health/live')
        self.assertEqual(response.status_code, 200)
        database.assert_not_called()
        chroma.assert_not_called()

    def test_readiness_checks_both_dependencies_and_handles_outage(self):
        with patch.object(session_store, 'get_connection') as database, patch('backend.main.requests.get') as chroma:
            client = TestClient(app)
            self.assertEqual(client.get('/health/ready').status_code, 200)
            database.return_value.execute.assert_called_with('SELECT 1')
            chroma.assert_called_once_with('http://localhost:8001/api/v2/heartbeat', timeout=3)
            chroma.return_value.raise_for_status.side_effect = RuntimeError('unavailable')
            self.assertEqual(client.get('/health/ready').status_code, 503)
            database.side_effect = RuntimeError('unavailable')
            self.assertEqual(client.get('/health/ready').status_code, 503)

    def test_chroma_uses_configured_http_service(self):
        rag_store.get_client.cache_clear()
        self.addCleanup(rag_store.get_client.cache_clear)
        with patch.dict(os.environ, {'CHROMA_HOST': 'chroma-service', 'CHROMA_PORT': '8000'}), patch.object(rag_store.chromadb, 'HttpClient') as client:
            rag_store.get_client()
            client.assert_called_once_with(host='chroma-service', port=8000)

    def test_mysql_configuration_and_transaction_rollback(self):
        with patch.dict(os.environ, {'MYSQL_HOST': 'mysql-service', 'MYSQL_USER': 'sidekick', 'MYSQL_PASSWORD': 'test-only-password'}), patch('pymysql.connect') as connect:
            conn = session_store.get_connection()
            self.assertIsInstance(conn, Connection)
            self.assertEqual(connect.call_args.kwargs['host'], 'mysql-service')
            with self.assertRaises(RuntimeError):
                with conn:
                    raise RuntimeError('failed turn')
            conn.raw.rollback.assert_called_once()
            conn.raw.commit.assert_not_called()

    def test_mysql_preserves_retry_serialization_and_parameter_binding(self):
        conn = Connection.__new__(Connection)
        conn.raw = MagicMock()
        conn.execute('BEGIN IMMEDIATE')
        conn.raw.begin.assert_called_once()
        sql = 'SELECT * FROM chat_requests WHERE session_id = ? AND request_id = ?'
        conn.execute(sql, ('session', 'request'))
        self.assertEqual(conn.raw.cursor.return_value.execute.call_args_list[0].args,
                         ('SELECT id FROM sessions WHERE id = %s FOR UPDATE', ('session',)))
        self.assertEqual(conn.raw.cursor.return_value.execute.call_args_list[1].args,
                         (sql.replace('?', '%s'), ('session', 'request')))

    def test_duplicate_mysql_email_uses_existing_conflict_handling(self):
        conn = Connection.__new__(Connection)
        conn.raw = MagicMock()
        conn.raw.cursor.return_value.execute.side_effect = pymysql.IntegrityError(1062, 'duplicate email')
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute('INSERT INTO users VALUES (?)', ('duplicate',))
