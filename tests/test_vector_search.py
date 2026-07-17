import os
import shutil
import unittest
from storage.vector_store import VectorStoreManager
from retrieval.vector_search import search_vector

class TestVectorSearch(unittest.TestCase):
    def setUp(self):
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

    def test_vector_search(self):
        # We index a mock chunk and query it
        manager = VectorStoreManager()
        manager.collection_name = "test_search_chunks"
        if manager.client.collection_exists(manager.collection_name):
            manager.client.delete_collection(manager.collection_name)
        manager._ensure_collection()
        
        chunk = {
            "content": "This is a search query helper method to find data.",
            "metadata": {
                "hash": "somehashval1",
                "repository": "repo",
                "branch": "main",
                "language": "python",
                "file": "utils.py",
                "class": None,
                "function": "find_data"
            }
        }
        manager.add_chunks([chunk])
        
        # Test search_vector by temporarily subclassing/pointing the method
        # or we can verify it directly with manager.search
        res = manager.search("find data", top_k=1)
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["metadata"]["function"], "find_data")

if __name__ == "__main__":
    unittest.main()
