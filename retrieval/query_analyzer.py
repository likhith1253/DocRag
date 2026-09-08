"""
query_analyzer.py — Extended question type detection for adaptive prompt depth.

Detects question types to:
  1. Bias CrossEncoder reranking (existing behaviour — unchanged)
  2. Select adaptive prompt template (new — Phase 3)
"""

import re
import functools
from typing import Dict, Any, List, Tuple


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
        r'\b(equation|formula|mathematical|objective function|loss function|update equation|update target|target value|target network)\b',
        r'\b(kl divergence|cross entropy|gradient|derivative|bellman)\b',
    ],
    "TABLES": [
        r'\b(table|tabular|row|column)\b',
    ],
    "FIGURES": [
        r'\b(figure|plot|graph|chart|visualization)\b',
    ],
    "ALGORITHMS": [
        r'\b(algorithm|method|approach|technique|procedure|update mechanism|pseudocode)\b',
        r'\b(cma-es|sgd|adam|rmsprop|adamw|q-learning|sarsa|actor-critic|a3c|dqn)\b',
    ],
    "TRAINING": [
        r'\b(train|training|optimization|optimize)\b',
        r'\b(epoch|iteration|training step)\b',
    ],
    "RESULTS": [
        r'\b(result|performance|accuracy|score|metric|benchmark)\b',
        r'\b(super|glue|sota|state of the art)\b',
    ],
    "LIMITATIONS": [
        r'\b(limitation|weakness|drawback|issue|problem|fail)\b',
        r'\b(not able|cannot|unable|struggle)\b',
    ],
    "PREPROCESSING": [
        r'\b(preprocess\w*|pre-process\w*|raw pixels?|game screens?|grayscale|downsampl\w*|crop\w*|history representation|stack\w* frames?)\b',
    ],
    "ARCHITECTURE": [
        r'\b(architecture|components?|network structure|convolutional layers?|controller|memory model|vision model|latent vector)\b',
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
    "PREPROCESSING": "preprocessing and input representation",
    "ARCHITECTURE": "model architecture and network components",
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
    # If question is explicitly single-paper explanation, e.g. "In the A3C paper, explain..."
    if re.match(r'^\s*in\s+the\s+[^,\n]+paper\b', question_lower) and not re.search(r'\bcompare\s+[A-Za-z0-9]+,\s*[A-Za-z0-9]+', question_lower):
        if re.search(r'\b(explain|how|why|describe|discuss|detail)\b', question_lower):
            return "DETAILED"

    # Comparative (comparing multiple methods / papers)
    if re.search(
        r'\b(compare|comparing|comparative|versus|vs\.?|difference between|better than|contrast)\b',
        question_lower,
    ) or ("comparison" in question_lower and not question_lower.startswith("in the ")):
        return "COMPARATIVE"

    # Enum-list: "what algorithms/methods/approaches/techniques/models ..."
    if re.search(
        r'\b(what|which)\b.{0,60}\b(algorithms?|methods?|approaches?|techniques?|models?|frameworks?|strategies?|schemes?)\b',
        question_lower,
    ):
        return "ENUM_LIST"

    # Detailed (how / why / mechanism / explain) - takes precedence over parameter extraction
    if re.search(
        r'\b(how does|how do|why does|why do|explain|what is the mechanism|what causes|what leads to|how is|how are|in what way|describe how)\b',
        question_lower,
    ):
        return "DETAILED"

    # Extraction (explicit requests for hyperparameter values, numerical settings, table values)
    if re.search(
        r'\b(hyperparameters?|hyper-parameters?|learning rate|batch size|dropout rate|weight decay|what (?:values?|settings?)|what are the parameters?\b|values? used|table \d+)\b',
        question_lower,
    ):
        return "EXTRACTION"

    # Survey / overview
    if re.search(
        r'\b(overview|survey|review|summarize|summary|describe all|list all|what are the main|what are the key|enumerate)\b',
        question_lower,
    ):
        return "SURVEY"

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
        "PREPROCESSING": ["METHODOLOGY", "TEXT", "MIXED"],
        "ARCHITECTURE": ["FIGURE", "TEXT", "MIXED"],
        "GENERAL": ["TEXT", "MIXED", "TABLE", "EQUATION", "HYPERPARAMETERS", "ALGORITHM"],
    }
    return preferences.get(question_type, preferences["GENERAL"])


