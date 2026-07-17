import os
import json
import unittest
from unittest.mock import patch, MagicMock
from agents.orchestrator import answer, LOGS_PATH

class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        from storage.vector_store import VectorStoreManager
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        # Remove logs if exist for clean verification
        if os.path.exists(LOGS_PATH):
            os.remove(LOGS_PATH)

    def tearDown(self):
        from storage.vector_store import VectorStoreManager
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        if os.path.exists(LOGS_PATH):
            os.remove(LOGS_PATH)

    @patch('storage.vector_store.VectorStoreManager.search')
    @patch('agents.code_agent.generate')
    @patch('agents.data_agent.generate')
    @patch('agents.reasoning_agent.generate')
    def test_e2e_flow_and_logging(self, mock_reasoning, mock_data, mock_code, mock_search):
        import numpy as np
        # Mock vector search to return proper (chunks, timing) tuple
        # retrieve_node unpacks: chunks, vector_timing = v_manager.search(...)
        mock_chunks = [
            {
                "content": "db = Database()",
                "metadata": {
                    "hash": "h123",
                    "file": "db.py",
                    "class": None,
                    "function": "init_db",
                    "language": "python",
                    "repository": "repo",
                    "branch": "main",
                    "lines": "1-2",
                    "timestamp": "2026-07-06"
                },
                "score": 0.9,
                "id": "mock-id-1",
            }
        ]
        mock_timing = {
            "embedding_ms": 0.0,
            "qdrant_ms": 0.0,
            "query_vector": np.zeros(768, dtype=np.float32),
        }
        mock_search.return_value = (mock_chunks, mock_timing)
        
        # Mock LLM generation
        mock_code.return_value = "The database is initialized in db.py."
        mock_data.return_value = "The database is initialized in db.py."
        mock_reasoning.return_value = "The database is initialized in db.py."
        
        # Call orchestrator — answer() returns (answer_str, latency_breakdown)
        query = "Show class definition for VectorStoreManager."
        ans, latency_breakdown = answer(query)
        
        # Asserts
        self.assertEqual(ans, "The database is initialized in db.py.")
        self.assertTrue(os.path.exists(LOGS_PATH), "Log file was not created.")
        
        # Verify log format
        with open(LOGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        self.assertEqual(len(lines), 1)
        log_entry = json.loads(lines[0])
        
        self.assertEqual(log_entry["question"], query)
        self.assertEqual(log_entry["agent"], "code_agent")
        self.assertEqual(log_entry["answer"], ans)
        self.assertIn("latency", log_entry)
        self.assertIn("memory", log_entry)

    def test_empty_query(self):
        # answer() returns (answer_str, latency_breakdown)
        ans, _ = answer("")
        self.assertEqual(ans, "Query is empty.")
        
        # Verify it logged
        with open(LOGS_PATH, "r", encoding="utf-8") as f:
            log_entry = json.loads(f.read().strip())
        self.assertEqual(log_entry["question"], "")
        self.assertEqual(log_entry["answer"], "Query is empty.")

    def test_malformed_query(self):
        # answer() returns (answer_str, latency_breakdown)
        ans, _ = answer(1234)
        self.assertEqual(ans, "Malformed query.")

if __name__ == "__main__":
    unittest.main()
