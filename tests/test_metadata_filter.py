import unittest
from retrieval.metadata_filter import filter_chunks

class TestMetadataFilter(unittest.TestCase):
    def test_filter_chunks(self):
        chunks = [
            {"content": "A", "metadata": {"file": "a.py", "language": "python"}},
            {"content": "B", "metadata": {"file": "b.js", "language": "javascript"}},
            {"content": "C", "metadata": {"file": "c.py", "language": "python"}}
        ]
        
        # Test empty criteria
        self.assertEqual(len(filter_chunks(chunks, {})), 3)
        
        # Test exact match criteria
        res = filter_chunks(chunks, {"language": "python"})
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["content"], "A")
        self.assertEqual(res[1]["content"], "C")
        
        # Test multiple criteria
        res2 = filter_chunks(chunks, {"language": "python", "file": "c.py"})
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["content"], "C")

if __name__ == "__main__":
    unittest.main()
