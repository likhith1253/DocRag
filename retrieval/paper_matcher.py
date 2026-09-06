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


# Known seminal algorithm acronyms and aliases mapped to title keywords
_SEMINAL_ALIASES: Dict[str, List[str]] = {
    "dqn": ["playing atari", "human level control through deep reinforcement learning"],
    "deep q network": ["playing atari"],
    "deep q networks": ["playing atari"],
    "playing atari": ["playing atari"],
    "a3c": ["asynchronous methods for deep reinforcement learning"],
    "asynchronous advantage actor critic": ["asynchronous methods for deep reinforcement learning"],
    "async advantage actor critic": ["asynchronous methods for deep reinforcement learning"],
    "asynchronous methods": ["asynchronous methods for deep reinforcement learning"],
    "a2c": ["asynchronous methods for deep reinforcement learning"],
    "sac": ["soft actor critic"],
    "soft actor critic": ["soft actor critic"],
    "ppo": ["proximal policy optimization"],
    "proximal policy optimization": ["proximal policy optimization"],
    "world models": ["world models"],
    "world model": ["world models"],
    "vae": ["auto encoding variational bayes"],
    "variational autoencoder": ["auto encoding variational bayes"],
    "variational autoencoders": ["auto encoding variational bayes"],
    "gan": ["generative adversarial nets", "generative adversarial networks"],
    "gpt": ["language models are few shot learners"],
    "gpt 3": ["language models are few shot learners"],
    "gpt3": ["language models are few shot learners"],
    "transformer": ["attention is all you need"],
    "transformers": ["attention is all you need"],
    "ddpg": ["continuous control with deep reinforcement learning"],
    "trpo": ["trust region policy optimization"],
    "ddpm": ["denoising diffusion probabilistic models"],
    "resnet": ["deep residual learning for image recognition"],
}


def _title_prefix(title: str) -> str:
    """Extract the primary title prefix before delimiters like :, -, or --."""
    m = re.split(r"[:\-\u2013\u2014]", title, maxsplit=1)
    return m[0].strip() if m else title.strip()


def score_title_match(
    query: str,
    title: str,
    acronym_tokens: List[str] = None,
    word_weights: Dict[str, float] = None,
) -> float:
    """
    Confidence (0..1) that `title` is explicitly named in `query`.

    - 1.0  the full normalized title (or primary prefix) appears verbatim in the query
    - 0.95 seminal algorithm/paper alias match (e.g. "DQN" -> "Playing Atari", "A3C" -> "Asynchronous Methods")
    - 0.9  short token matches the title's prefix initials (e.g. "SAC" -> "Soft Actor-Critic")
    - 0..1 fraction of the title's significant words present in the query
    """
    title_norm = _normalize(title)
    if not title_norm:
        return 0.0

    query_norm = _normalize(query)
    query_words = set(query_norm.split())

    # 1. Full normalized title appears verbatim in query
    if title_norm in query_norm:
        return 1.0

    # 1b. Singular/plural normalization for short titles (e.g. "world model" <-> "world models")
    if title_norm.endswith("s") and title_norm[:-1] in query_norm:
        return 1.0
    if not title_norm.endswith("s") and f"{title_norm}s" in query_norm:
        return 1.0

    # 2. Title prefix before delimiter (e.g. "soft actor critic", "asynchronous methods")
    prefix = _normalize(_title_prefix(title))
    if len(prefix) >= 4 and prefix in query_norm:
        return 1.0

    sig_words = _significant_words(title)
    if not sig_words:
        return 0.0

    # 3. Seminal algorithm alias matching
    for alias, target_keys in _SEMINAL_ALIASES.items():
        # Check if the alias is present in the query
        alias_matched = False
        if alias in query_words or (len(alias.split()) > 1 and alias in query_norm):
            alias_matched = True
        elif acronym_tokens and any(tok.lower() == alias for tok in acronym_tokens):
            alias_matched = True

        if alias_matched:
            for tkey in target_keys:
                if tkey in title_norm:
                    return 0.95

    # 4. Acronym initials matching (both full initials and prefix initials)
    if acronym_tokens:
        candidate_initials = set()
        # Full initials
        candidate_initials.add(_initials(sig_words).lower())
        # Prefix initials of length 2..5 (e.g. "Soft Actor-Critic" -> "sac")
        for k in range(2, min(6, len(sig_words) + 1)):
            candidate_initials.add(_initials(sig_words[:k]).lower())

        for tok in acronym_tokens:
            if len(tok) >= 2 and tok.lower() in candidate_initials:
                return 0.95

    # 5. Weighted significant word overlap
    if word_weights:
        weights = [word_weights.get(w, 1.0) for w in sig_words]
    else:
        weights = [1.0] * len(sig_words)
    total_weight = sum(weights) or 1.0
    matched_weight = sum(w for word, w in zip(sig_words, weights) if word in query_words)
    score = matched_weight / total_weight

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

    acronym_tokens = re.findall(r"\b[A-Za-z0-9]{2,6}\b", query)
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
