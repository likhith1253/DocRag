import os
import json
import statistics

def characterize():
    db_path = "d:/Document_RAG/eval/external_benchmark/db"
    meta_path = os.path.join(db_path, "metadata_store.json")
    kg_path = os.path.join(db_path, "knowledge_graph.json")
    
    if not os.path.exists(meta_path) or not os.path.exists(kg_path):
        print("Error: DB files not found.")
        return
        
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        
    with open(kg_path, "r", encoding="utf-8") as f:
        kg = json.load(f)
        
    chunks = metadata.values()
    num_chunks = len(chunks)
    chunk_lengths = [len(c.get("content", "")) for c in chunks if isinstance(c, dict)]
    avg_chunk_length = sum(chunk_lengths) / max(1, num_chunks)
    
    nodes = kg.get("nodes", {})
    edges = kg.get("edges", [])
    
    num_nodes = len(nodes)
    num_edges = len(edges)
    
    # Calculate import vs call graph density if we can distinguish edge types
    # or just overall density
    # Density = E / (N * (N-1))
    density = num_edges / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0
    
    import_edges = [e for e in edges if e.get("type") == "IMPORTS"]
    call_edges = [e for e in edges if e.get("type") == "CALLS"]
    import_density = len(import_edges) / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0
    call_density = len(call_edges) / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0
    
    # Average function/class size. We can get this from metadata or nodes.
    # Nodes typically have types like FUNCTION or CLASS
    functions = [n for n in nodes.values() if n.get("type") == "FUNCTION"]
    classes = [n for n in nodes.values() if n.get("type") == "CLASS"]
    
    # Content length is likely in the node or chunk
    # Let's just count nodes for now
    
    # Largest connected component
    # Simple BFS to find components
    adj = {n_id: [] for n_id in nodes.keys()}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in adj and t in adj:
            adj[s].append(t)
            adj[t].append(s)
            
    visited = set()
    max_component_size = 0
    for node in nodes.keys():
        if node not in visited:
            comp_size = 0
            q = [node]
            visited.add(node)
            while q:
                curr = q.pop(0)
                comp_size += 1
                for neighbor in adj.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        q.append(neighbor)
            if comp_size > max_component_size:
                max_component_size = comp_size
                
    print(f"Number of chunks: {num_chunks}")
    print(f"Average chunk length: {avg_chunk_length:.2f} chars")
    print(f"Knowledge graph nodes: {num_nodes}")
    print(f"Knowledge graph edges: {num_edges}")
    print(f"Import graph density: {import_density:.6f}")
    print(f"Call graph density: {call_density:.6f}")
    print(f"Total Functions: {len(functions)}")
    print(f"Total Classes: {len(classes)}")
    print(f"Largest connected component: {max_component_size}")
    
if __name__ == "__main__":
    characterize()
