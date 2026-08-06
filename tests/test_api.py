import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["system"], "DocumentRAG")
        self.assertIn("backend", data)

    @patch('api.main.orchestrator.answer')
    def test_query(self, mock_answer):
        mock_answer.return_value = ("The project uses tree-sitter.", {"total_ms": 1.0}, [], [])
        
        response = self.client.post("/query", json={"question": "What parser does it use?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "The project uses tree-sitter.")

if __name__ == "__main__":
    unittest.main()
