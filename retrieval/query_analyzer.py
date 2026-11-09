"""Topic-agnostic question and structural-evidence analysis."""

from __future__ import annotations

import functools
import re
from typing import Any, Dict, List, Tuple

_STRUCTURAL_PATTERNS = {
    "HYPERPARAMETERS": (r"\b(parameter|setting|configuration|learning rate|batch size|dropout|threshold)\b",),
    "DATASETS": (r"\b(dataset|corpus|training set|test set|evaluation set|sample)\b",),
    "EQUATIONS": (r"\b(equation|formula|objective(?: function)?|loss function|update rule|derivative|gradient)\b",),
    "TABLES": (r"\b(table|row|column|tabular)\b",),
    "FIGURES": (r"\b(figure|diagram|plot|chart|visualization)\b",),
    "ALGORITHMS": (r"\b(algorithm|method|approach|procedure|pseudocode|steps?)\b",),
    "TRAINING": (r"\b(train|training|optimization|optimize|epoch|iteration)\b",),
    "RESULTS": (r"\b(result|performance|accuracy|score|metric|benchmark|evaluation)\b",),
    "LIMITATIONS": (r"\b(limitation|weakness|drawback|failure|issue|problem)\b",),
    "PREPROCESSING": (r"\b(preprocess\w*|normalize|standardize|resiz\w*|crop\w*|tokeniz\w*)\b",),
    "ARCHITECTURE": (r"\b(architecture|component|module|encoder|decoder|layer|network structure)\b",),
}
_COMPILED = {name: tuple(re.compile(p, re.I) for p in patterns) for name, patterns in _STRUCTURAL_PATTERNS.items()}
_TYPE_PREFERENCE = {
    "HYPERPARAMETERS": ["HYPERPARAMETERS", "TABLE", "MIXED", "TEXT"],
    "DATASETS": ["TABLE", "TEXT", "MIXED"],
    "EQUATIONS": ["EQUATION", "TEXT", "MIXED"],
    "TABLES": ["TABLE", "TEXT", "MIXED"],
    "FIGURES": ["FIGURE", "TEXT", "MIXED"],
    "ALGORITHMS": ["ALGORITHM", "TEXT", "MIXED"],
    "TRAINING": ["ALGORITHM", "TEXT", "MIXED"],
    "RESULTS": ["TABLE", "TEXT", "MIXED"],
    "LIMITATIONS": ["TEXT", "MIXED"],
    "PREPROCESSING": ["METHODOLOGY", "TEXT", "MIXED"],
    "ARCHITECTURE": ["FIGURE", "TEXT", "MIXED"],
    "GENERAL": ["TEXT", "MIXED", "TABLE", "EQUATION", "ALGORITHM", "FIGURE"],
}
_DEPTH_LABELS = {
    "HYPERPARAMETERS": "explicit settings and values",
    "DATASETS": "data sources and sample descriptions",
    "EQUATIONS": "equations and objective functions",
    "TABLES": "table evidence",
    "FIGURES": "figure captions and descriptions",
    "ALGORITHMS": "procedures and methods",
    "TRAINING": "training procedure",
    "RESULTS": "reported results and metrics",
    "LIMITATIONS": "limitations and caveats",
    "PREPROCESSING": "preprocessing operations",
    "ARCHITECTURE": "system components and architecture",
}


def _structural_scores(question: str) -> Dict[str, int]:
    return {name: sum(len(pattern.findall(question)) for pattern in patterns)
            for name, patterns in _COMPILED.items()
            if any(pattern.search(question) for pattern in patterns)}


def _detect_answer_depth(question: str) -> str:
    q = question.lower()
    if re.search(r"\b(compare|contrast|versus|vs\.?|difference between)\b", q):
        return "COMPARATIVE"
    if re.search(r"\b(list|enumerate|(?:which|what)\b.*?\b(?:algorithms|methods|approaches|techniques|models|frameworks|strategies|schemes|scheme|items)\b)", q):
        return "ENUM_LIST"
    if re.search(r"\b(how many|how much|what value|what setting|which value|table \d+)\b", q):
        return "EXTRACTION"
    if re.search(r"\b(overview|summari[sz]e|survey|review|all findings)\b", q):
        return "SURVEY"
    if re.search(r"\b(what is|define|name|who|when|where)\b", q):
        return "CONCISE"
    return "DETAILED"


