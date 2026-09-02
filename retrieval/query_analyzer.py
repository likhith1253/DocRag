"""
query_analyzer.py — Extended question type detection for adaptive prompt depth.

Detects question types to:
  1. Bias CrossEncoder reranking (existing behaviour — unchanged)
  2. Select adaptive prompt template (new — Phase 3)
"""

import re
import functools
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Core type detection
# ---------------------------------------------------------------------------

_STRUCTURAL_PATTERNS = {
    "HYPERPARAMETERS": [
        r'\b(hyperparameter|parameter|setting|config|learning rate|batch size|dropout|gamma|alpha|beta|epsilon|lambda|momentum|weight decay)\b',
        r'\b(what is the|what are the|how much|how many|what value|what size)\b.*\b(discount|buffer|window|layer|hidden|embedding)\b',
        r'\b(set to|initialized to)\b',
    ],
    "DATASETS": [
        r'\b(dataset|data|training data|test data|evaluation data|corpus)\b',
        r'\b(common crawl|webtext|mnist|cifar|imagenet)\b',
    ],
    "EQUATIONS": [
        r'\b(equation|formula|mathematical|objective function|loss function)\b',
        r'\b(kl divergence|cross entropy|gradient|derivative)\b',
    ],
    "TABLES": [
        r'\b(table|tabular|row|column)\b',
    ],
    "FIGURES": [
        r'\b(figure|plot|graph|chart|visualization)\b',
    ],
    "ALGORITHMS": [
        r'\b(algorithm|method|approach|technique|procedure)\b',
        r'\b(cma-es|sgd|adam|rmsprop|adamw)\b',
    ],
    "TRAINING": [
        r'\b(train|training|learn|learning|optimization|optimize)\b',
        r'\b(epoch|iteration|step|update)\b',
    ],
    "RESULTS": [
        r'\b(result|performance|accuracy|score|metric|benchmark)\b',
        r'\b(super|glue|sota|state of the art)\b',
    ],
    "LIMITATIONS": [
        r'\b(limitation|weakness|drawback|issue|problem|fail)\b',
        r'\b(not able|cannot|unable|struggle)\b',
    ],
}

# Short natural-language phrase to steer a per-facet retrieval subquery.
_FACET_PHRASES = {
    "HYPERPARAMETERS": "hyperparameters and configuration values",
    "DATASETS": "datasets used",
    "EQUATIONS": "equations and objective function",
    "TABLES": "results tables",
    "FIGURES": "figures and plots",
    "ALGORITHMS": "algorithm and method description",
    "TRAINING": "training procedure",
    "RESULTS": "experimental results and performance",
    "LIMITATIONS": "limitations and drawbacks",
}


def _structural_scores(question_lower: str):
    """Shared by detect_question_type() and decompose_complex_question()."""
    scores: Dict[str, int] = {}
    matched_keywords: Dict[str, List[str]] = {}

    for qtype, type_patterns in _STRUCTURAL_PATTERNS.items():
        score = 0
        keywords: List[str] = []
        for pattern in type_patterns:
            matches = re.findall(pattern, question_lower)
            if matches:
                score += len(matches)
                keywords.extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])
        if score > 0:
            scores[qtype] = score
            matched_keywords[qtype] = keywords

    return scores, matched_keywords


@functools.lru_cache(maxsize=256)
def detect_question_type(question: str) -> Dict[str, Any]:
    """
    Detect the type of question being asked.

    Returns dict with:
        - question_type: str
        - answer_depth:  str  ('CONCISE' | 'DETAILED' | 'COMPARATIVE' | 'SURVEY')
        - keywords:      List[str]
        - confidence:    float (0–1)
    """
    question_lower = question.lower()
    scores, matched_keywords = _structural_scores(question_lower)

    structural_type = max(scores, key=scores.get) if scores else "GENERAL"
    structural_confidence = min(scores.get(structural_type, 0) / 3.0, 1.0) if scores else 0.5

    # ------------------------------------------------------------------
    # Semantic / depth patterns (new — for adaptive prompt)
    # ------------------------------------------------------------------
    depth = _detect_answer_depth(question_lower)

    return {
        "question_type": structural_type,
        "answer_depth": depth,
        "keywords": matched_keywords.get(structural_type, []),
        "confidence": structural_confidence,
    }


