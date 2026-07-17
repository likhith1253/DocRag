import os
import re
from typing import Dict, Any, Tuple
from storage.vector_store import _get_config

# Agent categories
AGENT_CODE = "code_agent"
AGENT_DATA = "data_agent"
AGENT_REASONING = "reasoning_agent"

# Rule-based keyword patterns per category
RULES = {
    AGENT_CODE: [
        r"\bfunction\b", r"\bclass\b", r"\bmethod\b", r"\bimport\b", r"\bdef\b",
        r"\bimplements?\b", r"\bcode\b", r"\bsyntax\b", r"\bsource\b",
        r"\bAPI\b", r"\bmodule\b", r"\bpackage\b", r"\binterface\b",
        r"\brefactor\b", r"\bbug\b", r"\bdebug\b", r"\bfix\b",
        r"\bloop\b", r"\brecursion\b", r"\bcall\b", r"\binherit\b",
        r"\bpattern\b", r"\barchitecture\b", r"\binstantiat\b",
        r"\bsignature\b", r"\bdocstring\b", r"\bdecorator\b",
    ],
    AGENT_DATA: [
        r"\bhow many\b", r"\bcount\b", r"\bsum\b", r"\baverage\b",
        r"\bnumber of\b", r"\bpercentage\b", r"\bstatistic\b",
        r"\bfrequency\b", r"\bdistribution\b", r"\bmax\b", r"\bmin\b",
        r"\bextract\b", r"\blist all\b", r"\benumerate\b",
        r"\bwhat values?\b", r"\bcompare\b", r"\bwhich files?\b",
        r"\bhow often\b", r"\bmetric\b", r"\bmeasure\b",
    ],
    AGENT_REASONING: [
        r"\bwhy\b", r"\bexplain\b", r"\bhow does\b", r"\bwhat is\b",
        r"\bunderstand\b", r"\bdifference between\b", r"\bpros and cons\b",
        r"\bpurpose\b", r"\bdesign decision\b", r"\btrade.?off\b",
        r"\banalyze\b", r"\bevaluate\b", r"\binfer\b", r"\bdeduce\b",
        r"\bstrategy\b", r"\bapproach\b", r"\badvantage\b",
    ],
}

def _score_query(query: str) -> Dict[str, float]:
    """
    Score a query against each agent's rule set.
    Returns normalized confidence score per agent.
    """
    q_lower = query.lower()
    scores = {}
    for agent, patterns in RULES.items():
        match_count = sum(1 for p in patterns if re.search(p, q_lower, re.IGNORECASE))
        scores[agent] = match_count / len(patterns)
    return scores

def route(query: str) -> Tuple[str, float]:
    """
    Route a query to the appropriate agent.
    
    Returns:
        (agent_name, confidence_score)
        If confidence < threshold, escalates to reasoning_agent regardless of rule match.
    """
    config = _get_config()
    threshold = config.get("router", {}).get("confidence_threshold", 0.6)
    
    scores = _score_query(query)
    
    # Pick highest-scoring agent
    best_agent = max(scores, key=scores.get)
    best_score = scores[best_agent]
    
    # Normalize to [0, 1] range relative to total signal
    total_signal = sum(scores.values())
    if total_signal > 0:
        confidence = scores[best_agent] / total_signal
    else:
        confidence = 0.0

    # Enforce direct agent routing for high-confidence code lookup queries.
    # This reduces unnecessary reasoning and preserves exact answer style.
    if best_agent == AGENT_CODE and confidence >= 0.75:
        return best_agent, confidence
    
    # If confidence < threshold, escalate to reasoning agent
    if confidence < threshold:
        return AGENT_REASONING, confidence
    
    return best_agent, confidence
