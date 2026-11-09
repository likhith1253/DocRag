from llm.cache import cache_key, read_cached, write_cached


def test_cache_key_tracks_model_prompt_and_decoding():
    base = cache_key("model-a", "prompt", {"temperature": 0, "seed": 1})
    assert base == cache_key("model-a", "prompt", {"seed": 1, "temperature": 0})
    assert base != cache_key("model-b", "prompt", {"temperature": 0, "seed": 1})
    assert base != cache_key("model-a", "other", {"temperature": 0, "seed": 1})
    assert base != cache_key("model-a", "prompt", {"temperature": 0, "seed": 2})


def test_content_addressed_cache_roundtrip():
    key = cache_key("unit-test", "cache test", {"temperature": 0})
    write_cached(key, "cached output")
    assert read_cached(key) == "cached output"


def test_generate_uses_cache_and_force_override(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import llm.backend as llm_backend
    import llm.backend_factory as backend_factory
    import llm.cache as cache_module

    settings = SimpleNamespace(cache_dir=str(tmp_path), log_dir=str(tmp_path), generation=SimpleNamespace(num_predict=8))
    monkeypatch.setattr(cache_module, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_backend, "_load_config", lambda: {
        "doc_agent_model": "model-test",
        "llm_backend": "mock",
        "generation": {"num_predict": 8, "temperature": 0, "seed": 4},
    })

    class Backend:
        calls = 0
        def generate(self, prompt, model, request_id=None, answer_depth=None):
            self.calls += 1
            return f"response-{self.calls}"

    fake_backend = Backend()
    monkeypatch.setattr(backend_factory, "get_backend", lambda: fake_backend)
    first = llm_backend.generate("prompt", "doc_agent_model", answer_depth="DETAILED")
    second = llm_backend.generate("prompt", "doc_agent_model", answer_depth="DETAILED")
    assert first == second == "response-1"
    assert fake_backend.calls == 1

    monkeypatch.setenv("DOCRAG_FORCE_GENERATION", "1")
    forced = llm_backend.generate("prompt", "doc_agent_model", answer_depth="DETAILED")
    assert forced == "response-2"
    assert fake_backend.calls == 2
