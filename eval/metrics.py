import difflib


def exact_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def semantic_similarity(a: str, b: str) -> float:
    # lightweight similarity using SequenceMatcher
    return difflib.SequenceMatcher(None, a, b).ratio()


def concept_coverage(key_concepts, actual: str) -> float:
    if not key_concepts:
        return 0.0
    actual_lower = actual.lower()
    matches = 0
    for kc in key_concepts:
        if kc.lower() in actual_lower:
            matches += 1
    return round((matches / len(key_concepts)) * 100, 2)


def compute_metrics(expected: str, actual: str, key_concepts: list = None) -> dict:
    em = exact_match(expected, actual)
    sim = semantic_similarity(expected, actual)

    # grounding: proportion of expected tokens found in actual (fallback)
    expected_tokens = [t for t in expected.lower().split() if len(t) > 3]
    if expected_tokens:
        matches = sum(1 for t in expected_tokens if t in actual.lower())
        grounding_score = round((matches / max(1, len(expected_tokens))) * 100, 2)
    else:
        grounding_score = 0.0

    # concept coverage if key_concepts provided
    concept_cov = concept_coverage(key_concepts, actual) if key_concepts else 0.0

    # verdict based primarily on concept coverage (global evaluation rule)
    if concept_cov >= 70.0:
        verdict = 'Correct'
    elif concept_cov >= 40.0:
        verdict = 'Partial'
    else:
        verdict = 'Incorrect'

    # grounding label
    if grounding_score >= 70.0:
        grounding_label = 'Grounded'
    elif grounding_score >= 30.0:
        grounding_label = 'Partially Grounded'
    else:
        grounding_label = 'Hallucinated'

    return {
        'exact_match': em,
        'semantic_similarity': round(sim, 4),
        'grounding_score_percent': grounding_score,
        'concept_coverage_percent': concept_cov,
        'verdict': verdict,
        'grounding_label': grounding_label
    }
