import unittest
from unittest.mock import patch, MagicMock
from agents.code_agent import run

class TestCodeAgent(unittest.TestCase):
    @patch('llm.backend_factory.get_backend')
    def test_run_returns_text(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.generate.return_value = "The load_repository function streams files."
        mock_get_backend.return_value = mock_backend
        
        chunks = [
            {
                "content": "def load_repository(path):\n    for file in os.walk(path): yield file",
                "metadata": {"file": "ingestion/loader.py", "class": None, "function": "load_repository",
                             "language": "python", "hash": "abc", "lines": "1-2"}
            }
        ]
        
        result = run("What does load_repository do?", chunks)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

if __name__ == "__main__":
    unittest.main()
