import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        class FakeBackend:
            def __init__(self):
                self.model = object()
                self.tokenizer = object()
                self.model_name = "fake-model"
                self.device = "cuda"
                self.dtype_str = "float16"
                self.gpu_name = "Fake GPU"

            def ensure_loaded(self):
                return None

        self.fake_backend = FakeBackend()
        self.get_backend_patcher = patch("llm.backend_factory.get_backend", return_value=self.fake_backend)
        self.mock_get_backend = self.get_backend_patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.get_backend_patcher.stop()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["system"], "DocumentRAG")
        self.assertIn("backend", data)
        self.assertEqual(data["backend"]["backend_class"], "FakeBackend")
        self.assertEqual(data["backend"]["backend_object_id"], id(self.fake_backend))
        self.assertTrue(data["backend"]["model_loaded"])
        self.assertEqual(data["backend"]["model_name"], "fake-model")
        self.assertEqual(data["backend"]["device"], "cuda")

    @patch('api.main.orchestrator.answer')
    def test_query(self, mock_answer):
        mock_answer.return_value = ("The project uses tree-sitter.", {"total_ms": 1.0}, [], [])
        
        response = self.client.post("/query", json={"question": "What parser does it use?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "The project uses tree-sitter.")

if __name__ == "__main__":
    unittest.main()
