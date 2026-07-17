import unittest
from agents.router import route, AGENT_CODE, AGENT_DATA, AGENT_REASONING

class TestRouter(unittest.TestCase):
    def test_code_query(self):
        agent, confidence = route("What does the load_repository function do?")
        self.assertEqual(agent, AGENT_CODE)
        self.assertGreater(confidence, 0)

    def test_data_query(self):
        agent, confidence = route("How many files are in the repository?")
        self.assertEqual(agent, AGENT_DATA)
        self.assertGreater(confidence, 0)

    def test_reasoning_query(self):
        agent, confidence = route("Why does the system use tree-sitter instead of regex?")
        self.assertEqual(agent, AGENT_REASONING)
        self.assertGreater(confidence, 0)

    def test_low_confidence_escalates(self):
        # A very vague query that triggers nothing clearly
        agent, confidence = route("hello")
        # Should escalate to reasoning_agent due to low confidence
        self.assertEqual(agent, AGENT_REASONING)

if __name__ == "__main__":
    unittest.main()
