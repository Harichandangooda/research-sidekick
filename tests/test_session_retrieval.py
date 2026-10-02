"""Exercise actual Chroma ranking and session filters without model downloads."""
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import chromadb
import numpy as np

from backend.storage import rag_store


class SessionRetrievalTests(unittest.TestCase):
    def test_old_and_new_chunks_share_ranking_and_exclude_other_sessions_and_failed_papers(self):
        client = chromadb.EphemeralClient()
        name = f"followup_{uuid4().hex}"
        collection = client.create_collection(name)
        self.addCleanup(client.delete_collection, name)
        vectors = {"Old evidence": [1.0, 0.0], "Unrelated evidence": [0.0, 1.0],
                   "New evidence": [0.99, 0.01], "Question": [1.0, 0.0]}
        model = Mock()
        model.encode.side_effect = lambda value: np.array([vectors[text] for text in value]
                                                         if isinstance(value, list) else vectors[value])
        with patch.object(rag_store, "get_collection", return_value=collection), \
             patch.object(rag_store, "get_embedding_model", return_value=model):
            rag_store.index_paper(1, "existing", "Old evidence", "A.pdf")
            rag_store.index_paper(2, "existing", "Unrelated evidence", "B.pdf")
            before = rag_store.retrieve_session_chunks("existing", "Question", [1, 2], top_k=1)
            self.assertEqual([chunk["paper_id"] for chunk in before], [1])
            rag_store.index_paper(3, "existing", "New evidence", "C.pdf")
            rag_store.index_paper(4, "other-session", "Old evidence", "other.pdf")
            rag_store.index_paper(5, "existing", "Old evidence", "failed.pdf")
            after = rag_store.retrieve_session_chunks("existing", "Question", [1, 2, 3], top_k=2)
            self.assertEqual([chunk["paper_id"] for chunk in after], [1, 3])
            self.assertEqual([chunk["text"] for chunk in after], ["Old evidence", "New evidence"])
            self.assertEqual(collection.count(), 5)

    def test_empty_candidates_do_not_load_model_or_query_store(self):
        with patch.object(rag_store, "get_collection") as collection, \
             patch.object(rag_store, "get_embedding_model") as model:
            self.assertEqual(rag_store.retrieve_session_chunks("session", "Question", []), [])
            collection.assert_not_called()
            model.assert_not_called()
