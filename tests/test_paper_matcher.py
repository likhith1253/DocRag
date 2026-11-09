import unittest

from retrieval.paper_matcher import (
    match_papers_in_query,
    classify_paper_scope,
    score_title_match,
    get_collection_papers,
    invalidate_paper_cache,
)


class TestPaperMatcher(unittest.TestCase):
    def setUp(self):
        self.titles = [
            "Adaptive Control for Urban Networks",
            "Asynchronous Scheduling for Shared Systems",
            "Stable Optimization with Sparse Feedback",
            "Deep Learning for Traffic Flow Prediction",
            "Quantum Annealing for Combinatorial Auction Optimization",
        ]

    def test_exact_title_substring_match_scores_high(self):
        query = "Explain the training procedure used in Stable Optimization with Sparse Feedback."
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "Stable Optimization with Sparse Feedback")
        self.assertAlmostEqual(matches[0][1], 1.0)

    def test_multi_paper_full_title_mentions(self):
        query = (
            "Compare Adaptive Control for Urban Networks, "
            "Asynchronous Scheduling for Shared Systems, and Stable Optimization with Sparse Feedback."
        )
        matched_titles = {title for title, _ in match_papers_in_query(query, self.titles)}
        self.assertEqual(matched_titles, set(self.titles[:3]))
        self.assertNotIn("Deep Learning for Traffic Flow Prediction", matched_titles)

    def test_title_derived_acronym_match(self):
        query = "How does SOSF handle feedback?"
        matches = match_papers_in_query(query, self.titles)
        self.assertIn("Stable Optimization with Sparse Feedback", {title for title, _ in matches})

    def test_topic_only_query_matches_no_specific_paper(self):
        self.assertEqual(match_papers_in_query("Which papers discuss replay memory?", self.titles), [])

    def test_unrelated_generic_query_does_not_match(self):
        self.assertEqual(match_papers_in_query("What is the capital of France?", self.titles), [])

    def test_generalizes_to_arbitrary_never_seen_title(self):
        title = self.titles[-1]
        matches = match_papers_in_query(f"Summarize the approach in {title}.", self.titles)
        self.assertEqual(matches, [(title, 1.0)])

    def test_classify_paper_scope(self):
        self.assertEqual(classify_paper_scope([]), "collection")
        self.assertEqual(classify_paper_scope([("Paper A", 1.0)]), "single")
        self.assertEqual(classify_paper_scope([("Paper A", 1.0), ("Paper B", 0.8)]), "multi")

    def test_score_title_match_case_and_punctuation_insensitive(self):
        score = score_title_match(
            "tell me about ADAPTIVE-CONTROL FOR URBAN NETWORKS",
            "Adaptive Control for Urban Networks",
        )
        self.assertGreaterEqual(score, 0.99)

    def test_get_collection_papers_and_cache_invalidation(self):
        class FakeVManager:
            collection_name = "test_collection_xyz"

            def get_all_chunks(self):
                return [
                    {"metadata": {"paper_title": "Paper One"}},
                    {"metadata": {"paper_title": "Paper One"}},
                    {"metadata": {"paper_title": "Paper Two"}},
                ]

        vm = FakeVManager()
        self.assertEqual(get_collection_papers(vm), ["Paper One", "Paper Two"])
        vm.get_all_chunks = lambda: [{"metadata": {"paper_title": "Paper Three"}}]
        self.assertEqual(get_collection_papers(vm), ["Paper One", "Paper Two"])
        invalidate_paper_cache("test_collection_xyz")
        self.assertEqual(get_collection_papers(vm), ["Paper Three"])


if __name__ == "__main__":
    unittest.main()
