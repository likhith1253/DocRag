import networkx as nx
from typing import List, Dict, Any
from storage.knowledge_graph import KnowledgeGraphManager

def expand_by_graph(
    retrieved_chunks: List[Dict[str, Any]], 
    kg_manager: KnowledgeGraphManager,
    all_chunks: List[Dict[str, Any]] = None,
    max_expansion: int = 15
) -> List[Dict[str, Any]]:
    """
    Expand the list of retrieved chunks using Knowledge Graph relationships.
    Steps:
      1. Collect nodes from retrieved_chunks (file paths, class names, function names).
      2. Find neighbors in the graph (direct incoming/outgoing edges like Calls, Imports, Inherits).
      3. Identify which additional chunks correspond to those neighbor nodes.
      4. Append them to the retrieved list.
    """
    if not retrieved_chunks:
        return []
        
    # Get active nodes from current chunks
    active_nodes = set()
    for chunk in retrieved_chunks:
        meta = chunk["metadata"]
        f = meta.get("file")
        c = meta.get("class")
        fn = meta.get("function")
        if f:
            active_nodes.add(f)
        if c:
            active_nodes.add(c)
        if fn:
            full_fn = f"{c}.{fn}" if c else fn
            active_nodes.add(full_fn)

    # Traverse graph to find neighbors
    expanded_nodes = set()
    for node in active_nodes:
        if kg_manager.graph.has_node(node):
            expanded_nodes.update(kg_manager.graph.successors(node))
            expanded_nodes.update(kg_manager.graph.predecessors(node))
            
    # Exclude nodes we already have
    new_nodes = expanded_nodes - active_nodes
    if not new_nodes or not all_chunks:
        return retrieved_chunks

    # Find chunks corresponding to new_nodes
    added_chunks = []
    seen_hashes = {c["metadata"]["hash"] for c in retrieved_chunks}
    
    for chunk in all_chunks:
        meta = chunk.get("metadata", {})
        c_hash = meta.get("hash")
        if not c_hash or c_hash in seen_hashes:
            continue
            
        f = meta.get("file")
        c = meta.get("class")
        fn = meta.get("function")
        full_fn = f"{c}.{fn}" if c else fn
        
        if f in new_nodes or c in new_nodes or (fn and full_fn in new_nodes):
            # Create a score field for consistency
            c_copy = dict(chunk)
            if "score" not in c_copy:
                c_copy["score"] = 0.5 # default lower score for graph-expanded items
            added_chunks.append(c_copy)
            seen_hashes.add(c_hash)
            if len(added_chunks) >= max_expansion:
                break
                
    return retrieved_chunks + added_chunks