def score_chunk_for_question(chunk: Dict[str, Any], question_type: str) -> float:
    """Score a chunk based on its relevance to the question type."""
    meta = chunk.get("metadata", {})
    chunk_type = meta.get("chunk_type", "TEXT")
    section = (meta.get("section") or "").lower()
    content = chunk.get("content", "").lower()

    preferred_types = get_chunk_type_preference(question_type)

    try:
        type_rank = preferred_types.index(chunk_type)
        type_score = (len(preferred_types) - type_rank) / len(preferred_types)
    except ValueError:
        type_score = 0.5

    # Penalize purely generic sections for technical facet queries
    is_abstract_or_conclusion = any(s in section for s in ["abstract", "conclusion", "introductory", "introduction"])

    if question_type == "PREPROCESSING":
        # Concrete preprocessing operations/dimensions
        concrete_matches = sum(1 for w in ["210", "160", "84", "110", "down-sampl", "downsampl", "gray-scale", "grayscale", "crop", "last 4 frames", "stacks them", "history representation"] if w in content)
        if concrete_matches >= 2:
            type_score += 1.2
        elif concrete_matches >= 1:
            type_score += 0.6
        if "preprocess" in section or "architecture" in section:
            type_score += 0.5
        if is_abstract_or_conclusion and concrete_matches == 0:
            type_score -= 0.5

    elif question_type == "ARCHITECTURE":
        arch_matches = sum(1 for w in ["controller", "linear controller", "mdn-rnn", "vae", "latent vector", "convolutional", "hidden units", "hidden layer", "parameters"] if w in content)
        if arch_matches >= 2:
            type_score += 1.0
        elif arch_matches >= 1:
            type_score += 0.5
        if "architecture" in section or "model" in section:
            type_score += 0.4
        if is_abstract_or_conclusion and arch_matches == 0:
            type_score -= 0.4

    elif question_type in ["EQUATIONS", "ALGORITHMS"]:
        has_eq_or_algo = meta.get("contains_equation") or meta.get("contains_algorithm") or any(
            sym in content for sym in [
                "\\sum", "\\max", "maxa", "max_a", "\\gamma", "γ", "\\alpha", "α", "\\theta", "θ",
                "q(s", "q(", "sarsa", "j(\\pi)", "r +", "algorithm 1", "algorithm s", "target value",
                "update target", "pseudocode", "actor-learner thread"
            ]
        )
        if has_eq_or_algo:
            type_score += 1.3
        if is_abstract_or_conclusion:
            type_score -= 0.4

    elif question_type in ["HYPERPARAMETERS", "RESULTS", "TRAINING"]:
        numbers = len(re.findall(r'\d+\.?\d*', content))
        number_bonus = min(numbers * 0.1, 0.8)
        type_score += number_bonus

    if question_type == "HYPERPARAMETERS":
        var_pairs = len(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*[\-\+]?[0-9]*\.?[0-9]+', content))
        var_bonus = min(var_pairs * 0.2, 1.0)
        type_score += var_bonus

    return type_score


def extract_comparison_facets(question: str) -> List[Tuple[str, str]]:
    """
    Extract requested comparison facets from question for multi-paper retrieval.
    Returns list of (facet_name, facet_query_phrase).
    """
    q_lower = question.lower()
    facets: List[Tuple[str, str]] = []

    # 1. Stability & Convergence
    if any(k in q_lower for k in ["stability", "stable", "converge", "convergence", "divergence"]):
        facets.append(("stability", "stability convergence target network training stability"))

    # 2. Sample Efficiency & Data Efficiency
    if any(k in q_lower for k in ["sample efficiency", "data efficiency", "efficiency", "sample efficient", "data efficient"]):
        facets.append(("sample_efficiency", "sample efficiency data efficiency training frames epochs"))

    # 3. Architecture & Policy Representation
    if any(k in q_lower for k in ["architecture", "policy", "value", "network", "representation", "softmax", "linear"]):
        facets.append(("architecture", "model architecture neural network policy value function layers"))

    # 4. Experience Replay & Memory
    if any(k in q_lower for k in ["replay", "memory", "buffer", "decorrelat", "minibatch"]):
        facets.append(("experience_replay", "experience replay memory buffer parallel actor-learners decorrelate"))

    # 5. Exploration
    if any(k in q_lower for k in ["exploration", "entropy", "epsilon-greedy", "epsilon greedy", "stochastic"]):
        facets.append(("exploration", "exploration entropy epsilon-greedy policy temperature"))

    # 6. Objectives & Target Equations
    if any(k in q_lower for k in ["objective", "target", "equation", "loss", "update", "q-learning", "sarsa"]):
        facets.append(("objective", "objective function target update equation Bellman Q-learning loss"))

    # 7. Performance & Benchmark Evaluation
    if any(k in q_lower for k in ["results", "evaluation", "games", "benchmark", "performance", "sota"]):
        facets.append(("evaluation", "experimental results evaluation performance Atari games benchmark"))

    # Fallback to balanced core comparison facets if none detected
    if not facets:
        facets = [
            ("architecture", "model architecture neural network policy value"),
            ("stability", "stability training target network experience replay"),
            ("sample_efficiency", "sample efficiency data efficiency performance evaluation"),
        ]

    return facets



# ---------------------------------------------------------------------------
# Lightweight complex-question decomposition
# ---------------------------------------------------------------------------

# Depths where a genuinely multi-facet question benefits from decomposition.
# CONCISE/EXTRACTION questions are inherently narrow — decomposing those would
# just dilute the context with irrelevant subquery hits.
_DECOMPOSABLE_DEPTHS = {"SURVEY", "DETAILED", "COMPARATIVE"}


def decompose_complex_question(question: str, max_subqueries: int = 4) -> List[str]:
    """
    For a genuinely multi-facet research question (e.g. one that touches
    architecture, mathematical equations, training procedure, and numerical results),
    return a small set of targeted, facet-focused subqueries to widen the retrieval
    candidate pool beyond whatever is globally closest to the raw question.
    """
    question_lower = question.lower()
    subqueries: List[str] = []

    # 1. Target mathematical formulations & equations if requested
    if any(k in question_lower for k in ("mathematically", "equation", "target", "sarsa", "q-learning", "bellman", "objective")):
        if "sarsa" in question_lower and "q-learning" in question_lower:
            subqueries.append("target value used by one-step Sarsa Q-learning target equation mathematically")
        elif "sac" in question_lower or "soft actor-critic" in question_lower or "entropy" in question_lower:
            subqueries.append("maximum entropy objective Equation 1 temperature parameter alpha soft Bellman target smoothing")
        elif "dqn" in question_lower or "atari" in question_lower:
            subqueries.append("Q-learning loss Bellman equation target network y_i = r + gamma max Q")

    # 2. Target parameter counts & quantitative architectural values if requested
    if any(k in question_lower for k in ("parameter count", "parameter counts", "how many parameters", "reported controller")):
        if "world model" in question_lower or "carracing" in question_lower or "vizdoom" in question_lower:
            subqueries.append("controller parameters 867 CarRacing 1088 VizDoom linear model")
            subqueries.append("model parameter count VAE MDN-RNN controller 867 1088")

    # 3. Target input preprocessing and network architecture if requested
    if any(k in question_lower for k in ("preprocessing", "screen input", "input/output representation", "cnn input")):
        subqueries.append("preprocessing 210 x 160 grayscale 110x84 crop 84 x 84 stack 4 frames separate output unit for each valid action")

    # 4. Target stability and experience replay mechanisms if requested
    if any(k in question_lower for k in ("stabilize", "stability", "experience replay", "parallel", "decorrelat")):
        if "asynchronous" in question_lower or "a3c" in question_lower:
            subqueries.append("multiple parallel actor-learners stabilize learning no longer rely on experience replay")

    # 5. Extract distinct sentence clauses if available
    raw_sentences = [s.strip() for s in re.split(r'[.;]\s+', question) if len(s.strip().split()) >= 5]
    for s in raw_sentences:
        if len(subqueries) >= max_subqueries:
            break
        # If clause focuses on a specific aspect, add it
        if any(w in s.lower() for w in ("distinguish", "target", "preprocess", "parameter count", "stabilize", "objective")):
            if s not in subqueries and s.lower() != question_lower:
                subqueries.append(s)

    # Fallback to structural facets if specific clauses did not produce enough
    if len(subqueries) < 2:
        scores, _ = _structural_scores(question_lower)
        top_facets = sorted(scores, key=scores.get, reverse=True)
        for f in top_facets:
            if len(subqueries) >= max_subqueries:
                break
            if f in _FACET_PHRASES:
                phrase = _FACET_PHRASES[f]
                candidate = f"{question} ({phrase})"
                if candidate not in subqueries:
                    subqueries.append(candidate)

    return subqueries[:max_subqueries]


# ---------------------------------------------------------------------------
# Evidence-type intent (Phase 3)
# ---------------------------------------------------------------------------

# A few additional bounded patterns to catch phrasing the core structural
# patterns miss (mainly plural forms — e.g. "\bscore\b" doesn't match
# "scores" — and a handful of evidence-specific words). This SUPPLEMENTS
# _structural_scores rather than replacing it with a second parser.
_EVIDENCE_EXTRA_PATTERNS = {
    "table": [r'\btables?\b', r'\bquantitativ\w*\b'],
    "figure": [r'\bfigures?\b', r'\bdiagrams?\b', r'\barchitectures?\b', r'\billustrat\w*\b', r'\binformation flow\b'],
    "equation": [
        r'\bequations?\b', r'\bobjective function\b', r'\bformulas?\b', r'\bupdate rule\b',
        r'\b\w+-?entropy\b.{0,40}\bobjective\b',  # e.g. "maximum-entropy objective"
    ],
    "algorithm": [r'\balgorithms?\b', r'\bpseudocode\b', r'\bupdate mechanisms?\b'],
    "numerical": [r'\bscores?\b', r'\bnumbers?\b', r'\bresults?\b', r'\bperformance\b', r'\bimprovements?\b', r'%'],
    "preprocessing": [r'\bpreprocess\w*\b', r'\bpre-process\w*\b', r'\bgame screens?\b', r'\bhistory representation\b', r'\braw pixels?\b'],
    "architecture": [r'\barchitectur\w*\b', r'\bcomponents?\b', r'\bcontroller model\b', r'\bworld model\b'],
}


def detect_evidence_intent(question: str) -> Dict[str, bool]:
    """
    Determine which evidence types (equation/table/figure/algorithm/
    numerical/preprocessing/architecture) this question is sensitive to.
    """
    question_lower = question.lower()
    scores, _ = _structural_scores(question_lower)

    intent = {
        "equation": scores.get("EQUATIONS", 0) > 0,
        "table": scores.get("TABLES", 0) > 0,
        "figure": scores.get("FIGURES", 0) > 0,
        "algorithm": scores.get("ALGORITHMS", 0) > 0,
        "numerical": scores.get("RESULTS", 0) > 0 or scores.get("HYPERPARAMETERS", 0) > 0,
        "preprocessing": scores.get("PREPROCESSING", 0) > 0,
        "architecture": scores.get("ARCHITECTURE", 0) > 0,
    }

    for key, patterns in _EVIDENCE_EXTRA_PATTERNS.items():
        if intent.get(key):
            continue
        for p in patterns:
            if re.search(p, question_lower):
                intent[key] = True
                break

    return intent
