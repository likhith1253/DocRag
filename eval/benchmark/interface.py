"""
eval.benchmark.interface
========================
Abstract pipeline interface that every evaluated system must implement.

Design rationale (Amendment 3):
  The BenchmarkEvaluator communicates with every system — CodeGraphRAG, all
  baselines, and any future system — exclusively through this interface.
  This guarantees:
    - Identical evaluation conditions (timing, memory measurement) for all systems.
    - No evaluator code paths depend on internal implementation details.
    - New systems can be registered without touching evaluator code.
    - Every system is interchangeable in experiment YAML configurations.

Research mapping:
  All 7 Research Questions. Every experiment uses RetrievalSystem.answer().
"""

from __future__ import annotations

import time
import tracemalloc
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """
    A single chunk returned by the retrieval step of any system.

    Attributes
    ----------
    content : str
        Raw text content of the chunk.
    file_path : str
        Normalized relative file path (e.g., "ingestion/chunker.py").
        Used for Recall@K matching against DatasetItem.relevant_sources.
        Must be consistently normalized across all systems.
    score : float
        Relevance score assigned by the retrieval system.
        Semantics differ per system (cosine similarity, BM25 score, etc.).
    metadata : dict
        System-specific metadata (language, class, function, lines, etc.).
    rank : int
        1-indexed rank in the returned list (set by the evaluator).
    """
    content: str
    file_path: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0

    def __post_init__(self):
        if not isinstance(self.file_path, str) or not self.file_path:
            raise ValueError(f"RetrievedChunk.file_path must be a non-empty string, got: {self.file_path!r}")
        if not isinstance(self.score, (int, float)):
            raise TypeError(f"RetrievedChunk.score must be numeric, got: {type(self.score)}")
        # Normalize path separators
        self.file_path = self.file_path.replace("\\", "/")


@dataclass
class SystemResponse:
    """
    Complete response from a system for a single query.

    The BenchmarkEvaluator populates latency_s and peak_memory_mb by
    wrapping system.answer() in its own timing/memory context. Systems
    must NOT attempt to set these — they are always overwritten.

    Attributes
    ----------
    question : str
        The original query string.
    answer : str
        Generated answer text.
    retrieved_chunks : list[RetrievedChunk]
        Ordered list of chunks used to generate the answer.
    latency_s : float
        Wall-clock time for the full answer() call in seconds.
        Set by the evaluator, not the system.
    peak_memory_mb : float
        Peak RSS memory increase during the call in MB.
        Set by the evaluator, not the system.
    agent : str
        Which agent was selected (for routing analysis). Use "" if no routing.
    config_snapshot : dict
        Exact configuration used for this query (from system.configuration()).
    error : str or None
        If the system raised an exception, the error message is stored here
        and answer is set to "". Metrics are computed on empty answer.
    system_name : str
        Name of the system that produced this response.
    run_index : int
        Which repetition (0-indexed) this response belongs to.
    """
    question: str
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    latency_s: float = 0.0
    peak_memory_mb: float = 0.0
    agent: str = ""
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    system_name: str = ""
    run_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-serializable dict for JSONL logging."""
        return {
            "question": self.question,
            "answer": self.answer,
            "retrieved_chunks": [
                {
                    "content": c.content,
                    "file_path": c.file_path,
                    "score": c.score,
                    "rank": c.rank,
                    "metadata": c.metadata,
                }
                for c in self.retrieved_chunks
            ],
            "latency_s": self.latency_s,
            "peak_memory_mb": self.peak_memory_mb,
            "agent": self.agent,
            "config_snapshot": self.config_snapshot,
            "error": self.error,
            "system_name": self.system_name,
            "run_index": self.run_index,
        }


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class RetrievalSystem(ABC):
    """
    Abstract base class for all evaluated systems.

    Every system (CodeGraphRAG and all baselines) must implement this
    interface. The BenchmarkEvaluator only communicates through this class.

    Implementation contract:
      - `name` must be unique across all systems in an experiment.
      - `retrieve()` must return chunks in descending relevance order.
      - `answer()` must call retrieve() internally (or an equivalent) and
        populate SystemResponse.retrieved_chunks with the chunks used.
      - `answer()` must NOT measure latency or memory — that is the
        evaluator's responsibility.
      - `configuration()` must return a JSON-serializable dict capturing
        every hyperparameter that affects the system's outputs.
      - `warm_up()` is called once before timed evaluation starts.
        Use it to load models, warm model caches, etc.
      - `teardown()` is called once after all queries complete.
        Use it to release resources.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique system identifier used in result files and tables."""
        ...

    @abstractmethod
    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        """
        Retrieve the top-k most relevant chunks for the given question.

        Parameters
        ----------
        question : str
            The natural language query.
        top_k : int
            Maximum number of chunks to return.

        Returns
        -------
        list[RetrievedChunk]
            Ordered by relevance descending. Length ≤ top_k.
        """
        ...

    @abstractmethod
    def answer(self, question: str) -> SystemResponse:
        """
        Generate an answer for the given question.

        Must populate SystemResponse.retrieved_chunks with the chunks
        actually used to produce the answer.

        Parameters
        ----------
        question : str
            The natural language query.

        Returns
        -------
        SystemResponse
            The complete system response. latency_s and peak_memory_mb
            will be overwritten by the evaluator.
        """
        ...

    @abstractmethod
    def configuration(self) -> Dict[str, Any]:
        """
        Return the complete, JSON-serializable configuration of this system.

        Must include every hyperparameter that affects the system's outputs:
        model names, top-k values, chunking strategy, reranker, etc.

        Used for:
          - Reproducibility manifest
          - Ensuring two runs with different configs are not compared
        """
        ...

    def warm_up(self) -> None:
        """
        Called once before timed evaluation begins.

        Override to load models, initialize caches, etc.
        Default implementation does nothing.
        """
        pass

    def teardown(self) -> None:
        """
        Called once after all evaluation queries complete.

        Override to release resources (close DB connections, unload models).
        Default implementation does nothing.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
