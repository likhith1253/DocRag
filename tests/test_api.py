import unittest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

class TestAPI(unittest.TestCase):
    def _make_fake_backend(self, *, loaded=True):
        class FakeBackend:
            def __init__(self, is_loaded: bool):
                self.model = object() if is_loaded else None
                self.tokenizer = object() if is_loaded else None
                self.model_name = "fake-model"
                self.device = "cuda"
                self.dtype_str = "float16"
                self.gpu_name = "Fake GPU"

            def ensure_loaded(self):
                self.model = object()
                self.tokenizer = object()

        return FakeBackend(loaded)

    def test_health(self):
        fake_backend = self._make_fake_backend(loaded=True)
        with patch("llm.backend_factory.get_backend", return_value=fake_backend):
            with TestClient(app) as client:
                response = client.get("/health")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["system"], "DocumentRAG")
                self.assertIn("backend", data)
                self.assertEqual(data["backend"]["backend_class"], "FakeBackend")
                self.assertEqual(data["backend"]["backend_object_id"], id(fake_backend))
                self.assertTrue(data["backend"]["model_loaded"])
                self.assertEqual(data["backend"]["model_name"], "fake-model")
                self.assertEqual(data["backend"]["device"], "cuda")

    def test_startup_waits_for_backend_load_before_health(self):
        class SlowBackend:
            def __init__(self):
                self.model = None
                self.tokenizer = None
                self.model_name = "fake-model"
                self.device = "cpu"
                self.dtype_str = "float32"
                self.gpu_name = "N/A"
                self.ensure_loaded_called = False

            def ensure_loaded(self):
                time.sleep(0.15)
                self.model = object()
                self.tokenizer = object()
                self.ensure_loaded_called = True

        slow_backend = SlowBackend()
        with patch("llm.backend_factory.get_backend", return_value=slow_backend):
            with TestClient(app) as client:
                self.assertTrue(slow_backend.ensure_loaded_called)
                self.assertIsNotNone(slow_backend.model)
                self.assertIsNotNone(slow_backend.tokenizer)
                response = client.get("/health")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(data["backend"]["loaded"])
                self.assertTrue(data["backend"]["model_loaded"])
                self.assertEqual(data["backend"]["backend_object_id"], id(slow_backend))

    @patch('api.main.orchestrator.answer')
    def test_query(self, mock_answer):
        mock_answer.return_value = ("The project uses tree-sitter.", {"total_ms": 1.0}, [], [])
        fake_backend = self._make_fake_backend(loaded=True)
        with patch("llm.backend_factory.get_backend", return_value=fake_backend):
            with TestClient(app) as client:
                response = client.post("/query", json={"question": "What parser does it use?"})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["answer"], "The project uses tree-sitter.")

if __name__ == "__main__":
    unittest.main()
