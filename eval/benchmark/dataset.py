"""
eval.benchmark.dataset
======================
BenchmarkDataset — the independent research artifact for CodeGraphRAG evaluation.

Design rationale (Amendments 2, 4):
  - Dataset schema is designed from the start to support BOTH internal
    (CodeGraphRAG itself) and external unseen repositories.
  - The `repository` block on each item links it to a registered repo entry.
  - This enables cross-repository generalization analysis without schema changes.
  - `debug_dataset.json` (purpose="debug") is schema-valid but blocked by
    the experiment runner from being used in reported experiments.

Dataset schema versioning:
  schema_version is checked at load time. Breaking changes require a new version.
  Migration functions handle version upgrades.

Research mapping:
  All 7 RQs — every experiment uses BenchmarkDataset.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple


SCHEMA_VERSION = "1.0"
SUPPORTED_CATEGORIES = {
    "Function Lookup",
    "Cross-file Reasoning",
    "Control Flow",
    "Data Flow",
    "Dependency Tracing",
    "API Reasoning",
    "Configuration Reasoning",
    "Architecture Reasoning",
    "Multi-hop Retrieval",
    "Bug Localization",
    "Retrieval Strategy",
    "Agent Reasoning",
}
SUPPORTED_RETRIEVAL_COMPLEXITIES = {
    "Single Chunk",
    "Multi Chunk",
    "Cross File",
    "Graph Dependent",
    "Long Context"
}
SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}
SUPPORTED_SPLITS = {"train", "dev", "test"}
SUPPORTED_VERIFIERS = {"human", "auto_then_human"}


# ---------------------------------------------------------------------------
# Repository registry entry
# ---------------------------------------------------------------------------

@dataclass
class RepositoryEntry:
    """
    A repository registered in the benchmark.

    Attributes
    ----------
    repo_id : str
        Unique identifier (e.g., "codegraphrag_main", "cpython_3.12").
    name : str
        Human-readable name.
    url : str
        Repository URL or "local" for local-only repos.
    commit : str
        Git commit hash pinned for reproducibility. Use "unknown" if not tracked.
    is_internal : bool
        True if this is the CodeGraphRAG repo itself (evaluated on its own code).
        False if this is an external unseen repository.
    description : str
        Brief description of the repository.
    language : str
        Primary language (e.g., "python", "mixed").
    """
    repo_id: str
    name: str
    url: str
    commit: str
    is_internal: bool
    description: str
    language: str = "python"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RepositoryEntry":
        return cls(**d)


# ---------------------------------------------------------------------------
# Dataset item
# ---------------------------------------------------------------------------

@dataclass(init=False)
class DatasetItem:
    """
    A single Q&A pair in the benchmark dataset.
    """
    id: str
    repo_id: str
    language: str
    reasoning_capability: str
    difficulty: str
    question: str
    verified_answer: str
    primary_source_file: str
    supporting_source_files: List[str]
    evidence_line_ranges: Dict[str, str]
    expected_retrieval_type: str
    expected_reasoning_type: str
    verification_method: str
    ground_truth_retrieval_chunks: List[str]
    retrieval_complexity: str
    notes: str
    verified: bool
    verifier: str
    created_at: str
    split: str

    def __init__(
        self,
        id: str,
        repo_id: str,
        question: str,
        difficulty: str,
        split: str,
        language: str = "python",
        reasoning_capability: str = "Architecture Reasoning",
        verified_answer: str = "",
        primary_source_file: str = "",
        supporting_source_files: List[str] = None,
        evidence_line_ranges: Dict[str, str] = None,
        expected_retrieval_type: str = "dense",
        expected_reasoning_type: str = "factual-lookup",
        verification_method: str = "source-code-inspection",
        ground_truth_retrieval_chunks: List[str] = None,
        retrieval_complexity: str = "Single Chunk",
        notes: str = "",
        verified: bool = True,
        verifier: str = "human",
        created_at: str = "",
        # Legacy fields
        category: str = "",
        answer: str = "",
        relevant_sources: List[str] = None,
    ):
        self.id = id
        self.repo_id = repo_id
        self.question = question
        self.difficulty = difficulty
        self.split = split
        self.language = language
        self.reasoning_capability = reasoning_capability or category or "Architecture Reasoning"
        self.verified_answer = verified_answer or answer
        self.primary_source_file = primary_source_file or (relevant_sources[0] if relevant_sources else "")
        self.supporting_source_files = supporting_source_files or (relevant_sources[1:] if relevant_sources and len(relevant_sources) > 1 else [])
        self.evidence_line_ranges = evidence_line_ranges or {}
        self.expected_retrieval_type = expected_retrieval_type
        self.expected_reasoning_type = expected_reasoning_type
        self.verification_method = verification_method
        self.ground_truth_retrieval_chunks = ground_truth_retrieval_chunks or []
        self.retrieval_complexity = retrieval_complexity
        self.notes = notes
        self.verified = verified
        self.verifier = verifier
        from datetime import datetime, timezone
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        
        # Normalize paths
        self.primary_source_file = self.primary_source_file.replace("\\", "/")
        self.supporting_source_files = [s.replace("\\", "/") for s in self.supporting_source_files]

    @property
    def category(self) -> str:
        return self.reasoning_capability

    @category.setter
    def category(self, value: str):
        self.reasoning_capability = value

    @property
    def answer(self) -> str:
        return self.verified_answer

    @answer.setter
    def answer(self, value: str):
        self.verified_answer = value

    @property
    def relevant_sources(self) -> List[str]:
        res = []
        if self.primary_source_file:
            res.append(self.primary_source_file)
        if self.supporting_source_files:
            res.extend(self.supporting_source_files)
        return res

    @relevant_sources.setter
    def relevant_sources(self, value: List[str]):
        if value:
            self.primary_source_file = value[0]
            self.supporting_source_files = value[1:]
        else:
            self.primary_source_file = ""
            self.supporting_source_files = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "repo_id": self.repo_id,
            "language": self.language,
            "reasoning_capability": self.reasoning_capability,
            "difficulty": self.difficulty,
            "question": self.question,
            "verified_answer": self.verified_answer,
            "primary_source_file": self.primary_source_file,
            "supporting_source_files": self.supporting_source_files,
            "evidence_line_ranges": self.evidence_line_ranges,
            "expected_retrieval_type": self.expected_retrieval_type,
            "expected_reasoning_type": self.expected_reasoning_type,
            "verification_method": self.verification_method,
            "ground_truth_retrieval_chunks": self.ground_truth_retrieval_chunks,
            "retrieval_complexity": self.retrieval_complexity,
            "notes": self.notes,
            "verified": self.verified,
            "verifier": self.verifier,
            "created_at": self.created_at,
            "split": self.split,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DatasetItem":
        return cls(**d)


# ---------------------------------------------------------------------------
# Validation results
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    item_count: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    split_counts: Dict[str, int] = field(default_factory=dict)
    repo_counts: Dict[str, int] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [f"ValidationReport: {'VALID' if self.is_valid else 'INVALID'}"]
        lines.append(f"  Items: {self.item_count}")
        lines.append(f"  Categories: {self.category_counts}")
        lines.append(f"  Splits: {self.split_counts}")
        lines.append(f"  Repos: {self.repo_counts}")
        if self.errors:
            lines.append(f"  ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append(f"  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main dataset class
# ---------------------------------------------------------------------------

class BenchmarkDataset:
    """
    The CodeGraphRAG benchmark dataset.

    Supports both internal (CodeGraphRAG) and external unseen repositories.
    Repository metadata is stored in `repositories` and linked per-item via `repo_id`.

    Schema version is enforced at load time. debug datasets (purpose="debug")
    are loadable but raise DatasetError when used in reported experiments.
    """

    SCHEMA_VERSION = SCHEMA_VERSION

    def __init__(
        self,
        items: List[DatasetItem],
        repositories: List[RepositoryEntry],
        description: str = "",
        purpose: str = "benchmark",
        created_at: Optional[str] = None,
    ):
        self.items = items
        self.repositories = repositories
        self.description = description
        self.purpose = purpose  # "benchmark" | "debug"
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self._repo_index: Dict[str, RepositoryEntry] = {r.repo_id: r for r in repositories}

    # ------------------------------------------------------------------
    # Loading / saving
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "BenchmarkDataset":
        """
        Load and validate a dataset from a JSON file.

        Raises
        ------
        FileNotFoundError
            If path does not exist.
        DatasetSchemaError
            If schema_version is unsupported or required fields are missing.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        version = raw.get("schema_version", "MISSING")
        if version != SCHEMA_VERSION:
            raise DatasetSchemaError(
                f"Unsupported schema_version '{version}'. Expected '{SCHEMA_VERSION}'. "
                f"Run the migration tool or use a compatible dataset."
            )

        repositories = [
            RepositoryEntry.from_dict(r)
            for r in raw.get("repositories", [])
        ]
        items = [DatasetItem.from_dict(item) for item in raw.get("items", [])]

        return cls(
            items=items,
            repositories=repositories,
            description=raw.get("description", ""),
            purpose=raw.get("purpose", "benchmark"),
            created_at=raw.get("created_at", ""),
        )

    def save(self, path: str) -> None:
        """Serialize dataset to JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {
            "schema_version": self.SCHEMA_VERSION,
            "purpose": self.purpose,
            "description": self.description,
            "created_at": self.created_at,
            "repositories": [r.to_dict() for r in self.repositories],
            "items": [item.to_dict() for item in self.items],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def compute_hash(self) -> str:
        """
        Compute a stable SHA-256 hash of the dataset content.
        Used in the experiment manifest for reproducibility.
        Deterministic: sorts items by id before hashing.
        """
        items_sorted = sorted([item.to_dict() for item in self.items], key=lambda x: x["id"])
        content = json.dumps(items_sorted, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def assert_is_benchmark(self) -> None:
        """
        Raise DatasetError if this is a debug dataset.
        Called by run_experiment.py before any experiment runs.
        """
        if self.purpose != "benchmark":
            raise DatasetError(
                f"Dataset purpose='{self.purpose}' is not allowed in reported experiments. "
                f"Only purpose='benchmark' datasets may be used. "
                f"The debug dataset must never appear in paper results."
            )

    def get_test_items(self) -> List[DatasetItem]:
        """Return only test-split items (used in all reported experiments)."""
        return [item for item in self.items if item.split == "test"]

    def get_by_category(self, category: str) -> List[DatasetItem]:
        """Return items matching the given category."""
        return [item for item in self.items if item.category == category]

    def get_by_difficulty(self, difficulty: str) -> List[DatasetItem]:
        """Return items matching the given difficulty."""
        return [item for item in self.items if item.difficulty == difficulty]

    def get_by_repo(self, repo_id: str) -> List[DatasetItem]:
        """Return items from the given repository."""
        return [item for item in self.items if item.repo_id == repo_id]

    def get_internal_items(self) -> List[DatasetItem]:
        """Return items from internal (CodeGraphRAG) repositories."""
        internal_ids = {r.repo_id for r in self.repositories if r.is_internal}
        return [item for item in self.items if item.repo_id in internal_ids]

    def get_external_items(self) -> List[DatasetItem]:
        """Return items from external (unseen) repositories."""
        external_ids = {r.repo_id for r in self.repositories if not r.is_internal}
        return [item for item in self.items if item.repo_id in external_ids]

    def get_repository(self, repo_id: str) -> Optional[RepositoryEntry]:
        """Lookup a repository entry by ID."""
        return self._repo_index.get(repo_id)

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict for logging and debugging."""
        from collections import Counter
        cat_counts = Counter(item.category for item in self.items)
        diff_counts = Counter(item.difficulty for item in self.items)
        split_counts = Counter(item.split for item in self.items)
        repo_counts = Counter(item.repo_id for item in self.items)
        verified_count = sum(1 for item in self.items if item.verified)
        return {
            "schema_version": self.SCHEMA_VERSION,
            "purpose": self.purpose,
            "total_items": len(self.items),
            "verified_items": verified_count,
            "categories": dict(cat_counts),
            "difficulties": dict(diff_counts),
            "splits": dict(split_counts),
            "repositories": dict(repo_counts),
            "internal_items": len(self.get_internal_items()),
            "external_items": len(self.get_external_items()),
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> ValidationReport:
        """
        Validate the dataset schema and content consistency.
        """
        from collections import Counter
        errors = []
        warnings = []
        seen_ids = set()
        known_repo_ids = {r.repo_id for r in self.repositories}
        cat_counts = Counter()
        split_counts = Counter()
        repo_counts = Counter()

        for i, item in enumerate(self.items):
            prefix = f"Item[{i}] id={item.id!r}"

            # Duplicate ID
            if item.id in seen_ids:
                errors.append(f"{prefix}: Duplicate id")
            seen_ids.add(item.id)

            # Required string fields non-empty
            for field_name in ("id", "question", "verified_answer"):
                val = getattr(item, field_name, "")
                if not isinstance(val, str) or not val.strip():
                    errors.append(f"{prefix}: Field '{field_name}' is empty or not a string")

            # Valid category (reasoning_capability)
            if item.reasoning_capability not in SUPPORTED_CATEGORIES:
                errors.append(f"{prefix}: Invalid reasoning_capability '{item.reasoning_capability}'")

            # Valid difficulty
            if item.difficulty not in SUPPORTED_DIFFICULTIES:
                errors.append(f"{prefix}: Invalid difficulty '{item.difficulty}'")

            # Valid split
            if item.split not in SUPPORTED_SPLITS:
                errors.append(f"{prefix}: Invalid split '{item.split}'")

            # Repo resolution
            if item.repo_id not in known_repo_ids:
                errors.append(f"{prefix}: repo_id '{item.repo_id}' not found in repositories")

            # Primary source file
            if not item.primary_source_file or not item.primary_source_file.strip():
                errors.append(f"{prefix}: primary_source_file is empty")
            elif os.path.isabs(item.primary_source_file):
                errors.append(f"{prefix}: primary_source_file entry is absolute path: {item.primary_source_file!r}")

            # Supporting source files
            for src in item.supporting_source_files:
                if os.path.isabs(src):
                    errors.append(f"{prefix}: supporting_source_files entry is absolute path: {src!r}")
                if not src.strip():
                    errors.append(f"{prefix}: supporting_source_files contains empty string")

            # Retrieval complexity
            if item.retrieval_complexity not in SUPPORTED_RETRIEVAL_COMPLEXITIES:
                errors.append(f"{prefix}: Invalid retrieval_complexity '{item.retrieval_complexity}'")

            # Verifier consistency
            if item.verified and item.verifier not in SUPPORTED_VERIFIERS:
                errors.append(f"{prefix}: verified=True but verifier='{item.verifier}' is unknown")
            if not item.verified and item.split == "test":
                warnings.append(f"{prefix}: test-split item is not verified")

            cat_counts[item.category] += 1
            split_counts[item.split] += 1
            repo_counts[item.repo_id] += 1

        # At least one test item per category present in the dataset
        test_cats = Counter(
            item.category for item in self.items if item.split == "test"
        )
        for cat in SUPPORTED_CATEGORIES:
            if cat not in test_cats:
                warnings.append(f"No test-split items for category '{cat}'")

        is_valid = len(errors) == 0
        return ValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            item_count=len(self.items),
            category_counts=dict(cat_counts),
            split_counts=dict(split_counts),
            repo_counts=dict(repo_counts),
        )

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return (
            f"BenchmarkDataset(items={len(self.items)}, "
            f"purpose={self.purpose!r}, "
            f"repos={len(self.repositories)})"
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DatasetError(Exception):
    """Raised when a dataset is used inappropriately (e.g., debug in experiment)."""
    pass


class DatasetSchemaError(DatasetError):
    """Raised when a dataset file does not match the expected schema version."""
    pass
