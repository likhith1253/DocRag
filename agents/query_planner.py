import os
import re
from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process

from storage.knowledge_graph import KnowledgeGraphManager
from storage.metadata_store import MetadataStoreManager
from storage.registry import QUERYABLE_REPO_STATUSES, RepositoryRegistry


STRUCTURAL_PATTERNS = {
    "definition": [
        re.compile(r"where\s+is\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\s+defined\??", re.IGNORECASE),
        re.compile(r"where\s+is\s+the\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\s+(function|class|method)\s+defined\??", re.IGNORECASE),
    ],
    "callers": [
        re.compile(r"who\s+calls\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\??", re.IGNORECASE),
        re.compile(r"what\s+calls\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\??", re.IGNORECASE),
    ],
    "imports": [
        re.compile(r"what\s+imports\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\??", re.IGNORECASE),
        re.compile(r"who\s+imports\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\??", re.IGNORECASE),
    ],
    "repo_lookup": [
        re.compile(r"which\s+repo(?:sitory)?\s+(?:contains|has|defines)\s+['`\"]?(?P<symbol>[\w./:-]+)['`\"]?\??", re.IGNORECASE),
    ],
}


def plan_structural_query(
    query: str,
    repo_id: Optional[str] = None,
    registry: Optional[RepositoryRegistry] = None,
) -> Optional[Dict[str, str]]:
    strategy, symbol = _classify_structural_query(query)
    if not strategy or not symbol:
        return None

    registry = registry or RepositoryRegistry()
    repos = _select_repositories(registry, repo_id)
    if not repos:
        return None

    if strategy == "definition":
        answer = _answer_definition(symbol, repos)
    elif strategy == "callers":
        answer = _answer_callers(symbol, repos)
    elif strategy == "imports":
        answer = _answer_imports(symbol, repos)
    else:
        answer = _answer_repo_lookup(symbol, repos)

    if not answer:
        return None

    return {
        "answer": answer,
        "strategy": strategy,
        "agent": "query_planner",
    }


def _classify_structural_query(query: str) -> tuple[Optional[str], Optional[str]]:
    cleaned = " ".join((query or "").strip().split())
    for strategy, patterns in STRUCTURAL_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(cleaned)
            if match:
                return strategy, match.group("symbol").strip("`'\" ")
    return None, None


def _normalize_symbol(symbol: str) -> List[str]:
    """Generate normalized variants of a symbol for flexible matching."""
    variants = [symbol.lower()]
    
    # Split by common separators
    for sep in ['_', '-', '.', ' ']:
        if sep in symbol:
            parts = symbol.split(sep)
            variants.append(''.join(parts).lower())
            variants.append(' '.join(parts).lower())
    
    # Remove common prefixes/suffixes
    prefixes = ['base', 'abstract', 'default', 'generic', 'simple']
    suffixes = ['base', 'impl', 'manager', 'handler', 'factory']
    
    for prefix in prefixes:
        if symbol.lower().startswith(prefix):
            variants.append(symbol[len(prefix):].lower())
    
    for suffix in suffixes:
        if symbol.lower().endswith(suffix):
            variants.append(symbol[:-len(suffix)].lower())
    
    # Handle pluralization (simple cases)
    if symbol.endswith('s'):
        variants.append(symbol[:-1].lower())  # Remove 's'
    if symbol.endswith('es'):
        variants.append(symbol[:-2].lower())  # Remove 'es'
    if symbol.endswith('ies'):
        variants.append(symbol[:-3] + 'y')  # Change 'ies' to 'y'
    
    # Add singular form if plural
    if not symbol.endswith('s'):
        variants.append(symbol + 's')  # Add 's'
    
    return list(set(variants))


def _find_best_match(symbol: str, candidates: List[str], threshold: float = 80) -> Optional[str]:
    """Find best fuzzy match for symbol among candidates."""
    if not candidates:
        return None
    
    # Try exact match first
    symbol_lower = symbol.lower()
    for candidate in candidates:
        if candidate.lower() == symbol_lower:
            return candidate
    
    # Try fuzzy matching
    result = process.extractOne(symbol, candidates, scorer=fuzz.WRatio)
    if result and result[1] >= threshold:
        return result[0]
    
    return None


def _get_all_symbols(repo) -> List[str]:
    """Extract all symbols (class names, function names, file names) from metadata."""
    store = _load_metadata(repo)
    symbols = set()
    
    for meta in store.store.values():
        file_name = os.path.basename(meta.get("file", ""))
        class_name = meta.get("class") or ""
        function_name = meta.get("function") or ""
        
        if file_name:
            symbols.add(file_name)
        if class_name:
            symbols.add(class_name)
        if function_name:
            symbols.add(function_name)
    
    return list(symbols)


def _select_repositories(registry: RepositoryRegistry, repo_id: Optional[str]):
    if repo_id:
        repo = registry.get_repository(repo_id)
        return [repo] if repo else []
    return [repo for repo in registry.list_repositories() if repo.status in QUERYABLE_REPO_STATUSES]


def _load_metadata(repo) -> MetadataStoreManager:
    return MetadataStoreManager(os.path.join("metadata_storage", f"{repo.metadata}.json"))


