import os
import unittest
from unittest.mock import patch, MagicMock
from llm.backend import generate

class TestPhase0(unittest.TestCase):
    def setUp(self):
        os.environ["DISABLE_PROMPT_CACHE"] = "1"

    def tearDown(self):
        if "DISABLE_PROMPT_CACHE" in os.environ:
            del os.environ["DISABLE_PROMPT_CACHE"]

    @patch('llm.backend_factory.get_backend')
    def test_generate_mocked(self, mock_get_backend):
        mock_backend = MagicMock()
        mock_backend.generate.return_value = "Mocked response from LLM backend"
        mock_get_backend.return_value = mock_backend
        
        result = generate("hello_test_prompt_unique", model_key="doc_agent_model")
        
        self.assertEqual(result, "Mocked response from LLM backend")
        mock_backend.generate.assert_called_once()

if __name__ == '__main__':
    unittest.main()
