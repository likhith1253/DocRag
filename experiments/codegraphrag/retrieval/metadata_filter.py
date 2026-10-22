from typing import List, Dict, Any

def filter_chunks(chunks: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filter retrieved chunks based on metadata criteria.
    Only returns chunks where all criteria fields match the chunk's metadata exactly.
    """
    if not criteria:
        return chunks
        
    filtered = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        match = True
        for key, val in criteria.items():
            # Support exact matches or simple string list matches
            if meta.get(key) != val:
                match = False
                break
        if match:
            filtered.append(chunk)
    return filtered
