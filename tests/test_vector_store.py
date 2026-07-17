import os
import unittest
import shutil
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.vector_store import VectorStoreManager

class TestVectorStore(unittest.TestCase):
    def setUp(self):
        # We will use a temporary storage path for testing to avoid overriding production DB
        self.test_qdrant_path = "./test_qdrant_storage"
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        if os.path.exists(self.test_qdrant_path):
            try:
                shutil.rmtree(self.test_qdrant_path)
            except Exception:
                pass

    def tearDown(self):
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        if os.path.exists(self.test_qdrant_path):
            try:
                shutil.rmtree(self.test_qdrant_path)
            except Exception:
                pass

    def test_add_and_search(self):
        # Read files from workspace_path
        workspace_path = "d:/Document_RAG"
        
        # Collect chunks from a few select python files in tests
        chunks = []
        for file_info in load_repository(workspace_path):
            file_path = file_info["file_path"]
            if file_path.replace("\\", "/").startswith(".venv/") or not file_path.endswith(".py") or "test_loader" not in file_path:
                continue
            
            content = file_info["content"]
            repo_name = file_info["repo_name"]
            branch = file_info["branch"]
            lang = detect_language(file_path)
            file_chunks = chunk_file(file_path, content, repo_name, branch, lang)
            chunks.extend(file_chunks)
            if len(chunks) > 5:
                break
                
        self.assertTrue(len(chunks) > 0, "No chunks generated to index.")
        
        # Override manager's path temporarily
        manager = VectorStoreManager()
        manager.collection_name = "test_chunks"
        if manager.client.collection_exists(manager.collection_name):
            manager.client.delete_collection(manager.collection_name)
        manager._ensure_collection()
        
        # Add chunks
        manager.add_chunks(chunks)
        
        # Search — returns (chunks, timing_dict) tuple
        result_chunks, _ = manager.search("test", top_k=2)
        self.assertTrue(len(result_chunks) > 0)
        self.assertIn("content", result_chunks[0])
        self.assertIn("metadata", result_chunks[0])
        self.assertIn("score", result_chunks[0])

if __name__ == "__main__":
    unittest.main()
