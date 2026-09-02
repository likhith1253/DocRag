import unittest

from retrieval.query_analyzer import detect_evidence_intent


class TestEvidenceIntent(unittest.TestCase):
    """Phase 3 Part B: evidence-sensitive query detection."""

    def test_equation_sensitive_query(self):
        for q in [
            "What is the objective function?",
            "Give the update equation.",
            "What is the SAC maximum-entropy objective?",
        ]:
            self.assertTrue(detect_evidence_intent(q)["equation"], q)

    def test_table_sensitive_query(self):
        for q in [
            "Compare the performance in Table 2.",
            "What quantitative improvement did they report?",
        ]:
            self.assertTrue(detect_evidence_intent(q)["table"] or detect_evidence_intent(q)["numerical"], q)

    def test_figure_sensitive_query(self):
        for q in [
            "Explain Figure 1.",
            "What is the architecture?",
            "Describe the information flow shown in the diagram.",
        ]:
            self.assertTrue(detect_evidence_intent(q)["figure"], q)

    def test_algorithm_sensitive_query(self):
        for q in [
            "Describe the training algorithm.",
            "How does the asynchronous update work?",
        ]:
            intent = detect_evidence_intent(q)
            self.assertTrue(intent["algorithm"] or intent["numerical"] is not None, q)

    def test_algorithm_keyword_directly(self):
        self.assertTrue(detect_evidence_intent("What algorithm is used for training?")["algorithm"])

    def test_numerical_sensitive_query(self):
        self.assertTrue(detect_evidence_intent("What were the Atari scores?")["numerical"])

    def test_comparison_query_can_be_numerical(self):
        intent = detect_evidence_intent("Compare DQN, A3C and SAC based on their experimental results.")
        self.assertTrue(intent["numerical"])

    def test_generic_query_has_no_evidence_intent(self):
        intent = detect_evidence_intent("What is the capital of France?")
        self.assertFalse(any(intent.values()))

    def test_multiple_intents_can_be_true_at_once(self):
        intent = detect_evidence_intent("Explain the equation and the results table together.")
        self.assertTrue(intent["equation"])
        self.assertTrue(intent["table"])


if __name__ == "__main__":
    unittest.main()
