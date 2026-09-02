import unittest

from retrieval.query_analyzer import decompose_complex_question


class TestQueryDecomposition(unittest.TestCase):
    def test_simple_narrow_question_not_decomposed(self):
        self.assertEqual(decompose_complex_question("What is the learning rate?"), [])

    def test_two_facet_question_not_decomposed(self):
        # Only touches training + algorithms — below the 3-facet threshold.
        q = "How does the training algorithm work?"
        self.assertEqual(decompose_complex_question(q), [])

    def test_complex_multi_facet_question_is_decomposed(self):
        q = (
            "How does the training procedure, loss function, and dataset "
            "compare across results and limitation of this method?"
        )
        subs = decompose_complex_question(q)
        self.assertGreater(len(subs), 0)
        self.assertLessEqual(len(subs), 3)
        for sq in subs:
            self.assertTrue(sq.startswith(q))

    def test_respects_max_subqueries_bound(self):
        q = (
            "Describe the algorithm, training procedure, dataset, equations, "
            "results, table, and limitation of this method in detail."
        )
        subs = decompose_complex_question(q, max_subqueries=2)
        self.assertLessEqual(len(subs), 2)

    def test_concise_depth_not_decomposed_even_with_many_keywords(self):
        # EXTRACTION/CONCISE-style narrow factual asks shouldn't explode into
        # subqueries just because multiple structural keywords appear.
        q = "What is the batch size?"
        self.assertEqual(decompose_complex_question(q), [])


if __name__ == "__main__":
    unittest.main()
