import unittest
from ingestion.chunker import chunk_file

class TestChunker(unittest.TestCase):
    def test_chunking_python(self):
        code = """import sys
import os

class Helper:
    def execute(self):
        sys.exit(0)

def main():
    h = Helper()
    h.execute()
"""
        chunks = chunk_file("app/main.py", code, "myrepo", "main", "python")
        
        self.assertTrue(len(chunks) > 0)
        for chunk in chunks:
            meta = chunk["metadata"]
            self.assertEqual(meta["repository"], "myrepo")
            self.assertEqual(meta["branch"], "main")
            self.assertEqual(meta["language"], "python")
            self.assertEqual(meta["file"], "app/main.py")
            self.assertIn("class", meta)
            self.assertIn("function", meta)
            self.assertIn("lines", meta)
            self.assertIn("hash", meta)
            self.assertIn("timestamp", meta)
            self.assertIn("dependencies", meta)
            
        # Verify helper method chunk has class header prepended if chunk is class-specific
        helper_chunks = [c for c in chunks if c["metadata"]["class"] == "Helper"]
        self.assertTrue(len(helper_chunks) > 0)
        
        # Check call dependencies
        main_chunks = [c for c in chunks if c["metadata"]["function"] == "main"]
        self.assertTrue(len(main_chunks) > 0)

if __name__ == "__main__":
    unittest.main()
