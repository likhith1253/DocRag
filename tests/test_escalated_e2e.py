import sys
sys.path.insert(0, "d:/Document_RAG")

from agents.router import route
from storage.vector_store import VectorStoreManager
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.knowledge_graph import KnowledgeGraphManager
from retrieval.graph_search import expand_by_graph
from retrieval.metadata_filter import filter_chunks
from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder
import agents.reasoning_agent as reasoning_agent

def main():
    workspace_path = "d:/Document_RAG"
    all_chunks = []
    for file_info in load_repository(workspace_path):
        fp = file_info["file_path"]
        if fp.replace("\\", "/").startswith(".venv/") or not fp.endswith(".py"):
            continue
        lang = detect_language(fp)
        file_chunks = chunk_file(fp, file_info["content"], file_info["repo_name"], file_info["branch"], lang)
        all_chunks.extend(file_chunks)
        
    v_manager = VectorStoreManager()
    v_manager.add_chunks(all_chunks)
    
    kg_manager = KnowledgeGraphManager()
    kg_manager.build_from_chunks(all_chunks)
    
    queries = [
        "What functions are defined in loader.py?",
        "How does the chunk_file method work?",
    ]
    
    for query in queries:
        agent, conf = route(query)
        print(f"\nQuery: {query}")
        print(f"Routed to: {agent} (confidence: {conf:.2f})")
        
        # Retrieval
        results = v_manager.search(query, top_k=10)
        results = expand_by_graph(results, kg_manager, all_chunks=all_chunks, max_expansion=5)
        results = filter_chunks(results, {"language": "python"})
        if results:
            results = mmr_rerank(query, results, top_k=min(5, len(results)))
            results = rerank_cross_encoder(query, results, top_k=min(5, len(results)))
            
        if not results:
            results = all_chunks[:3]
            
        answer = reasoning_agent.run(query, results)
        print(f"Answer:\n{answer}\n")

if __name__ == "__main__":
    main()
