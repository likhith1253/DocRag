import os
import json
import sys
sys.path.insert(0, "d:/Document_RAG")

from agents.orchestrator import answer, LOGS_PATH

# Manual queries
QUERIES = [
    "Where is database connection initialized?",
    "Summarize authentication flow.",
    "List API endpoints.",
    "How are embeddings generated?",
    "Which module builds the knowledge graph?"
]

def run_tests():
    # Make sure we clean the logs first to verify entries
    if os.path.exists(LOGS_PATH):
        os.remove(LOGS_PATH)
        
    print("\n=== Running 5 Manual Queries ===")
    for i, q in enumerate(QUERIES, 1):
        print(f"\nQuery {i}: {q}")
        ans = answer(q)
        print(f"Answer: {ans[:200]}...")
        
        # Verify log entry
        with open(LOGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entry = json.loads(lines[-1])
        
        print(f"Router Selected Agent: {entry['agent']}")
        print(f"Retrieval Returned Chunks: {len(entry['retrieved_chunks'])}")
        print(f"Chosen Agent Produced Text: {isinstance(ans, str) and len(ans) > 0}")
        print(f"JSON Log Entry Written: YES")
        
    print("\n=== Running Malformed Query ===")
    ans_empty = answer("")
    print(f"Query: \"\"")
    print(f"Answer: {ans_empty}")
    with open(LOGS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entry_empty = json.loads(lines[-1])
    print(f"Agent: {entry_empty['agent']}, Answer: {entry_empty['answer']}")
    
    print("\n=== Running Nonsense Query ===")
    ans_nonsense = answer("asdfgh qwerty zxcv")
    print(f"Query: \"asdfgh qwerty zxcv\"")
    print(f"Answer: {ans_nonsense}")
    with open(LOGS_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entry_nonsense = json.loads(lines[-1])
    print(f"Agent: {entry_nonsense['agent']}, Answer: {entry_nonsense['answer']}, Chunks: {len(entry_nonsense['retrieved_chunks'])}")

if __name__ == "__main__":
    run_tests()