def _detect_answer_depth(question_lower: str) -> str:
    """
    Map a question to the appropriate answer depth.

    Returns one of:
        EXTRACTION  — hyperparameter, numerical, experimental setup, parameter list questions
        ENUM_LIST   — enumeration of named entities: algorithms, methods, approaches, techniques, models
        CONCISE     — definition / what-is questions
        DETAILED    — how / why / mechanism / causal questions
        COMPARATIVE — compare / difference / versus questions
        SURVEY      — overview / review / summarize / list-all questions
    """
    # Extraction (hyperparameters, setup, parameters, numbers, datasets)
    if re.search(
        r'\b(hyperparameter|parameter|setting|config|learning rate|batch size|dropout|gamma|alpha|beta|epsilon|lambda|momentum|weight decay|experimental setup|dataset size|epochs|training setup|hardware|values? used)\b',
        question_lower,
    ):
        return "EXTRACTION"

    # Enum-list: "what algorithms/methods/approaches/techniques/models ..."
    # Must fire BEFORE the generic CONCISE check because "what are" is also
    # matched by CONCISE; an enumeration question needs explicit entity listing.
    # Note: plural forms are explicitly listed so \b word-boundary works correctly
    # (e.g. "approaches" = approach+es, not approach+s, so s? alone is insufficient).
    if re.search(
        r'\b(what|which)\b.{0,60}\b(algorithms?|methods?|approaches?|techniques?|models?|frameworks?|strategies?|schemes?)\b',
        question_lower,
    ):
        return "ENUM_LIST"

    # Comparative
    if re.search(
        r'\b(compar|versus|vs\.?|difference between|better than|contrast|relative to)\b',
        question_lower,
    ):
        return "COMPARATIVE"

    # Survey / overview
    if re.search(
        r'\b(overview|survey|review|summarize|summary|describe all|list all|what are the main|what are the key|enumerate)\b',
        question_lower,
    ):
        return "SURVEY"

    # Detailed (how / why / mechanism)
    if re.search(
        r'\b(how does|how do|why does|why do|explain|what is the mechanism|what causes|what leads to|how is|how are|in what way)\b',
        question_lower,
    ):
        return "DETAILED"

    # Concise (what is, define, name)
    if re.search(
        r'\b(what is|what are|define|who is|when|where|which|name the)\b',
        question_lower,
    ):
        return "CONCISE"

    # Default to DETAILED for open-ended academic questions
    return "DETAILED"


# ---------------------------------------------------------------------------
# Chunk type preference (existing — unchanged)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=32)
def get_chunk_type_preference(question_type: str) -> List[str]:
    """Return preferred chunk types for a given question type."""
    preferences = {
        "HYPERPARAMETERS": ["HYPERPARAMETERS", "TABLE", "MIXED", "TEXT"],
        "DATASETS": ["TABLE", "TEXT", "MIXED"],
        "EQUATIONS": ["EQUATION", "TEXT", "MIXED"],
        "TABLES": ["TABLE", "TEXT"],
        "FIGURES": ["TEXT"],
        "ALGORITHMS": ["ALGORITHM", "TEXT", "MIXED"],
        "TRAINING": ["ALGORITHM", "TEXT", "MIXED"],
        "RESULTS": ["TABLE", "TEXT", "MIXED"],
        "LIMITATIONS": ["TEXT"],
        "GENERAL": ["TEXT", "MIXED", "TABLE", "EQUATION", "HYPERPARAMETERS", "ALGORITHM"],
    }
    return preferences.get(question_type, preferences["GENERAL"])


def score_chunk_for_question(chunk: Dict[str, Any], question_type: str) -> float:
    """Score a chunk based on its relevance to the question type."""
    chunk_type = chunk.get("metadata", {}).get("chunk_type", "TEXT")
    content = chunk.get("content", "").lower()

    preferred_types = get_chunk_type_preference(question_type)

    try:
        type_rank = preferred_types.index(chunk_type)
        type_score = (len(preferred_types) - type_rank) / len(preferred_types)
    except ValueError:
        type_score = 0.5

    if question_type in ["HYPERPARAMETERS", "RESULTS", "TRAINING"]:
        numbers = len(re.findall(r'\d+\.?\d*', content))
        number_bonus = min(numbers * 0.1, 0.8)
        type_score += number_bonus

    if question_type == "HYPERPARAMETERS":
        var_pairs = len(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*[\-\+]?[0-9]*\.?[0-9]+', content))
        var_bonus = min(var_pairs * 0.2, 1.0)
        type_score += var_bonus

    return type_score


# ---------------------------------------------------------------------------
# Lightweight complex-question decomposition
# ---------------------------------------------------------------------------

# Depths where a genuinely multi-facet question benefits from decomposition.
# CONCISE/EXTRACTION questions are inherently narrow — decomposing those would
# just dilute the context with irrelevant subquery hits.
_DECOMPOSABLE_DEPTHS = {"SURVEY", "DETAILED", "COMPARATIVE"}


def decompose_complex_question(question: str, max_subqueries: int = 3) -> List[str]:
    """
    For a genuinely multi-facet research question (e.g. one that touches
    architecture, training procedure, AND numerical results at once), return
    a small number of facet-focused subqueries to widen the retrieval
    candidate pool beyond whatever is globally closest to the raw question.

    Returns [] for questions that don't need it — most questions ask about
    one thing and should not be decomposed.
    """
    question_lower = question.lower()
    scores, _ = _structural_scores(question_lower)

    # Require at least 3 distinct facets to actually be present; a question
    # that only touches one or two structural categories is not "complex"
    # in the sense this is meant to help with.
    if len(scores) < 3:
        return []

    depth = _detect_answer_depth(question_lower)
    if depth not in _DECOMPOSABLE_DEPTHS:
        return []

    top_facets = sorted(scores, key=scores.get, reverse=True)[:max_subqueries]
    return [f"{question} ({_FACET_PHRASES[f]})" for f in top_facets if f in _FACET_PHRASES]
