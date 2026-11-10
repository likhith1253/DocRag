"""Typed application settings loaded from YAML with ``DOCRAG__...`` overrides."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config.yaml"


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ChunkingConfig(ConfigModel):
    max_chunk_tokens: int = 1024
    overlap_tokens: int = 128
    strategy: str = "section_aware"


class EmbeddingConfig(ConfigModel):
    device: str = "cpu"
    batch_size: int = 32


class GenerationConfig(ConfigModel):
    num_predict: int = 256
    repetition_penalty: float = 1.0
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0


class RetrievalConfig(ConfigModel):
    vector_top_k: int = 40
    rerank_top_k: int = 8
    agent_chunk_cap: int = 8
    single_paper_rerank_candidates: int = 20
    multi_paper_rerank_candidates: int = 15
    mmr_lambda: float = 0.7
    use_graph: bool = False
    use_mmr: bool = True


class RouterConfig(ConfigModel):
    confidence_threshold: float = 0.6


class WorkerConfig(ConfigModel):
    parse_workers: int = 2
    qa_workers: int = 1


class IndexingConfig(ConfigModel):
    background_batch_size: int = 16


class PortConfig(ConfigModel):
    api: int = 9001
    ui: int = 8501


class Settings(ConfigModel):
    debug_mode: bool = False
    llm_backend: str = "transformers"
    hf_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    doc_agent_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_model_revision: str = "7ae557604adf67be50417f59c2c2f167def9a775"
    ollama_model: str = "qwen2.5:0.5b-instruct"
    embedding_model: str = "intfloat/e5-base-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    device: str = "cpu"
    qdrant_path: str = "qdrant_storage"
    default_collection_name: str = "chunks"
    collection_prefix: str = "collection_"
    log_dir: str = "logs"
    debug_dir: str = ".debug/current_query"
    registry_path: str = "registry.json"
    metadata_store_path: str = "metadata_store.json"
    metadata_dir: str = "metadata_storage"
    snapshot_dir: str = "snapshot_storage"
    repository_data_dir: str = "repositories"
    semantic_cache_path: str = "semantic_cache.db"
    embedding_cache_path: str = "embedding_cache.db"
    cache_dir: str = "cache"
    prompt_token_budget: int = 6144
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    workers: WorkerConfig = Field(default_factory=WorkerConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    ports: PortConfig = Field(default_factory=PortConfig)


def _parse_override(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _set_nested(target: dict[str, Any], parts: list[str], value: Any) -> None:
    current = target
    for part in parts[:-1]:
        found = next((key for key in current if key.lower() == part.lower()), part.lower())
        nested = current.get(found)
        if not isinstance(nested, dict):
            nested = {}
            current[found] = nested
        current = nested
    final = next((key for key in current if key.lower() == parts[-1].lower()), parts[-1].lower())
    current[final] = value


def load_settings(
    config_file: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load and validate YAML settings, then apply nested environment overrides."""
    env = os.environ if environ is None else environ
    configured_path = config_file or env.get("DOCRAG_CONFIG_FILE") or DEFAULT_CONFIG_FILE
    path = Path(configured_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as config_stream:
            loaded = yaml.safe_load(config_stream) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Configuration root must be a mapping: {path}")
        raw = loaded
    for name, value in env.items():
        prefix = "DOCRAG__"
        if name.upper().startswith(prefix):
            parts = [part.lower() for part in name[len(prefix):].split("__") if part]
            if parts:
                _set_nested(raw, parts, _parse_override(value))
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide validated settings object."""
    return load_settings()


def clear_settings_cache() -> None:
    """Clear the process cache; intended for tests and explicit reconfiguration."""
    get_settings.cache_clear()


def get_config_dict() -> dict[str, Any]:
    """Compatibility view for legacy call sites while they migrate to typed fields."""
    return get_settings().model_dump(mode="python")


def resolve_project_path(value: str | Path) -> Path:
    """Resolve a configured relative path from the repository root."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path