@functools.lru_cache(maxsize=256)
def detect_question_type(question: str) -> Dict[str, Any]:
    scores = _structural_scores(question)
    question_type = max(scores, key=lambda name: scores[name]) if scores else "GENERAL"
    total = sum(scores.values())
    return {
        "question_type": question_type,
        "answer_depth": _detect_answer_depth(question),
        "keywords": [],
        "confidence": min(scores.get(question_type, 0) / max(total, 1), 1.0),
    }


def get_chunk_type_preference(question_type: str) -> List[str]:
    """Return a generic evidence-type preference for the detected question class."""
    return list(_TYPE_PREFERENCE.get(question_type, _TYPE_PREFERENCE["GENERAL"]))


def score_chunk_for_question(chunk: Dict[str, Any], question_type: str) -> float:
    """Score structural fit using chunk metadata and generic section cues."""
    meta = chunk.get("metadata", {})
    chunk_type = str(meta.get("chunk_type", "TEXT")).upper()
    preferred = get_chunk_type_preference(question_type)
    try:
        score = (len(preferred) - preferred.index(chunk_type)) / len(preferred)
    except ValueError:
        score = 0.25

    content = str(chunk.get("content", ""))
    if question_type in {"HYPERPARAMETERS", "RESULTS", "DATASETS"}:
        score += min(len(re.findall(r"\b\d+(?:\.\d+)?%?\b", content)) * 0.05, 0.4)
    if question_type == "EQUATIONS" and meta.get("contains_equation"):
        score += 0.5
    if question_type in {"TABLES", "RESULTS"} and meta.get("contains_table"):
        score += 0.5
    if question_type == "FIGURES" and meta.get("contains_figure"):
        score += 0.5
    section = str(meta.get("section", "")).lower()
    if section.startswith(("abstract", "introduction")) and question_type in {"RESULTS", "HYPERPARAMETERS"}:
        score -= 0.15
    return score


def extract_comparison_facets(question: str) -> List[Tuple[str, str]]:
    """Extract comparison dimensions from the user's wording without a fixed topic list."""
    match = re.search(r"\b(?:in terms of|across|regarding|with respect to|on)\s+(.+?)(?:[?.]|$)", question, re.I)
    if not match:
        return []
    dimensions = re.split(r"\s*,\s*|\s+and\s+|\s+or\s+", match.group(1))
    facets: List[Tuple[str, str]] = []
    for dimension in dimensions:
        normalized = " ".join(dimension.strip(" .?!").split())
        if len(normalized.split()) >= 1:
            facets.append((f"facet_{len(facets) + 1}", normalized))
    return facets


def decompose_complex_question(question: str, max_subqueries: int = 3) -> List[str]:
    """Create bounded subqueries only when the question names multiple evidence classes."""
    if max_subqueries <= 0:
        return []
    scores = _structural_scores(question)
    if len(scores) < 3:
        return []
    clauses = [part.strip(" ,;:") for part in re.split(r"[;?]+|\.(?=\s|$)", question) if len(part.split()) >= 4]
    if len(clauses) > 1:
        return clauses[:max_subqueries]
    selected = sorted(scores, key=lambda name: scores[name], reverse=True)[:max_subqueries]
    return [f"{question} ({_DEPTH_LABELS[kind]})" for kind in selected]


_EVIDENCE_PATTERNS = {
    "equation": r"\b(equation|formula|objective(?: function)?|loss function|update rule)\b",
    "table": r"\b(table|tabular|row|column|quantitative)\b",
    "figure": r"\b(figure|diagram|plot|chart|illustration)\b",
    "algorithm": r"\b(algorithm|pseudocode|procedure|steps?)\b",
    "numerical": r"\b(number|value|scores?|results?|performance|metrics?|percent|percentage)\b",
    "preprocessing": r"\b(preprocess\w*|normalize|standardize|resize|crop|tokenize)\b",
    "architecture": r"\b(architecture|component|module|encoder|decoder|layer|network structure)\b",
}


def detect_evidence_intent(question: str) -> Dict[str, bool]:
    """Detect requested structural evidence using topic-independent patterns."""
    lowered = question.lower()
    return {kind: bool(re.search(pattern, lowered)) for kind, pattern in _EVIDENCE_PATTERNS.items()}
