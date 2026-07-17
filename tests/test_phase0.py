import unittest
from unittest.mock import patch, MagicMock
from llm.backend import generate

class TestPhase0(unittest.TestCase):
    @patch('llm.ollama_backend.requests.post')
    def test_generate_mocked(self, mock_post):
        # Mock the Ollama API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Mocked response from Ollama"}
        mock_post.return_value = mock_response
        
        # Test code_agent_model key
        result = generate("hello", model_key="code_agent_model")
        
        self.assertEqual(result, "Mocked response from Ollama")
        
        # Verify that it was called with the correct model and payload
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['model'], "qwen2.5-coder:3b")
        self.assertEqual(kwargs['json']['prompt'], "hello")
        self.assertEqual(kwargs['json']['stream'], False)

if __name__ == '__main__':
    unittest.main()
