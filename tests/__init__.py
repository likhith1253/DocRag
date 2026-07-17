import requests
import llm.ollama_backend
import storage.vector_store

# 1. Force tests to use the test Qdrant storage path to avoid locks on the production DB
cfg = storage.vector_store._get_config()
cfg["qdrant_path"] = "./test_qdrant_storage"

# 2. Redirect requests.Session.post to llm.ollama_backend.requests.post to support existing mocks
requests.Session.post = lambda self, *args, **kwargs: llm.ollama_backend.requests.post(*args, **kwargs)
