"""eval.benchmark.systems — Concrete system adapters."""
from .codegraphrag import CodeGraphRAGSystem
from .vector_only import VectorOnlySystem
from .no_kg import NoKGSystem
from .no_ast import NoASTSystem
from .single_agent import SingleAgentSystem
from .simple_rag import SimpleRAGSystem
from .bm25 import BM25System
from .hybrid import HybridSystem

__all__ = [
    "CodeGraphRAGSystem",
    "VectorOnlySystem",
    "NoKGSystem",
    "NoASTSystem",
    "SingleAgentSystem",
    "SimpleRAGSystem",
    "BM25System",
    "HybridSystem",
]

# Registry: maps config YAML "class" field to system class
SYSTEM_REGISTRY: dict = {
    "eval.benchmark.systems.codegraphrag.CodeGraphRAGSystem": CodeGraphRAGSystem,
    "eval.benchmark.systems.vector_only.VectorOnlySystem": VectorOnlySystem,
    "eval.benchmark.systems.no_kg.NoKGSystem": NoKGSystem,
    "eval.benchmark.systems.no_ast.NoASTSystem": NoASTSystem,
    "eval.benchmark.systems.single_agent.SingleAgentSystem": SingleAgentSystem,
    "eval.benchmark.systems.simple_rag.SimpleRAGSystem": SimpleRAGSystem,
    "eval.benchmark.systems.bm25.BM25System": BM25System,
    "eval.benchmark.systems.hybrid.HybridSystem": HybridSystem,
}


def load_system(class_path: str, config_overrides: dict = None) -> "RetrievalSystem":
    """
    Instantiate a system by its fully-qualified class path.

    Parameters
    ----------
    class_path : str
        e.g. "eval.benchmark.systems.bm25.BM25System"
    config_overrides : dict, optional
        Per-experiment config overrides (applied on top of config.yaml).
    """
    from eval.benchmark.interface import RetrievalSystem
    cls = SYSTEM_REGISTRY.get(class_path)
    if cls is None:
        raise ValueError(
            f"Unknown system class: '{class_path}'. "
            f"Registered: {list(SYSTEM_REGISTRY.keys())}"
        )
    return cls(config_overrides=config_overrides or {})
