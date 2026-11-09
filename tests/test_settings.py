from settings import load_settings


def test_nested_environment_overrides_are_validated(tmp_path):
    config = tmp_path / "settings.yaml"
    config.write_text("generation:\n  temperature: 0.4\n", encoding="utf-8")
    loaded = load_settings(config, {
        "DOCRAG__GENERATION__TEMPERATURE": "0",
        "DOCRAG__RETRIEVAL__RERANK_TOP_K": "5",
        "DOCRAG__DEFAULT_COLLECTION_NAME": "docs",
    })
    assert loaded.generation.temperature == 0.0
    assert loaded.retrieval.rerank_top_k == 5
    assert loaded.default_collection_name == "docs"


def test_invalid_setting_type_fails_early():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        load_settings(environ={"DOCRAG__PORTS__API": "not-a-port"})
