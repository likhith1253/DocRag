import os
import unittest
from unittest.mock import patch, MagicMock

class TestLLMBackends(unittest.TestCase):
    def setUp(self):
        from llm.backend_factory import reset_backend
        reset_backend()

    def tearDown(self):
        from llm.backend_factory import reset_backend
        reset_backend()
        if "LLM_BACKEND" in os.environ:
            del os.environ["LLM_BACKEND"]

    def test_default_backend_factory_selection(self):
        from llm.backend_factory import get_backend
        from llm.transformers_backend import HFTransformersBackend
        
        backend = get_backend()
        self.assertIsInstance(backend, HFTransformersBackend)

    def test_ollama_backend_factory_selection(self):
        os.environ["LLM_BACKEND"] = "ollama"
        from llm.backend_factory import get_backend
        from llm.ollama_backend import OllamaBackend
        
        backend = get_backend()
        self.assertIsInstance(backend, OllamaBackend)

    def test_transformers_backend_factory_selection(self):
        os.environ["LLM_BACKEND"] = "transformers"
        from llm.backend_factory import get_backend
        from llm.transformers_backend import HFTransformersBackend
        
        backend = get_backend()
        self.assertIsInstance(backend, HFTransformersBackend)

    def test_ollama_backend_generation(self):
        from llm.ollama_backend import OllamaBackend
        
        backend = OllamaBackend()
        with patch.object(backend._session, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "Test Ollama Response"}
            mock_post.return_value = mock_resp
            
            out = backend.generate("Hello", "qwen2.5:3b-instruct")
            self.assertEqual(out, "Test Ollama Response")

    def test_transformers_backend_generation(self):
        from llm.transformers_backend import HFTransformersBackend
        import torch

        with patch("transformers.AutoTokenizer.from_pretrained") as mock_tok, \
             patch("transformers.AutoModelForCausalLM.from_pretrained") as mock_model:
            
            mock_tok_inst = MagicMock()
            mock_tok_inst.pad_token_id = 0
            mock_tok_inst.eos_token_id = 2
            mock_tok_inst.apply_chat_template.return_value = "<user>Hello"
            mock_tok_inst.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
            mock_tok_inst.decode.return_value = "Test Transformers Response"
            mock_tok.return_value = mock_tok_inst
            
            mock_model_inst = MagicMock()
            mock_model_inst.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])
            mock_model.return_value = mock_model_inst

            backend = HFTransformersBackend(model_name="Qwen/Qwen2.5-3B-Instruct")
            out = backend.generate("Hello", "Qwen/Qwen2.5-3B-Instruct")
            self.assertEqual(out, "Test Transformers Response")

if __name__ == "__main__":
    unittest.main()
