import os, sys, json
os.environ["DISABLE_PROMPT_CACHE"] = "1"
sys.path.insert(0, r"d:\DocRag")

from agents.orchestrator import answer

question = "How does the paper address contradictions in NLP tasks?"
print("=== TESTING TARGET QUESTION (Q10) ===")
print("Question:", question)

ans, bd, chunks, citations = answer(
    query=question,
    repo_id="71e2cffe-8756-4ff3-b35c-52fc94babdd4",
    filters={},
    retrieval_mode="single"
)

print("\n" + "="*70)
print("ANSWER:")
print("="*70)
print(ans)
print("\n" + "="*70)
print("RETRIEVED CHUNKS SUMMARY:")
print("="*70)
print(f"Total chunks delivered to LLM: {len(chunks)}")
for i, c in enumerate(chunks, 1):
    m = c.get("metadata", {})
    doc = m.get("file") or m.get("paper_title") or "Unknown"
    sec = m.get("section", "?")
    p1 = m.get("page_start", "?")
    score = c.get("score", 0.0)
    print(f"  Chunk #{i:2d} | doc={doc} | sec='{sec}' | p={p1} | score={score:.4f}")
