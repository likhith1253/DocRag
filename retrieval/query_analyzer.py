"""
query_analyzer.py — Extended question type detection for adaptive prompt depth.

Detects question types to:
  1. Bias CrossEncoder reranking (existing behaviour — unchanged)
  2. Select adaptive prompt template (new — Phase 3)
"""

import re
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Core type detection
# ---------------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Structural / retrieval-side patterns (existing, unchanged)
    # ------------------------------------------------------------------
    structural_patterns = {
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

    scores: Dict[str, int] = {}
    matched_keywords: Dict[str, List[str]] = {}

    for qtype, type_patterns in structural_patterns.items():
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
        CONCISE     — definition / what-is questions
        DETAILED    — how / why / mechanism / causal questions
        COMPARATIVE — compare / difference / versus questions
        SURVEY      — overview / review / summarize / list-all questions
    """
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
