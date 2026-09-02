"""
paper_matcher.py — Detects when a query explicitly names one or more indexed
papers, so the orchestrator can enforce strict paper-level retrieval isolation
instead of relying purely on global embedding similarity.

Generalizes to arbitrary papers using only the collection's own indexed
`paper_title`/`file` metadata — no external paper database, no hardcoded
paper list. Matching is intentionally conservative (word-overlap + exact
substring + self-referential acronym/initials) since a false-positive "this
paper was requested" match is worse than falling back to normal
collection-wide retrieval.
"""

import re
from typing import Any, Dict, List, Tuple

_STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "in", "on", "with", "to",
    "is", "are", "using", "via", "towards", "toward", "based", "from",
    "into", "under", "over", "by", "as", "at", "its", "an", "new",
}

# Cache of distinct paper titles per Qdrant collection name. Invalidated
# whenever the collection is re-indexed (see invalidate_paper_cache, wired
# into ingestion/worker.py the same way retrieval/repository_router.py's
# router cache is invalidated on re-index).
_paper_cache: Dict[str, List[str]] = {}


def invalidate_paper_cache(collection_name: str = None) -> None:
    if collection_name is None:
        _paper_cache.clear()
    else:
        _paper_cache.pop(collection_name, None)


def get_collection_papers(v_manager) -> List[str]:
    """Distinct paper_title (or file, if paper_title is missing) values in a collection."""
    key = v_manager.collection_name
    if key in _paper_cache:
        return _paper_cache[key]

    titles = set()
    try:
        for c in v_manager.get_all_chunks():
            meta = c.get("metadata", {})
            title = meta.get("paper_title") or meta.get("file") or ""
            title = title.strip()
            if title:
                titles.add(title)
    except Exception:
        pass

    result = sorted(titles)
    _paper_cache[key] = result
    return result


def _normalize(s: str) -> str:
    s = s.strip().lower()
    if s.endswith(".pdf"):
        s = s[:-4]
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _significant_words(title: str) -> List[str]:
    return [w for w in _normalize(title).split() if len(w) > 2 and w not in _STOPWORDS]


def _initials(words: List[str]) -> str:
    return "".join(w[0] for w in words if w)


def _compute_word_weights(available_titles: List[str]) -> Dict[str, float]:
    """
    Downweight words shared across many candidate titles in this collection
    (e.g. "Deep Reinforcement Learning" repeated across several RL papers'
    titles) so a query mentioning only that common phrase doesn't score a
    false match against every paper that happens to contain it — a real
    failure mode of plain word-overlap on academic titles that often share
    boilerplate phrasing. Words unique to one title keep full weight.
    """
    doc_freq: Dict[str, int] = {}
    for title in available_titles:
        for w in set(_significant_words(title)):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    return {w: 1.0 / (1 + df) for w, df in doc_freq.items()}


def score_title_match(
    query: str,
    title: str,
    acronym_tokens: List[str] = None,
    word_weights: Dict[str, float] = None,
) -> float:
    """
    Confidence (0..1) that `title` is explicitly named in `query`.

    - 1.0  the full normalized title appears verbatim in the query
    - 0..1 fraction of the title's significant words present in the query
    - 0.9  a short ALL-CAPS token in the original query matches the title's
           own word-initials (e.g. "SAC" <-> "Soft Actor-Critic") — only
           catches acronyms that are self-referential to the title text
           itself, since no external abbreviation database is used.
    """
    title_norm = _normalize(title)
    if not title_norm:
        return 0.0

    query_norm = _normalize(query)
    if title_norm in query_norm:
        return 1.0

    sig_words = _significant_words(title)
    if not sig_words:
        return 0.0

    query_words = set(query_norm.split())
    if word_weights:
        weights = [word_weights.get(w, 1.0) for w in sig_words]
    else:
        weights = [1.0] * len(sig_words)
    total_weight = sum(weights) or 1.0
    matched_weight = sum(w for word, w in zip(sig_words, weights) if word in query_words)
    score = matched_weight / total_weight

    if acronym_tokens:
        initials = _initials(sig_words).lower()
        for tok in acronym_tokens:
            if len(tok) >= 2 and tok.lower() == initials:
                score = max(score, 0.9)

    return score


def match_papers_in_query(
    query: str, available_titles: List[str], threshold: float = 0.55
) -> List[Tuple[str, float]]:
    """
    Return (title, score) pairs for indexed papers explicitly named in the
    query, sorted by descending confidence. Empty if none clear enough —
    callers should treat that as "no explicit paper requested" (general
    collection-wide search), not an error.
    """
    if not available_titles:
        return []

    acronym_tokens = re.findall(r"\b[A-Z][A-Z0-9]{1,5}\b", query)
    word_weights = _compute_word_weights(available_titles)

    scored = []
    for title in available_titles:
        score = score_title_match(query, title, acronym_tokens, word_weights)
        if score >= threshold:
            scored.append((title, score))

    scored.sort(key=lambda x: -x[1])
    return scored


def classify_paper_scope(matched_titles: List[Tuple[str, float]]) -> str:
    """
    "single"     — exactly one paper explicitly named -> strict isolation
    "multi"      — two or more papers explicitly named -> per-paper retrieval
    "collection" — no specific paper named -> normal collection-wide search
    """
    if len(matched_titles) == 1:
        return "single"
    if len(matched_titles) >= 2:
        return "multi"
    return "collection"
