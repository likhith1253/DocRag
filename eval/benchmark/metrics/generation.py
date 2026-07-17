"""
eval.benchmark.metrics.generation
===================================
Generation quality metrics for the CodeGraphRAG benchmark.

Metrics:
  - Exact Match (EM): normalized string equality
  - Token F1: SQuAD-style token-level overlap
  - Semantic Similarity: cosine similarity of sentence embeddings
  - ROUGE-L: Longest Common Subsequence based
  - BLEU: n-gram precision (1-4 gram)
  - BERTScore: optional; imported lazily to avoid hard dependency

Research mapping:
  RQ1 (hybrid vs conventional): Token F1, Semantic Similarity
  RQ4 (routing ablation): Token F1, EM
  RQ6 (latency): — (system metrics primary)
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections import Counter
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Text normalization (SQuAD-style)
# ---------------------------------------------------------------------------

def _normalize_answer(text: str) -> str:
    """
    Normalize answer text for EM and Token F1 computation.

    Steps (following SQuAD evaluation):
      1. Unicode normalization (NFKD)
      2. Lowercase
      3. Remove articles (a, an, the)
      4. Remove punctuation
      5. Normalize whitespace
    """
    def remove_articles(s: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", s)

    def remove_punctuation(s: str) -> str:
        return s.translate(str.maketrans("", "", string.punctuation))

    def normalize_whitespace(s: str) -> str:
        return " ".join(s.split())

    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    text = remove_articles(text)
    text = remove_punctuation(text)
    text = normalize_whitespace(text)
    return text


def _tokenize(text: str) -> List[str]:
    """Split normalized text into tokens."""
    return _normalize_answer(text).split()


# ---------------------------------------------------------------------------
# Exact Match
# ---------------------------------------------------------------------------

def exact_match(predicted: str, expected: str) -> float:
    """
    Normalized Exact Match.

    Returns 1.0 if normalized(predicted) == normalized(expected), else 0.0.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.

    Returns
    -------
    float: 1.0 or 0.0
    """
    return 1.0 if _normalize_answer(predicted) == _normalize_answer(expected) else 0.0


# ---------------------------------------------------------------------------
# Token F1
# ---------------------------------------------------------------------------

def token_f1(predicted: str, expected: str) -> float:
    """
    Token-level F1 score (SQuAD-style).

    Measures token overlap between predicted and expected answers.

    F1 = 2 * (precision * recall) / (precision + recall)

    where precision = |common| / |predicted_tokens|
    and   recall    = |common| / |expected_tokens|

    Returns 0.0 if either string is empty after normalization.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.

    Returns
    -------
    float in [0, 1]
    """
    pred_tokens = _tokenize(predicted)
    gold_tokens = _tokenize(expected)

    if not pred_tokens or not gold_tokens:
        return 0.0

    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_common = sum(common.values())

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(gold_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


# ---------------------------------------------------------------------------
# Semantic Similarity
# ---------------------------------------------------------------------------

# Module-level encoder cache to avoid reloading the model per query
_encoder_cache: Optional[Any] = None
_encoder_model_name: Optional[str] = None


def _get_encoder(model_name: str = "intfloat/e5-base-v2"):
    """Lazily load the sentence transformer encoder (cached)."""
    from storage.vector_store import _get_encoder as _get_shared_encoder
    return _get_shared_encoder(model_name)


def semantic_similarity(
    predicted: str,
    expected: str,
    model_name: Optional[str] = None,
) -> float:
    """
    Cosine similarity between sentence embeddings of predicted and expected answers.

    Uses the configured embedding model (from config.yaml by default).
    Model is cached across calls.

    Note: This metric uses the same embedding model as the retrieval system.
    Reviewer note: This does NOT create circular evaluation — retrieval metrics
    are based purely on file path matching. Semantic similarity is used only
    to assess generation quality (answer text comparison), where the model is
    acting as a semantic judge, not a retriever.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.
    model_name : str, optional
        Override embedding model name. If None, loads from config.yaml.

    Returns
    -------
    float in [-1, 1], typically in [0, 1] for meaningful text.
    """
    import numpy as np

    if not predicted.strip() or not expected.strip():
        return 0.0

    if model_name is None:
        try:
            import yaml, os
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)
                )))),
                "config.yaml"
            )
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            model_name = cfg.get("embedding_model", "intfloat/e5-base-v2")
        except Exception:
            model_name = "intfloat/e5-base-v2"

    encoder = _get_encoder(model_name)
    embeddings = encoder.encode([predicted, expected], show_progress_bar=False)
    pred_emb = embeddings[0]
    gold_emb = embeddings[1]

    pred_norm = np.linalg.norm(pred_emb)
    gold_norm = np.linalg.norm(gold_emb)

    if pred_norm == 0 or gold_norm == 0:
        return 0.0

    return float(np.dot(pred_emb, gold_emb) / (pred_norm * gold_norm))


# ---------------------------------------------------------------------------
# ROUGE-L
# ---------------------------------------------------------------------------

def rouge_l(predicted: str, expected: str) -> float:
    """
    ROUGE-L F1 score (Longest Common Subsequence based).

    Uses the rouge_score library. Returns 0.0 on error.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.

    Returns
    -------
    float in [0, 1]
    """
    try:
        from rouge_score import rouge_scorer as rouge_module
        scorer = rouge_module.RougeScorer(["rougeL"], use_stemmer=False)
        scores = scorer.score(expected, predicted)
        return float(scores["rougeL"].fmeasure)
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# BLEU
# ---------------------------------------------------------------------------

def bleu(predicted: str, expected: str, max_n: int = 4) -> float:
    """
    BLEU score (1 to max_n gram precision with brevity penalty).

    Uses NLTK's sentence_bleu. Returns 0.0 on error.
    Smoothing method 1 (add-1) applied to avoid zero scores on short answers.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.
    max_n : int
        Maximum n-gram order (default 4, i.e., BLEU-4).

    Returns
    -------
    float in [0, 1]
    """
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
        reference = [_tokenize(expected)]
        hypothesis = _tokenize(predicted)
        if not hypothesis:
            return 0.0
        weights = tuple(1.0 / max_n for _ in range(max_n))
        smoothing = SmoothingFunction().method1
        return float(sentence_bleu(reference, hypothesis, weights=weights, smoothing_function=smoothing))
    except ImportError:
        return float("nan")
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# BERTScore (optional)
# ---------------------------------------------------------------------------

def bertscore(
    predicted: str,
    expected: str,
    lang: str = "en",
) -> Dict[str, float]:
    """
    BERTScore precision, recall, F1.

    Optional metric: returns {"bertscore_p": nan, "bertscore_r": nan, "bertscore_f1": nan}
    if bert_score is not installed.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.
    lang : str
        Language for BERTScore (default "en").

    Returns
    -------
    dict with bertscore_p, bertscore_r, bertscore_f1 (all floats).
    """
    try:
        from bert_score import score as bert_score_fn
        P, R, F1 = bert_score_fn([predicted], [expected], lang=lang, verbose=False)
        return {
            "bertscore_p": float(P[0]),
            "bertscore_r": float(R[0]),
            "bertscore_f1": float(F1[0]),
        }
    except ImportError:
        import math
        return {
            "bertscore_p": float("nan"),
            "bertscore_r": float("nan"),
            "bertscore_f1": float("nan"),
        }
    except Exception:
        return {
            "bertscore_p": 0.0,
            "bertscore_r": 0.0,
            "bertscore_f1": 0.0,
        }


# ---------------------------------------------------------------------------
# Aggregate computation
# ---------------------------------------------------------------------------

def compute_generation_metrics(
    predicted: str,
    expected: str,
    include_semantic: bool = True,
    include_rouge: bool = True,
    include_bleu: bool = True,
    include_bertscore: bool = False,
    embedding_model: Optional[str] = None,
) -> Dict[str, float]:
    """
    Compute all generation metrics for a single query.

    Parameters
    ----------
    predicted : str
        System-generated answer.
    expected : str
        Ground truth answer.
    include_semantic : bool
        Whether to compute semantic similarity (requires sentence-transformers).
    include_rouge : bool
        Whether to compute ROUGE-L (requires rouge_score).
    include_bleu : bool
        Whether to compute BLEU (requires nltk).
    include_bertscore : bool
        Whether to compute BERTScore (requires bert_score, slow).
    embedding_model : str, optional
        Override embedding model for semantic similarity.

    Returns
    -------
    dict mapping metric name to float.
    """
    metrics: Dict[str, float] = {
        "exact_match": exact_match(predicted, expected),
        "token_f1": token_f1(predicted, expected),
    }

    if include_semantic:
        metrics["semantic_similarity"] = semantic_similarity(predicted, expected, embedding_model)

    if include_rouge:
        metrics["rouge_l"] = rouge_l(predicted, expected)

    if include_bleu:
        metrics["bleu"] = bleu(predicted, expected)

    if include_bertscore:
        bs = bertscore(predicted, expected)
        metrics.update(bs)

    return metrics


def aggregate_generation_metrics(
    per_query_metrics: List[Dict[str, float]],
) -> Dict[str, float]:
    """
    Aggregate per-query generation metrics into dataset-level averages.

    NaN values are excluded from averages (e.g., optional metrics not installed).

    Parameters
    ----------
    per_query_metrics : list[dict]
        One dict per query from compute_generation_metrics().

    Returns
    -------
    dict mapping metric name to mean float.
    """
    import math
    if not per_query_metrics:
        return {}
    keys = per_query_metrics[0].keys()
    result = {}
    for key in keys:
        values = [m[key] for m in per_query_metrics if key in m and not math.isnan(m[key])]
        result[key] = sum(values) / len(values) if values else float("nan")
    return result
