import unittest
from unittest.mock import patch, MagicMock
from agents.code_agent import run

class TestCodeAgent(unittest.TestCase):
    @patch('llm.ollama_backend.requests.post')
    def test_run_returns_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "The load_repository function streams files."}
        mock_post.return_value = mock_response
        
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
