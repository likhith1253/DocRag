#!/usr/bin/env python3
"""
Extract actual expected answers from papers.
"""

import sys, os, json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval.vector_search import search_vector

questions = [
    ("Q1", "What is the main contribution of the deep reinforcement learning approach for ramp metering?", "A_Deep_Reinforcement_Learning"),
    ("Q2", "How does the paper address ramp metering using reinforcement learning?", "A_Deep_Reinforcement_Learning"),
    ("Q3", "What are the experimental results for traffic flow in the ramp metering study?", "A_Deep_Reinforcement_Learning"),
    ("Q4", "What approach is used for automatic compliance checking in privacy documents?", "Compliance_Generation"),
    ("Q5", "What datasets were used to evaluate privacy document compliance?", "Compliance_Generation"),
    ("Q6", "What is the DynamicK recommendation approach for personalized decisions?", "DynamicK"),
    ("Q7", "What are the key hyperparameters and algorithmic details in DynamicK?", "DynamicK"),
    ("Q8", "Why do fuzzy commitments offer insufficient protection according to this paper?", "Fuzzy_Commitments"),
    ("Q9", "How does portfolio-based algorithm selection relate to generalization performance?", "Generalization"),
    ("Q10", "How does the paper address contradictions in NLP tasks?", "I_like_fish"),
    ("Q11", "What is the approach for modelling human routines and social practices?", "Modelling_Human"),
    ("Q12", "What are the main FPGA acceleration techniques for deep learning?", "Overview_of_FPGA"),
    ("Q13", "What algorithms are proposed for AI-based power grid voltage control?", "Rethink_AI"),
    ("Q14", "What are skeleton-based approaches in machine vision for action recognition?", "Skeleton")
]

print("ACTUAL PAPER CONTENT FOR EXPECTED ANSWERS\n" + "="*100 + "\n")

for qid, question, paper_hint in questions:
    print(f"\n{qid}: {question}")
    print("-" * 100)
    
    result = search_vector(question, top_k=5)
    if isinstance(result, tuple):
        chunks = result[0]
    else:
        chunks = result
    
    # Show top 2 chunks
    for i, chunk in enumerate(chunks[:2], 1):
        meta = chunk.get('metadata', {})
        section = meta.get('section', '')
        content = chunk.get('content', '')[:250]
        print(f"  [Chunk {i}] Section: {section}")
        print(f"    {content}...")
        print()
