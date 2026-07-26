import os
import requests
import yaml
from pathlib import Path
from llm.backend_factory import LLMBackend

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

class OllamaBackend(LLMBackend):
    def __init__(self):
        self._session = requests.Session()
        self._gen_config = self._load_gen_config()
        
        model_name = os.environ.get("LLM_MODEL") or os.environ.get("OLLAMA_MODEL") or "qwen2.5:3b-instruct"
        print("=" * 40)
        print(f"LLM Backend : ollama")
        print(f"Model       : {model_name}")
        print("=" * 40)

    def _load_gen_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                return cfg.get("generation", {}) if cfg else {}
            except Exception:
                return {}
        return {}

    def generate(self, prompt: str, model: str) -> str:
        """
        Call local Ollama generate API.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if self._gen_config:
            if "num_predict" in self._gen_config:
                payload["num_predict"] = int(self._gen_config["num_predict"])
            if "temperature" in self._gen_config:
                payload["temperature"] = float(self._gen_config["temperature"])
            if "top_p" in self._gen_config:
                payload["top_p"] = float(self._gen_config["top_p"])

        try:
            response = self._session.post(OLLAMA_URL, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API request failed: {e}")

    def generate_stream(self, prompt: str, model: str):
        """
        Stream text response from local Ollama generate API.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if self._gen_config:
            if "num_predict" in self._gen_config:
                payload["num_predict"] = int(self._gen_config["num_predict"])
            if "temperature" in self._gen_config:
                payload["temperature"] = float(self._gen_config["temperature"])
            if "top_p" in self._gen_config:
                payload["top_p"] = float(self._gen_config["top_p"])

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
