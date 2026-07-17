import sys
sys.path.insert(0, "d:/Document_RAG")

from agents.orchestrator import answer

def main():
    print("\n--- Running ONE manual query with instrumentation ---")
    query = "Where is database connection initialized?"
    answer(query)

if __name__ == "__main__":
    main()
