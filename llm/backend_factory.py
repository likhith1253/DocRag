import os
import threading
import yaml
from abc import ABC, abstractmethod
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def _load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}

class LLMBackend(ABC):
    @abstractmethod
    def generate(self, prompt: str, model: str) -> str:
        """Generate text response from prompt for the given model."""
        pass

    def generate_stream(self, prompt: str, model: str):
        """Stream text chunks from prompt for the given model."""
        yield self.generate(prompt, model)

_backend_instance = None
_backend_lock = threading.Lock()

def get_backend(backend_name: str = None) -> LLMBackend:
    """
    Get or initialize the singleton LLM backend instance.
    Backend selection precedence:
    1. Parameter 'backend_name' if provided
    2. Environment variable 'LLM_BACKEND'
    3. Configuration file 'config.yaml' (llm_backend)
    4. Default: 'transformers'
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    with _backend_lock:
        if _backend_instance is not None:
            return _backend_instance

        if not backend_name:
            backend_name = os.environ.get("LLM_BACKEND")
        if not backend_name:
            config = _load_config()
            backend_name = config.get("llm_backend", "transformers")

        backend_name = backend_name.lower().strip()

        if backend_name == "ollama":
            from llm.ollama_backend import OllamaBackend
            _backend_instance = OllamaBackend()
        elif backend_name in ["transformers", "huggingface", "hf"]:
            from llm.transformers_backend import HFTransformersBackend
            _backend_instance = HFTransformersBackend()
        else:
            raise ValueError(f"Unsupported LLM backend: '{backend_name}'. Supported backends are 'ollama' and 'transformers'.")

        return _backend_instance

def reset_backend():
    """Reset the backend singleton (useful for testing or switching backends)."""
    global _backend_instance
    _backend_instance = None
