import os
import threading
from abc import ABC, abstractmethod

from settings import get_config_dict, get_settings

def _load_config():
    return get_config_dict()

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
    2. Validated application settings (including DOCRAG__LLM_BACKEND)
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    with _backend_lock:
        if _backend_instance is not None:
            return _backend_instance

        if not backend_name:
            backend_name = get_settings().llm_backend

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
