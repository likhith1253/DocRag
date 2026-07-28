import unittest
from unittest.mock import patch, MagicMock
from agents.reasoning_agent import run

class TestReasoningAgent(unittest.TestCase):
    @patch('llm.backend_factory.get_backend')
    def test_run_returns_text(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.generate.return_value = "Tree-sitter provides language-agnostic AST parsing with incremental updates."
        mock_get_backend.return_value = mock_backend
        
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
