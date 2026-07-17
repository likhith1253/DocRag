import unittest
from retrieval.cross_encoder_rerank import rerank_cross_encoder

class TestCrossEncoderRerank(unittest.TestCase):
    def test_rerank_cross_encoder(self):
        chunks = [
            {"content": "A cat sits on the mat."},
            {"content": "Python is a programming language."},
            {"content": "A dog chases a frisbee in the park."}
        ]
        
        # Querying about coding/python should score Python highest
        reranked = rerank_cross_encoder("writing python code", chunks, top_k=2)
        
        self.assertEqual(len(reranked), 2)
        self.assertTrue("Python" in reranked[0]["content"])
        self.assertTrue("score" in reranked[0])

if __name__ == "__main__":
    unittest.main()
