import tempfile
import unittest
import json
import asyncio
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from io import BytesIO
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter
import jwt

from backend.main import app
from backend.services import discovery_service, sidekick_service
from backend.limits import MAX_AGENT_INPUT_CHARACTERS
from backend.storage import session_store


class StepOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.start_patch = lambda *a, **kw: self._patch(*a, **kw)
        self.start_patch("backend.storage.session_store.DB_PATH", Path(self.temp.name) / "test.db")
        self.start_patch("backend.auth.get_jwt_secret_key", return_value="deterministic-test-secret-with-32-bytes")
        self.index = self.start_patch("backend.services.paper_service.index_paper_text", return_value=2)
        self.parse = self.start_patch("backend.services.paper_service.extract_pdf_text", return_value="Uploaded paper text")
        self.cleanup_index = self.start_patch("backend.storage.rag_store.delete_paper_chunks")
        self.search = self.start_patch("backend.services.sidekick_service.discover_papers", return_value=[])
        self.analysis = self.start_patch("backend.services.sidekick_service.run_analysis", return_value=SimpleNamespace(final_output="Answer"))
        self.retrieve = self.start_patch("backend.services.sidekick_service.retrieve_relevant_chunks", return_value=["context"])
        self.retrieve_session = self.start_patch("backend.services.sidekick_service.retrieve_relevant_session_chunks",
            side_effect=lambda session_id, query, paper_ids, top_k: [{"paper_id": identifier, "text": "context"}
                                                                  for identifier in paper_ids[:top_k]])
        session_store.init_db()
        self.client = TestClient(app)
        auth = self.client.post("/auth/register", json={"email": "owner@example.com", "password": "password123"})
        self.assertEqual(auth.status_code, 200)
        self.headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
        self.session = self.client.post("/sessions", headers=self.headers).json()["id"]
        self.base = f"/sessions/{self.session}"

    def _patch(self, *args, **kwargs):
        p = patch(*args, **kwargs)
        value = p.start()
        self.addCleanup(p.stop)
        return value

    def upload(self, name="paper.pdf", content=b"%PDF-test", mime="application/pdf"):
        return self.client.post(self.base + "/papers", headers=self.headers, files={"file": (name, content, mime)})

    def chat(self, prompt, **kwargs):
        return self.client.post(self.base + "/chat", headers=self.headers, json={"prompt": prompt, **kwargs})

    def papers(self):
        return self.client.get(self.base + "/papers", headers=self.headers).json()

    def test_prompt_only_searches(self):
        self.assertEqual(self.chat("  graph neural networks  ").status_code, 200)
        self.search.assert_called_once_with(self.session, "graph neural networks")

    def test_prompt_with_single_and_multiple_files_does_not_search(self):
        for count in (1, 3):
            with self.subTest(count=count):
                for i in range(count):
                    self.assertEqual(self.upload(f"unrelated-{count}-{i}.pdf").status_code, 200)
                self.assertEqual(self.chat("Summarize these papers").status_code, 200)
                self.search.assert_not_called()
        self.assertEqual(len(self.papers()), 4)

    def test_files_without_prompt(self):
        for i in range(3):
            self.assertEqual(self.upload(f"paper-{i}.pdf").status_code, 200)
            for prompt in ("", " \n\t "):
                self.assertEqual(self.chat(prompt).status_code, 200)
        self.assertEqual(len(self.papers()), 3)
        self.search.assert_not_called()
        self.analysis.assert_not_called()

    def test_empty_input_never_processes(self):
        for prompt in ("", " \n\t "):
            response = self.chat(prompt)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], "Please enter a prompt or upload at least one file.")
        self.search.assert_not_called()
        self.analysis.assert_not_called()

    def test_external_research_exception(self):
        for count in (1, 2):
            self.upload(f"paper-{count}.pdf")
            for prompt in ("Find recent papers on transformers", "Search online for related studies", "Include external research"):
                with self.subTest(prompt=prompt, count=count):
                    self.search.reset_mock()
                    self.assertEqual(self.chat(prompt).status_code, 200)
                    self.search.assert_called_once_with(self.session, prompt)
        for prompt in ("Compare this approach with RAG", "Do not search online; summarize this paper", "Find the main contributions in these papers", "Search the uploaded papers for weaknesses"):
            self.search.reset_mock()
            self.chat(prompt)
            self.search.assert_not_called()

    def test_failed_uploads_do_not_trigger_search(self):
        self.assertEqual(self.upload(content=b"").status_code, 400)
        self.assertEqual(self.chat("Summarize", upload_attempted=True).status_code, 200)
        self.search.assert_not_called()

    def test_invalid_uploads(self):
        for name, content, mime in (("file.txt", b"text", "text/plain"), ("empty.pdf", b"", "application/pdf"), ("fake.pdf", b"garbage", "application/pdf")):
            self.assertEqual(self.upload(name, content, mime).status_code, 400)
        self.parse.side_effect = RuntimeError("corrupt")
        self.assertEqual(self.upload().status_code, 400)
        self.parse.side_effect = None
        self.parse.return_value = " \n "
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(self.papers(), [])
        self.index.assert_not_called()

    def test_real_parser_rejects_corrupt_and_textless_pdf(self):
        from backend.services.document_parser import extract_pdf_text
        self.parse.side_effect = extract_pdf_text
        self.assertEqual(self.upload(content=b"%PDF-corrupt").status_code, 400)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        stream = BytesIO()
        writer.write(stream)
        self.assertEqual(self.upload(content=stream.getvalue()).status_code, 400)
        self.assertEqual(self.papers(), [])

    def test_partial_failure_and_persistence(self):
        self.assertEqual(self.upload("first.pdf").status_code, 200)
        self.index.side_effect = RuntimeError("index unavailable")
        self.assertEqual(self.upload("failed.pdf").status_code, 500)
        self.cleanup_index.assert_called_once()
        self.index.side_effect = None
        self.assertEqual(self.upload("last.pdf").status_code, 200)
        # A fresh connection and DB initialization preserve only successful rows.
        session_store.init_db()
        self.assertEqual({p["file_name"] for p in self.papers()}, {"first.pdf", "last.pdf"})

    def test_zero_chunks_is_failure(self):
        self.index.return_value = 0
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(self.papers(), [])

    def test_coordinator_has_no_search_tool(self):
        from backend.agents import sidekick
        with patch.object(sidekick.Runner, "run_sync") as runner:
            sidekick.run_analysis("Summarize uploaded papers")
        agent = runner.call_args.args[0]
        self.assertNotIn("search_agent", [tool.name for tool in agent.tools])

    def test_authentication_and_ownership(self):
        login = self.client.post("/auth/login", json={"email": "owner@example.com", "password": "password123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.post("/auth/login", json={"email": "owner@example.com", "password": "incorrect"}).status_code, 401)
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            self.assertEqual(self.client.get(self.base + "/papers", headers=headers).status_code, 401)
        for subject, expiration in (("invalid-id", datetime.now(UTC) + timedelta(hours=1)), ("1", datetime.now(UTC) - timedelta(hours=1))):
            token = jwt.encode({"sub": subject, "email": "owner@example.com", "exp": expiration}, "deterministic-test-secret-with-32-bytes", algorithm="HS256")
            self.assertEqual(self.client.get(self.base + "/papers", headers={"Authorization": "Bearer " + token}).status_code, 401)
        other = self.client.post("/auth/register", json={"email": "other@example.com", "password": "password123"}).json()
        headers = {"Authorization": "Bearer " + other["access_token"]}
        self.assertEqual(self.client.post(self.base + "/chat", headers=headers, json={"prompt": "research"}).status_code, 404)
        self.assertEqual(self.client.post(self.base + "/papers", headers=headers, files={"file": ("x.pdf", b"%PDF-test", "application/pdf")}).status_code, 404)
        uploaded = self.upload().json()
        self.assertEqual(self.client.get(f"/papers/{uploaded['paper_id']}", headers=headers).status_code, 404)
        self.search.assert_not_called()

    def test_discovery_ranks_only_online_and_persists_top_five(self):
        self.upload("unrelated.pdf")
        candidates = [discovery_service.DiscoveredPaper(title=f"Paper {i}", authors="Author", year=2025, summary="Summary", url=f"https://example.org/{i}", relevance=i / 10, relevance_reason="Relevant") for i in range(8)]
        with patch.object(discovery_service.Runner, "run_sync", return_value=SimpleNamespace(final_output=discovery_service.SearchResults(papers=candidates))):
            saved = discovery_service.discover_papers(self.session, "topic")
        self.assertEqual([p["title"] for p in saved], [f"Paper {i}" for i in (7, 6, 5, 4, 3)])
        session_store.init_db()
        self.assertEqual(len(self.papers()), 6)
        self.assertIn("unrelated.pdf", [p["file_name"] for p in self.papers()])

    def test_online_selection_uses_saved_metadata_without_embeddings_or_search(self):
        metadata = {"title": "Online paper", "authors": "Author", "year": 2025, "summary": "Important evidence",
                    "url": "https://example.org/paper", "relevance": 0.9, "relevance_reason": "Relevant"}
        # The original JSON-only storage format must work without reindexing.
        paper_id = session_store.save_paper(self.session, {"file_name": metadata["title"], "file_size": 100,
            "raw_text": json.dumps(metadata), "source": "online_discovery"})
        listed = self.papers()[0]
        detail = self.client.get(f"/papers/{paper_id}", headers=self.headers).json()
        for key, value in metadata.items():
            self.assertEqual(listed[key], value)
            self.assertEqual(detail[key], value)
        self.assertNotIn("raw_text", detail)
        self.assertEqual(self.chat("Explain the paper", paper_id=paper_id).status_code, 200)
        context = self.analysis.call_args.args[0]
        self.assertIn("Important evidence", context)
        self.assertIn(metadata["url"], context)
        self.assertIn("full text has not been retrieved", context)
        self.retrieve.assert_not_called()
        self.search.assert_not_called()

    def test_discovery_reuses_urls_across_retries(self):
        paper = discovery_service.DiscoveredPaper(title="Paper", authors="Author", year=2025, summary="Summary",
             url="https://example.org/paper", relevance=0.8, relevance_reason="Relevant")
        with patch.object(discovery_service.Runner, "run_sync", return_value=SimpleNamespace(
                final_output=discovery_service.SearchResults(papers=[paper, paper]))):
            first = discovery_service.discover_papers(self.session, "topic")
            second = discovery_service.discover_papers(self.session, "topic")
        self.assertEqual(first[0]["id"], second[0]["id"])
        self.assertEqual(len(self.papers()), 1)

    def test_retrieval_selects_session_evidence_and_explicit_selection_is_respected(self):
        first = self.upload("first.pdf").json()["paper_id"]
        second = self.upload("second.pdf").json()["paper_id"]
        self.retrieve_session.side_effect = None
        self.retrieve_session.return_value = [{"paper_id": first, "text": "Relevant evidence"}]
        self.chat("Compare these papers")
        context = self.analysis.call_args.args[0]
        self.assertIn("first.pdf", context)
        self.assertNotIn("second.pdf", context)
        self.assertEqual(set(self.retrieve_session.call_args.args[2]), {first, second})
        self.retrieve.assert_not_called()
        self.chat("Analyze the active paper", paper_id=first)
        context = self.analysis.call_args.args[0].split("Recent Conversation:", 1)[-1]
        self.assertIn("Uploaded Paper: first.pdf", context)
        self.assertNotIn("Uploaded Paper: second.pdf", context)

    def test_agent_failure_leaves_no_partial_conversation_or_title(self):
        self.analysis.side_effect = RuntimeError("model unavailable")
        self.assertEqual(self.chat("Research topic").status_code, 500)
        self.assertEqual(session_store.get_messages(self.session), [])
        self.assertEqual(session_store.get_reports(self.session), [])
        session = self.client.get(self.base, headers=self.headers).json()
        self.assertEqual(session["title"], "New Research Session")

    def test_persistence_failure_rolls_back_messages_title_and_retry_record(self):
        request_id = str(uuid4())
        with closing(session_store.get_connection()) as conn, conn:
            conn.execute("CREATE TRIGGER fail_report BEFORE INSERT ON reports BEGIN SELECT RAISE(ABORT, 'report failed'); END")
        self.assertEqual(self.chat("Research topic", request_id=request_id).status_code, 500)
        self.assertEqual(session_store.get_messages(self.session), [])
        self.assertEqual(self.client.get(self.base, headers=self.headers).json()["title"], "New Research Session")
        with closing(session_store.get_connection()) as conn, conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_requests").fetchone()[0], 0)
            conn.execute("DROP TRIGGER fail_report")
        self.assertEqual(self.chat("Research topic", request_id=request_id).status_code, 200)
        self.assertEqual(len(session_store.get_messages(self.session)), 2)

    def test_successful_retries_and_conflicting_input(self):
        request_id = str(uuid4())
        first = self.chat("Research topic", request_id=request_id)
        session_store.init_db()
        second = self.chat("Research topic", request_id=request_id)
        self.assertEqual(first.json(), second.json())
        self.analysis.assert_called_once()
        self.search.assert_called_once()
        self.assertEqual(len(session_store.get_messages(self.session)), 2)
        self.assertEqual(len(session_store.get_reports(self.session)), 1)
        self.assertEqual(self.chat("Different topic", request_id=request_id).status_code, 400)

    def test_concurrent_duplicate_requests_execute_analysis_once(self):
        request_id = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(sidekick_service.run_chat, self.session, "Research topic", None, False, request_id)
                       for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(results[0], results[1])
        self.analysis.assert_called_once()
        self.assertEqual(len(session_store.get_reports(self.session)), 1)

    def test_upload_and_prompt_limits_reject_before_processing(self):
        with patch("backend.main.MAX_UPLOAD_BYTES", 10):
            self.assertEqual(self.upload(content=b"%PDF-" + b"x" * 10).status_code, 413)
        self.parse.assert_not_called()
        self.assertEqual(self.chat("x" * 10001).status_code, 422)
        self.analysis.assert_not_called()
        self.search.assert_not_called()

    def test_pdf_processing_runs_outside_the_event_loop(self):
        def extract(_):
            with self.assertRaises(RuntimeError):
                asyncio.get_running_loop()
            return "Paper text"
        self.parse.side_effect = extract
        self.assertEqual(self.upload().status_code, 200)

    def test_context_is_bounded_and_keeps_retrieved_evidence_and_current_prompt(self):
        identifiers = []
        for i in range(10):
            identifiers.append(self.upload(f"paper-{i}.pdf").json()["paper_id"])
        session_store.save_message(self.session, "assistant", "history " * 20000)
        self.retrieve_session.side_effect = None
        self.retrieve_session.return_value = [{"paper_id": identifier, "text": "context " * 10000}
                                              for identifier in identifiers[:5]]
        prompt = "Compare " + "x" * 9990
        self.assertEqual(self.chat(prompt).status_code, 200)
        context = self.analysis.call_args.args[0]
        self.assertLessEqual(len(context), MAX_AGENT_INPUT_CHARACTERS)
        self.assertIn(prompt, context)
        for i in range(5):
            self.assertIn(f"Uploaded Paper: paper-{i}.pdf", context)
        for i in range(5, 10):
            self.assertNotIn(f"Uploaded Paper: paper-{i}.pdf", context)
        self.assertIn("[Paper context truncated]", context)

    def test_explicit_search_adds_new_discovery_to_selected_upload(self):
        paper_id = self.upload().json()["paper_id"]
        def discover(session_id, prompt):
            metadata = {"title": "Related paper", "authors": "Author", "year": 2025, "summary": "External evidence",
                        "url": "https://example.org/related", "relevance": 0.9, "relevance_reason": "Relevant"}
            discovered_id = session_store.save_discovered_paper(session_id, metadata)
            return [{"id": discovered_id, **metadata}]
        self.search.side_effect = discover
        self.assertEqual(self.chat("Find related papers", paper_id=paper_id).status_code, 200)
        context = self.analysis.call_args.args[0]
        self.assertIn("Uploaded Paper: paper.pdf", context)
        self.assertIn("External evidence", context)

    def test_parser_page_and_text_limits(self):
        from backend.services.document_parser import extract_pdf_text
        with patch("backend.services.document_parser.PdfReader", return_value=SimpleNamespace(pages=[None] * 501)):
            with self.assertRaisesRegex(ValueError, "500 pages"):
                extract_pdf_text(b"pdf")
        page = SimpleNamespace(extract_text=lambda: "x" * 20)
        with patch("backend.services.document_parser.PdfReader", return_value=SimpleNamespace(pages=[page])), \
             patch("backend.services.document_parser.MAX_PAPER_CHARACTERS", 10):
            with self.assertRaisesRegex(ValueError, "too much text"):
                extract_pdf_text(b"pdf")

    def test_followups_accumulate_zero_one_and_multiple_uploads_and_new_reports(self):
        self.upload("A.pdf")
        self.upload("B.pdf")
        first = self.chat("Design an experiment plan").json()
        original = session_store.get_report(first["report_id"])
        expected = {"A.pdf", "B.pdf"}
        for names in ([], ["C.pdf"], ["D.pdf", "E.pdf"]):
            with self.subTest(names=names):
                analyses_before = self.analysis.call_count
                reports_before = len(session_store.get_reports(self.session))
                for name in names:
                    upload = self.upload(name)
                    self.assertEqual(upload.status_code, 200)
                    self.assertEqual(self.index.call_args.args[1], self.session)
                    expected.add(name)
                self.assertEqual(self.analysis.call_count, analyses_before)
                self.assertEqual(len(session_store.get_reports(self.session)), reports_before)
                response = self.chat("What evidence supports the method?", upload_attempted=bool(names))
                self.assertEqual(response.status_code, 200)
                self.assertNotEqual(response.json()["report_id"], first["report_id"])
                self.assertEqual(len(session_store.get_reports(self.session)), reports_before + 1)
                self.assertEqual(session_store.get_report(first["report_id"]), original)
                session_store.init_db()
                self.assertEqual({paper["file_name"] for paper in self.papers()}, expected)
                self.assertEqual({paper["session_id"] for paper in self.papers()}, {self.session})
                self.assertEqual(set(self.retrieve_session.call_args.args[2]), {paper["id"] for paper in self.papers()})
                self.assertEqual(len(self.client.get("/sessions", headers=self.headers).json()), 1)
        self.search.assert_not_called()

    def test_failed_followup_upload_preserves_old_papers_and_original_plan(self):
        self.upload("A.pdf")
        self.upload("B.pdf")
        first = self.chat("Design an experiment plan").json()
        original = session_store.get_report(first["report_id"])
        self.index.side_effect = RuntimeError("index failed")
        failure = self.upload("failed.pdf")
        self.assertEqual(failure.status_code, 500)
        self.assertIn("index failed", failure.json()["detail"])
        self.cleanup_index.assert_called_once()
        self.assertEqual({paper["file_name"] for paper in self.papers()}, {"A.pdf", "B.pdf"})
        self.assertEqual(self.analysis.call_count, 1)
        response = self.chat("Explain the evidence", upload_attempted=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session_store.get_report(first["report_id"]), original)
        self.assertNotEqual(response.json()["report_id"], first["report_id"])

    def test_followup_can_retrieve_both_old_and_new_papers_without_unrelated_papers(self):
        old = self.upload("A.pdf").json()["paper_id"]
        unrelated = self.upload("B.pdf").json()["paper_id"]
        self.chat("Design an experiment plan")
        new = self.upload("C.pdf").json()["paper_id"]
        self.retrieve_session.side_effect = None
        self.retrieve_session.return_value = [{"paper_id": old, "text": "Old relevant evidence"},
                                             {"paper_id": new, "text": "New relevant evidence"}]
        self.assertEqual(self.chat("What evidence supports the method?", upload_attempted=True).status_code, 200)
        self.assertEqual(set(self.retrieve_session.call_args.args[2]), {old, unrelated, new})
        context = self.analysis.call_args.args[0]
        self.assertIn("Uploaded Paper: A.pdf", context)
        self.assertIn("Uploaded Paper: C.pdf", context)
        self.assertIn("Old relevant evidence", context)
        self.assertIn("New relevant evidence", context)
        self.assertNotIn("Uploaded Paper: B.pdf", context)

    def test_empty_retrieval_does_not_add_every_paper_as_fallback(self):
        self.upload("A.pdf")
        self.upload("B.pdf")
        self.retrieve_session.side_effect = None
        self.retrieve_session.return_value = []
        self.assertEqual(self.chat("Explain the evidence").status_code, 200)
        self.assertNotIn("Uploaded Paper:", self.analysis.call_args.args[0])
        self.assertEqual(len(self.papers()), 2)


if __name__ == "__main__":
    unittest.main()
