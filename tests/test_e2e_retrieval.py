import os
import shutil
import unittest
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.vector_store import VectorStoreManager
from storage.knowledge_graph import KnowledgeGraphManager
from storage.metadata_store import MetadataStoreManager

from retrieval.vector_search import search_vector
from retrieval.graph_search import expand_by_graph
from retrieval.metadata_filter import filter_chunks
from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder

class TestE2ERetrieval(unittest.TestCase):
    def setUp(self):
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()

    def tearDown(self):
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()

    def test_e2e_pipeline(self):
        # Setup clean test dirs
        test_qdrant_path = "./test_qdrant_storage_e2e"
        test_metadata_path = "./test_metadata_store_e2e.json"
        test_kg_path = "./test_knowledge_graph_e2e.json"
        
        for path in [test_qdrant_path]:
            if os.path.exists(path):
                try:
                    shutil.rmtree(path)
                except Exception:
                    pass
        for path in [test_metadata_path, test_kg_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
                
        try:
            # 1. Ingestion
            workspace_path = "d:/Document_RAG"
            all_chunks = []
            
            for file_info in load_repository(workspace_path):
                file_path = file_info["file_path"]
                file_path_clean = file_path.replace("\\", "/")
                ignored_prefixes = (
                    ".venv/", "eval/", "tests/", "scratch/", "qdrant_storage",
                    "profile_qdrant_storage", "test_qdrant", "__pycache__"
                )
                if any(file_path_clean.startswith(p) for p in ignored_prefixes) or not file_path.endswith(".py"):
                    continue
                content = file_info["content"]
                repo_name = file_info["repo_name"]
                branch = file_info["branch"]
                lang = detect_language(file_path)
                file_chunks = chunk_file(file_path, content, repo_name, branch, lang)
                all_chunks.extend(file_chunks)
                
            self.assertTrue(len(all_chunks) > 0, "No chunks ingested.")
            
            # 2. Build databases
            # Vector DB
            v_manager = VectorStoreManager()
            v_manager.qdrant_path = test_qdrant_path
            v_manager.collection_name = "e2e_chunks"
            v_manager.client = v_manager.client.__class__(path=test_qdrant_path)
            v_manager._ensure_collection()
            v_manager.add_chunks(all_chunks)
            
            # KG
            kg_manager = KnowledgeGraphManager()
            kg_manager.build_from_chunks(all_chunks)
            kg_manager.save_to_json(test_kg_path)
            
            # Metadata
            meta_manager = MetadataStoreManager(test_metadata_path)
            for chunk in all_chunks:
                meta_manager.add_metadata(chunk["metadata"]["hash"], chunk["metadata"])
                
            # 3. Retrieval Pipeline End-to-End
            query = "loader code streaming load_repository"
            
            # Step A: Vector Search (top 30)
            vector_results = v_manager.search(query, top_k=30)
            self.assertTrue(len(vector_results) > 0, "Vector search returned no results.")
            print(f"\n[Step 1] Vector Search found {len(vector_results)} chunks.")
            
            # Step B: Knowledge Graph expansion
            expanded_results = expand_by_graph(vector_results, kg_manager, all_chunks=all_chunks, max_expansion=15)
            print(f"[Step 2] Graph expansion resulted in {len(expanded_results)} chunks.")
            
            # Step C: Metadata Filtering (no-op here or filter by python language)
            filtered_results = filter_chunks(expanded_results, {"language": "python"})
            print(f"[Step 3] Metadata filtering resulted in {len(filtered_results)} chunks.")
            
            # Step D: MMR rerank (rerank to top 15 first to keep diverse set)
            mmr_results = mmr_rerank(query, filtered_results, top_k=min(15, len(filtered_results)), lambda_param=0.5)
            print(f"[Step 4] MMR rerank selected top {len(mmr_results)} diverse chunks.")
            
            # Step E: Cross-Encoder rerank (top 5)
            final_top_5 = rerank_cross_encoder(query, mmr_results, top_k=5)
            print(f"[Step 5] Cross-Encoder reranked to top {len(final_top_5)} chunks.")
            
            # Confirm output format and DoD
            self.assertEqual(len(final_top_5), min(5, len(mmr_results)))
            for idx, chunk in enumerate(final_top_5):
                print(f"Rank {idx+1}: File={chunk['metadata']['file']} (Score: {chunk.get('score'):.4f})")
                self.assertIn("score", chunk)
                self.assertIn("content", chunk)
                self.assertIn("metadata", chunk)
                
            print("\nE2E Retrieval Pipeline DoD Met: YES")
            
        finally:
            # Close client to release file lock before cleanup
            try:
                v_manager.client.close()
            except Exception:
                pass
            # Clean up
            for path in [test_qdrant_path]:
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path)
                    except Exception:
                        pass
            for path in [test_metadata_path, test_kg_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

if __name__ == "__main__":
    unittest.main()
