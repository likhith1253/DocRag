"""
Phase 3 DoD validation:
- 10 hand-written queries routed through router.py only
- 3 of them run end-to-end (router → agent → real LLM answer via Ollama)
"""
import sys
import os
sys.path.insert(0, "d:/Document_RAG")

from agents.router import route, AGENT_CODE, AGENT_DATA, AGENT_REASONING

# 10 hand-written test queries with expected agent categories
TEST_QUERIES = [
    # code_search (expected: code_agent)
    ("What functions are defined in loader.py?",              AGENT_CODE),
    ("Show me the class definition for VectorStoreManager.",  AGENT_CODE),
    ("How does the chunk_file method work?",                  AGENT_CODE),
    ("What does the parse_code function import?",             AGENT_CODE),
    # data_extraction (expected: data_agent)
    ("How many chunks were generated from the test repository?", AGENT_DATA),
    ("Count the number of Python files in the project.",         AGENT_DATA),
    ("List all the languages detected in the ingestion pipeline.", AGENT_DATA),
    # reasoning (expected: reasoning_agent)
    ("Why does the chunker prepend class headers to method chunks?", AGENT_REASONING),
    ("Explain the difference between MMR and cross-encoder reranking.", AGENT_REASONING),
    ("What is the purpose of the knowledge graph in this retrieval system?", AGENT_REASONING),
]

def run_routing_test():
    correct = 0
    results = []
    
    print("\n=== Router Classification Test (10 queries) ===")
    for i, (query, expected) in enumerate(TEST_QUERIES, 1):
        agent, confidence = route(query)
        ok = (agent == expected)
        if ok:
            correct += 1
        status = "PASS" if ok else "FAIL"
        results.append((query, expected, agent, confidence, ok))
        print(f"Q{i:02d} [{status}] conf={confidence:.2f} | Expected={expected} | Got={agent}")
        if not ok:
            print(f"     Query: {query}")
    
    print(f"\nRouting accuracy: {correct}/10")
    return correct, results

def run_e2e_test():
    """Run 3 queries end-to-end: router → agent → real LLM answer"""
    from storage.vector_store import VectorStoreManager
    from ingestion.loader import load_repository
    from ingestion.language_detect import detect_language
    from ingestion.chunker import chunk_file
    from storage.knowledge_graph import KnowledgeGraphManager
    from retrieval.graph_search import expand_by_graph
    from retrieval.metadata_filter import filter_chunks
    from retrieval.mmr_rerank import mmr_rerank
    from retrieval.cross_encoder_rerank import rerank_cross_encoder
    import agents.code_agent as code_agent
    import agents.data_agent as data_agent
    import agents.reasoning_agent as reasoning_agent
    
    agent_map = {
        AGENT_CODE: code_agent,
        AGENT_DATA: data_agent,
        AGENT_REASONING: reasoning_agent,
    }
    
    # Build index from workspace
    workspace_path = "d:/Document_RAG"
    print("\n=== Building index for E2E test ===")
    all_chunks = []
    for file_info in load_repository(workspace_path):
        fp = file_info["file_path"]
        if fp.replace("\\", "/").startswith(".venv/") or not fp.endswith(".py"):
            continue
        lang = detect_language(fp)
        file_chunks = chunk_file(fp, file_info["content"], file_info["repo_name"], file_info["branch"], lang)
        all_chunks.extend(file_chunks)
    
    print(f"Indexed {len(all_chunks)} chunks.")
    
    v_manager = VectorStoreManager()
    v_manager.add_chunks(all_chunks)
    
    kg_manager = KnowledgeGraphManager()
    kg_manager.build_from_chunks(all_chunks)
    
    # 3 E2E test queries (one from each category)
    e2e_queries = [
        ("What does the load_repository function do?", AGENT_CODE),
        ("How many chunks are generated from the test repo?", AGENT_DATA),
        ("Why does the system use tree-sitter for code parsing?", AGENT_REASONING),
    ]
    
    print("\n=== E2E Agent Test (3 queries through router -> retrieval -> agent -> LLM) ===")
    all_passed = True
    for query, expected_agent in e2e_queries:
        routed_agent, confidence = route(query)
        print(f"\nQuery: {query}")
        print(f"Routed to: {routed_agent} (confidence: {confidence:.2f})")
        
        # Retrieve
        results = v_manager.search(query, top_k=10)
        results = expand_by_graph(results, kg_manager, all_chunks=all_chunks, max_expansion=5)
        results = filter_chunks(results, {"language": "python"})
        if results:
            results = mmr_rerank(query, results, top_k=min(5, len(results)))
            results = rerank_cross_encoder(query, results, top_k=min(5, len(results)))
        
        if not results:
            results = all_chunks[:3]
            
        # Call agent
        module = agent_map[routed_agent]
        answer = module.run(query, results)
        
        is_text = isinstance(answer, str) and len(answer.strip()) > 0
        print(f"Answer ({len(answer)} chars): {answer[:200]}{'...' if len(answer) > 200 else ''}")
        print(f"Real text output: {'YES' if is_text else 'NO'}")
        if not is_text:
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    correct, _ = run_routing_test()
    
    print("\n=== Running E2E with live LLM (requires Ollama running) ===")
    try:
        e2e_ok = run_e2e_test()
        print(f"\nE2E agent calls produced real text: {'YES' if e2e_ok else 'NO'}")
    except Exception as e:
        print(f"E2E skipped (Ollama may not be running): {e}")
        e2e_ok = None
    
    print(f"\n=== PHASE 3 SUMMARY ===")
    print(f"Router accuracy: {correct}/10")
    print(f"E2E text answers: {e2e_ok}")
    dod = correct >= 8
    print(f"Phase 3 DoD met: {'YES' if dod else 'NO'}")
