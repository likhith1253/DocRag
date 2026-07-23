"""
Query Analyzer for DocumentRAG.
Detects question types to bias retrieval and reranking.
"""

import re
from typing import Dict, Any, List


def detect_question_type(question: str) -> Dict[str, Any]:
    """
    Detect the type of question being asked.
    
    Returns dict with:
        - question_type: str (HYPERPARAMETERS, DATASETS, EQUATIONS, TABLES, FIGURES, ALGORITHMS, TRAINING, RESULTS, LIMITATIONS, GENERAL)
        - keywords: List[str] - keywords that triggered the classification
        - confidence: float - confidence score (0-1)
    """
    question_lower = question.lower()
    
    # Define patterns for each question type
    patterns = {
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
    
    # Score each question type
    scores = {}
    matched_keywords = {}
    
    for qtype, type_patterns in patterns.items():
        score = 0
        keywords = []
        for pattern in type_patterns:
            matches = re.findall(pattern, question_lower)
            if matches:
                score += len(matches)
                keywords.extend(matches)
        
        if score > 0:
            scores[qtype] = score
            matched_keywords[qtype] = keywords
    
    if not scores:
        return {
            "question_type": "GENERAL",
            "keywords": [],
            "confidence": 0.5
        }
    
    # Get the highest scoring type
    max_type = max(scores, key=scores.get)
    max_score = scores[max_type]
    
    # Normalize confidence
    confidence = min(max_score / 3.0, 1.0)
    
    return {
        "question_type": max_type,
        "keywords": matched_keywords.get(max_type, []),
        "confidence": confidence
    }


def get_chunk_type_preference(question_type: str) -> List[str]:
    """
    Return preferred chunk types for a given question type.
    Used to bias reranking.
    """
    preferences = {
        "HYPERPARAMETERS": ["HYPERPARAMETERS", "TABLE", "MIXED", "TEXT"],
        "DATASETS": ["TABLE", "TEXT", "MIXED"],
        "EQUATIONS": ["EQUATION", "TEXT", "MIXED"],
        "TABLES": ["TABLE", "TEXT"],
        "FIGURES": ["TEXT"],  # Figures are often described in text
        "ALGORITHMS": ["ALGORITHM", "TEXT", "MIXED"],
        "TRAINING": ["ALGORITHM", "TEXT", "MIXED"],
        "RESULTS": ["TABLE", "TEXT", "MIXED"],
        "LIMITATIONS": ["TEXT"],
        "GENERAL": ["TEXT", "MIXED", "TABLE", "EQUATION", "HYPERPARAMETERS", "ALGORITHM"],
    }
    
    return preferences.get(question_type, preferences["GENERAL"])


def score_chunk_for_question(chunk: Dict[str, Any], question_type: str) -> float:
    """
    Score a chunk based on its relevance to the question type.
    Higher score = more relevant.
    """
    chunk_type = chunk.get("metadata", {}).get("chunk_type", "TEXT")
    content = chunk.get("content", "").lower()
    
    # Get preferred chunk types for this question
    preferred_types = get_chunk_type_preference(question_type)
    
    # Base score from chunk type preference
    try:
        type_rank = preferred_types.index(chunk_type)
        type_score = (len(preferred_types) - type_rank) / len(preferred_types)
    except ValueError:
        type_score = 0.5  # Unknown chunk type
    
    # Bonus for numerical content in certain question types
    if question_type in ["HYPERPARAMETERS", "RESULTS", "TRAINING"]:
        numbers = len(re.findall(r'\d+\.?\d*', content))
        number_bonus = min(numbers * 0.1, 0.8) # increased weight
        type_score += number_bonus
    
    # Bonus for variable-value pairs in hyperparameter questions
    if question_type == "HYPERPARAMETERS":
        var_pairs = len(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*[\-\+]?[0-9]*\.?[0-9]+', content))
        var_bonus = min(var_pairs * 0.2, 1.0) # heavily boost
        type_score += var_bonus
        
    return type_score
