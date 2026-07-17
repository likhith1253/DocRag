import unittest
from unittest.mock import patch, MagicMock
from agents.reasoning_agent import run

class TestReasoningAgent(unittest.TestCase):
    @patch('llm.ollama_backend.requests.post')
    def test_run_returns_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Tree-sitter provides language-agnostic AST parsing with incremental updates."
        }
        mock_post.return_value = mock_response
        
        chunks = [
            {
                "content": "Code parsing: tree-sitter | Language-agnostic",
                "metadata": {"file": "PROJECT_SPEC.md", "class": None, "function": None,
                             "language": "markdown", "hash": "ghi789", "lines": "43-43"}
            }
        ]
        
        result = run("Why use tree-sitter over regex for code parsing?", chunks)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

if __name__ == "__main__":
    unittest.main()
