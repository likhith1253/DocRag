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
        # These titles are synthetic / not part of any real benchmark set,
        # to prove the matcher generalizes rather than being tuned to the
        # six benchmark papers.
        self.titles = [
            "Playing Atari with Deep Reinforcement Learning",
            "Asynchronous Methods for Deep Reinforcement Learning",
            "Soft Actor-Critic",
            "A Deep Reinforcement Learning Approach for Ramp Metering",
            "Quantum Annealing for Combinatorial Auction Optimization",
        ]

    def test_exact_title_substring_match_scores_high(self):
        query = "Explain the training procedure used in Soft Actor-Critic."
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "Soft Actor-Critic")
        self.assertAlmostEqual(matches[0][1], 1.0)

    def test_multi_paper_full_title_mentions(self):
        query = (
            "Compare Playing Atari with Deep Reinforcement Learning, "
            "Asynchronous Methods for Deep Reinforcement Learning, and Soft Actor-Critic."
        )
        matches = match_papers_in_query(query, self.titles)
        matched_titles = {t for t, _ in matches}
        self.assertEqual(
            matched_titles,
            {
                "Playing Atari with Deep Reinforcement Learning",
                "Asynchronous Methods for Deep Reinforcement Learning",
                "Soft Actor-Critic",
            },
        )
        # The unrelated ramp-metering paper must not be swept in.
        self.assertNotIn("A Deep Reinforcement Learning Approach for Ramp Metering", matched_titles)

    def test_self_referential_acronym_match(self):
        # "SAC" is literally derivable from "Soft Actor-Critic"'s own initials —
        # this is the kind of abbreviation the matcher can generalize to
        # without an external database (unlike "DQN", which isn't spelled out
        # in its actual paper title and can't be derived this way).
        query = "How does SAC handle entropy regularization?"
        matches = match_papers_in_query(query, self.titles)
        matched_titles = {t for t, _ in matches}
        self.assertIn("Soft Actor-Critic", matched_titles)

    def test_topic_only_query_matches_no_specific_paper(self):
        query = "What papers discuss experience replay in reinforcement learning?"
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(matches, [])

    def test_unrelated_generic_query_does_not_match(self):
        query = "What is the capital of France?"
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(matches, [])

    def test_generalizes_to_arbitrary_never_seen_title(self):
        # Proves no hardcoding of specific benchmark paper names.
        query = "Summarize the approach in Quantum Annealing for Combinatorial Auction Optimization."
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "Quantum Annealing for Combinatorial Auction Optimization")

    def test_classify_paper_scope(self):
        self.assertEqual(classify_paper_scope([]), "collection")
        self.assertEqual(classify_paper_scope([("Paper A", 1.0)]), "single")
        self.assertEqual(classify_paper_scope([("Paper A", 1.0), ("Paper B", 0.8)]), "multi")

    def test_score_title_match_case_and_punctuation_insensitive(self):
        score = score_title_match(
            "tell me about PLAYING ATARI WITH DEEP-REINFORCEMENT-LEARNING",
            "Playing Atari with Deep Reinforcement Learning",
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
        titles = get_collection_papers(vm)
        self.assertEqual(titles, ["Paper One", "Paper Two"])

        # Cache hit: changing the backing data shouldn't matter until invalidated.
        vm.get_all_chunks = lambda: [{"metadata": {"paper_title": "Paper Three"}}]
        self.assertEqual(get_collection_papers(vm), ["Paper One", "Paper Two"])

        invalidate_paper_cache("test_collection_xyz")
        self.assertEqual(get_collection_papers(vm), ["Paper Three"])


if __name__ == "__main__":
    unittest.main()