def _load_graph(repo) -> KnowledgeGraphManager:
    manager = KnowledgeGraphManager()
    manager.load_from_json(os.path.join("kg_storage", f"{repo.knowledge_graph}.json"))
    return manager


def _answer_definition(symbol: str, repos: List) -> Optional[str]:
    # First try exact match with normalization
    symbol_variants = _normalize_symbol(symbol)
    matches = []
    
    for repo in repos:
        store = _load_metadata(repo)
        for meta in store.store.values():
            file_name = os.path.basename(meta.get("file", ""))
            class_name = meta.get("class") or ""
            function_name = meta.get("function") or ""
            
            # Check all variants
            for variant in symbol_variants:
                if variant in {file_name.lower(), class_name.lower(), function_name.lower()}:
                    location = meta.get("file", "unknown file")
                    line_range = meta.get("lines", "unknown lines")
                    label = function_name or class_name or file_name
                    matches.append(f"{repo.name}: {label} in {location} ({line_range})")
                    break
    
    if matches:
        return "Definitions found:\n" + "\n".join(matches[:8])
    
    # If no exact match, try fuzzy matching
    for repo in repos:
        all_symbols = _get_all_symbols(repo)
        best_match = _find_best_match(symbol, all_symbols, threshold=75)
        
        if best_match:
            store = _load_metadata(repo)
            for meta in store.store.values():
                file_name = os.path.basename(meta.get("file", ""))
                class_name = meta.get("class") or ""
                function_name = meta.get("function") or ""
                
                if best_match in {file_name, class_name, function_name}:
                    location = meta.get("file", "unknown file")
                    line_range = meta.get("lines", "unknown lines")
                    label = function_name or class_name or file_name
                    matches.append(f"{repo.name}: {label} in {location} ({line_range})")
                    break
    
    if matches:
        return f"Definitions found (fuzzy match):\n" + "\n".join(matches[:8])
    
    return None


def _answer_callers(symbol: str, repos: List) -> Optional[str]:
    lines = []
    for repo in repos:
        graph = _load_graph(repo).graph
        
        # First try exact match
        if graph.has_node(symbol):
            callers = sorted(
                node for node, _, data in graph.in_edges(symbol, data=True)
                if data.get("type") == "Calls"
            )
            if callers:
                lines.append(f"{repo.name}: {', '.join(callers[:12])}")
        else:
            # Try fuzzy matching to find the actual symbol name in KG
            kg_symbols = list(graph.nodes())
            best_match = _find_best_match(symbol, kg_symbols, threshold=60)
            
            if best_match and graph.has_node(best_match):
                callers = sorted(
                    node for node, _, data in graph.in_edges(best_match, data=True)
                    if data.get("type") == "Calls"
                )
                if callers:
                    lines.append(f"{repo.name}: {', '.join(callers[:12])}")
    
    if not lines:
        return None
    return f"Callers of {symbol}:\n" + "\n".join(lines)


def _answer_imports(symbol: str, repos: List) -> Optional[str]:
    lines = []
    for repo in repos:
        graph = _load_graph(repo).graph
        
        # First try exact match
        if graph.has_node(symbol):
            importers = sorted(
                node for node, _, data in graph.in_edges(symbol, data=True)
                if data.get("type") == "Imports"
            )
            if importers:
                lines.append(f"{repo.name}: {', '.join(importers[:12])}")
        else:
            # Try fuzzy matching to find the actual symbol name in KG
            kg_symbols = list(graph.nodes())
            best_match = _find_best_match(symbol, kg_symbols, threshold=60)
            
            if best_match and graph.has_node(best_match):
                importers = sorted(
                    node for node, _, data in graph.in_edges(best_match, data=True)
                    if data.get("type") == "Imports"
                )
                if importers:
                    lines.append(f"{repo.name}: {', '.join(importers[:12])}")
    
    if not lines:
        return None
    return f"Importers of {symbol}:\n" + "\n".join(lines)


def _answer_repo_lookup(symbol: str, repos: List) -> Optional[str]:
    # First try exact match with normalization
    symbol_variants = _normalize_symbol(symbol)
    matches = []
    
    for repo in repos:
        store = _load_metadata(repo)
        found = False
        
        for meta in store.store.values():
            file_name = os.path.basename(meta.get("file", ""))
            class_name = meta.get("class") or ""
            function_name = meta.get("function") or ""
            
            # Check all variants
            for variant in symbol_variants:
                if variant in {file_name.lower(), class_name.lower(), function_name.lower()}:
                    matches.append(repo.name)
                    found = True
                    break
            
            if found:
                break
    
    if matches:
        return f"{symbol} appears in: {', '.join(matches[:12])}"
    
    # If no exact match, try fuzzy matching
    for repo in repos:
        all_symbols = _get_all_symbols(repo)
        best_match = _find_best_match(symbol, all_symbols, threshold=75)
        
        if best_match:
            matches.append(repo.name)
    
    if matches:
        return f"{symbol} appears in (fuzzy match): {', '.join(matches[:12])}"
    
    return None
