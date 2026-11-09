import os
import requests
from llm.backend_factory import LLMBackend

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
class OllamaBackend(LLMBackend):
    def __init__(self):
        self._session = requests.Session()
        self._gen_config = self._load_gen_config()
        
        from settings import get_settings
        self.model_name = os.environ.get("LLM_MODEL") or os.environ.get("OLLAMA_MODEL") or get_settings().ollama_model
        print("=" * 40)
        print(f"LLM Backend : ollama")
        print(f"Model       : {self.model_name}")
        print("=" * 40)

    def _load_gen_config(self):
        from settings import get_config_dict
        return get_config_dict()

    def generate(self, prompt: str, model: str) -> str:
        """
        Call local Ollama generate API.
        """
        target_model = model
        if not target_model or "/" in target_model:
            target_model = self.model_name

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }
        options = {"num_predict": 1024, "temperature": 0.0, "top_p": 0.9}
        gen_cfg = self._gen_config.get("generation", {})
        if gen_cfg:
            options.update({key: gen_cfg[key] for key in ("num_predict", "temperature", "top_p", "top_k", "seed", "repetition_penalty") if key in gen_cfg})
        payload["options"] = options

        try:
            response = self._session.post(OLLAMA_URL, json=payload, timeout=600)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API request failed: {e}")

    def generate_stream(self, prompt: str, model: str):
        """
        Stream text response from local Ollama generate API.
        """
        target_model = model
        if not target_model or "/" in target_model:
            target_model = self.model_name

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": True,
        }
        options = {"num_predict": 1024, "temperature": 0.0, "top_p": 0.9}
        gen_cfg = self._gen_config.get("generation", {})
        if gen_cfg:
            options.update({key: gen_cfg[key] for key in ("num_predict", "temperature", "top_p", "top_k", "seed", "repetition_penalty") if key in gen_cfg})
        payload["options"] = options

        try:
            with self._session.post(OLLAMA_URL, json=payload, stream=True, timeout=300) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        import json
                        chunk = json.loads(line.decode("utf-8"))
                        text = chunk.get("response", "")
                        if text:
                            yield text
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama streaming failed: {e}")

# Standalone function for backward compatibility
def generate(prompt: str, model: str) -> str:
    from llm.backend_factory import get_backend
    backend = get_backend("ollama")
    return backend.generate(prompt, model)
