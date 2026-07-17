import unittest
from retrieval.mmr_rerank import mmr_rerank

class TestMMRRerank(unittest.TestCase):
    def test_mmr_rerank(self):
        chunks = [
            {"content": "apple fruit red sweet juice", "score": 0.9},
            {"content": "apples and red delicious apples", "score": 0.85}, # very similar to first
            {"content": "space astronaut rocket launch mars orbit", "score": 0.6} # different
        ]
        
        # With high diversity weight (low lambda), the orbit chunk should be selected
        # instead of the second apple chunk
        reranked = mmr_rerank("delicious red apple", chunks, top_k=2, lambda_param=0.3)
        self.assertEqual(len(reranked), 2)
        
        # First should still be apple (highest initial similarity)
        self.assertTrue("apple" in reranked[0]["content"])
        
        # Second should be the space chunk because it is more diverse than the second apple chunk
        self.assertTrue("space" in reranked[1]["content"])

if __name__ == "__main__":
    unittest.main()
