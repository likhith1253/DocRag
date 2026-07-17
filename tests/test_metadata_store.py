import os
import unittest
from storage.metadata_store import MetadataStoreManager

class TestMetadataStore(unittest.TestCase):
    def setUp(self):
        self.test_path = "./test_metadata_store.json"
        if os.path.exists(self.test_path):
            os.remove(self.test_path)

    def tearDown(self):
        if os.path.exists(self.test_path):
            os.remove(self.test_path)

    def test_add_and_get(self):
        store = MetadataStoreManager(self.test_path)
        meta = {
            "repository": "myrepo",
            "branch": "main",
            "language": "python",
            "file": "main.py",
            "class": "None",
            "function": "None",
            "lines": "1-10",
            "hash": "abc123hash",
            "timestamp": "2026-07-06"
        }
        store.add_metadata("abc123hash", meta)
        
        # Reload
        store2 = MetadataStoreManager(self.test_path)
        fetched = store2.get_metadata("abc123hash")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["repository"], "myrepo")
        self.assertEqual(fetched["file"], "main.py")

if __name__ == "__main__":
    unittest.main()
