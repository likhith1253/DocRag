#!/usr/bin/env python3
"""
Rebuild expected answers by retrieving ACTUAL paper content,
focusing on Abstract/Introduction/Methodology sections.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval.vector_search import search_vector

questions = [
    ("Q1", "What is the main contribution of the deep reinforcement learning approach for ramp metering?", "main_contribution"),
    ("Q2", "How does the paper address ramp metering using reinforcement learning?", "methodology"),
    ("Q3", "What are the experimental results for traffic flow in the ramp metering study?", "results"),
    ("Q4", "What approach is used for automatic compliance checking in privacy documents?", "main_contribution"),
    ("Q5", "What datasets were used to evaluate privacy document compliance?", "experimental_setup"),
    ("Q6", "What is the DynamicK recommendation approach for personalized decisions?", "main_contribution"),
    ("Q7", "What are the key hyperparameters and algorithmic details in DynamicK?", "hyperparameters"),
    ("Q8", "Why do fuzzy commitments offer insufficient protection according to this paper?", "main_contribution"),
    ("Q9", "How does portfolio-based algorithm selection relate to generalization performance?", "methodology"),
    ("Q10", "How does the paper address contradictions in NLP tasks?", "main_contribution"),
    ("Q11", "What is the approach for modelling human routines and social practices?", "methodology"),
    ("Q12", "What are the main FPGA acceleration techniques for deep learning?", "main_contribution"),
    ("Q13", "What algorithms are proposed for AI-based power grid voltage control?", "methodology"),
    ("Q14", "What are skeleton-based approaches in machine vision for action recognition?", "methodology"),
]

# Filter function - exclude References, only use content sections
def is_valid_section(section_text):
    if not section_text:
        return False
    bad_keywords = ["references", "bibliography", "appendix", "supplementary", "code", "github"]
    return not any(kw in section_text.lower() for kw in bad_keywords)

print("\n" + "="*120)
print("REBUILDING EXPECTED ANSWERS FROM ACTUAL PAPER CONTENT")
print("="*120 + "\n")

new_answers = []

for qid, question, category in questions:
    print(f"\n{qid}: {question}")
    print("-" * 120)
    
    result = search_vector(question, top_k=10)
    if isinstance(result, tuple):
        chunks = result[0]
    else:
        chunks = result
    
    # Find best chunks from valid sections
    best_chunks = [c for c in chunks if is_valid_section(c.get('metadata', {}).get('section'))][:3]
    
    if not best_chunks:
        print("  WARNING: No valid chunks found!")
        best_chunks = chunks[:2]
    
    # Extract content for expected answer
    combined_text = " ".join([c.get('content', '')[:300] for c in best_chunks])
    
    # Show what we're using
    for chunk in best_chunks:
        meta = chunk.get('metadata', {})
        section = meta.get('section', 'Unknown')
        title = meta.get('title', '')
        print(f"  [{section}] {title}")
    
    print(f"  CONTENT:\n    {combined_text[:400]}...")
    
    # Extract key concepts (words appearing frequently in chunks)
    from collections import Counter
    words = combined_text.lower().split()
    words = [w.strip('.,;:()[]') for w in words if len(w) > 3]
    common_words = [w for w, _ in Counter(words).most_common(10) if w not in 
                    ['that', 'this', 'with', 'from', 'using', 'based', 'paper', 'approach', 'method', 'model']]
    
    key_concepts = common_words[:5]
    
    expected = {
        "id": qid,
        "paper": best_chunks[0].get('metadata', {}).get('title', 'Unknown.pdf'),
        "question": question,
        "expected_answer": combined_text[:300],  # Use actual paper text
        "key_concepts": key_concepts,
        "category": category
    }
    
    new_answers.append(expected)
    print(f"  KEY CONCEPTS: {key_concepts}\n")

print("\n" + "="*120)
print("Saving to eval/ai_papers_expected_answers_REBUILD.json")
print("="*120)

with open('eval/ai_papers_expected_answers_REBUILD.json', 'w') as f:
    json.dump(new_answers, f, indent=2)

print("\nDone! Review the file and rename to ai_papers_expected_answers.json if approved.")
