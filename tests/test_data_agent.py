import unittest
from unittest.mock import patch, MagicMock
from agents.data_agent import run

class TestDataAgent(unittest.TestCase):
    @patch('llm.backend_factory.get_backend')
    def test_run_returns_text(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.generate.return_value = "There are 56 files in the repository."
        mock_get_backend.return_value = mock_backend
        
        chunks = [
            {
                "content": "Processed 56 files, generated 73 chunks.",
                "metadata": {"file": "tests/test_integration.py", "class": None, "function": None,
                             "language": "python", "hash": "def456", "lines": "30-35"}
            }
        ]
        
        result = run("How many files were processed?", chunks)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

if __name__ == "__main__":
    unittest.main()
