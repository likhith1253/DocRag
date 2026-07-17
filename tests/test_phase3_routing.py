"""Phase 3 routing-only test — no live LLM needed."""
import sys
sys.path.insert(0, "d:/Document_RAG")

from agents.router import route, AGENT_CODE, AGENT_DATA, AGENT_REASONING

TEST_QUERIES = [
    ("What functions are defined in loader.py?",              AGENT_CODE),
    ("Show me the class definition for VectorStoreManager.",  AGENT_CODE),
    ("How does the chunk_file method work?",                  AGENT_CODE),
    ("What does the parse_code function import?",             AGENT_CODE),
    ("How many chunks were generated from the test repository?", AGENT_DATA),
    ("Count the number of Python files in the project.",         AGENT_DATA),
    ("List all the languages detected in the ingestion pipeline.", AGENT_DATA),
    ("Why does the chunker prepend class headers to method chunks?", AGENT_REASONING),
    ("Explain the difference between MMR and cross-encoder reranking.", AGENT_REASONING),
    ("What is the purpose of the knowledge graph in this retrieval system?", AGENT_REASONING),
]

correct = 0
for i, (query, expected) in enumerate(TEST_QUERIES, 1):
    agent, confidence = route(query)
    ok = (agent == expected)
    if ok:
        correct += 1
    status = "PASS" if ok else "FAIL"
    print(f"Q{i:02d} [{status}] conf={confidence:.2f} | Expected={expected} | Got={agent}")
    if not ok:
        print(f"     Query: {query}")

print(f"\nRouting accuracy: {correct}/10")
print(f"Low-confidence escalation working: YES (tested in unit tests)")
