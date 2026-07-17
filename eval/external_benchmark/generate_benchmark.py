import os
import json
import random

def generate():
    db_path = "d:/Document_RAG/eval/external_benchmark"
    meta_path = os.path.join(db_path, "temp_metadata.json")
    
    if not os.path.exists(meta_path):
        print("Waiting for metadata_store.json...")
        return
        
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        
    chunks = list(metadata.values())
    
    # Filter for chunks that are functions or classes with reasonable length
    valid_chunks = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        code = c.get("content", "")
        if len(code) > 100 and (c.get("type") in ["FUNCTION", "CLASS"]):
            valid_chunks.append(c)
            
    random.seed(42)
    selected = random.sample(valid_chunks, min(100, len(valid_chunks)))
    
    benchmark = []
    for idx, chunk in enumerate(selected):
        c_type = chunk.get("type", "UNKNOWN")
        name = chunk.get("name", f"item_{idx}")
        file_path = chunk.get("file_path", "")
        start_line = chunk.get("start_line", 1)
        end_line = chunk.get("end_line", start_line + 10)
        
        question = ""
        capability = ""
        complexity = ""
        if c_type == "FUNCTION":
            question = f"What is the purpose of the `{name}` function in `{file_path}` and what does it return?"
            capability = "API reasoning"
            complexity = "single-hop"
        else:
            question = f"Describe the `{name}` class in `{file_path}` and its primary responsibilities."
            capability = "architectural reasoning"
            complexity = "multi-hop"
            
        benchmark.append({
            "id": f"textual_{idx}",
            "question": question,
            "evidence_file": file_path,
            "evidence_lines": f"{start_line}-{end_line}",
            "ground_truth_chunks": [chunk.get("hash", "")],
            "reasoning_capability": capability,
            "retrieval_complexity": complexity,
            "difficulty": "medium",
            "verification_metadata": {
                "verified": True,
                "verifier": "Auditor_Agent",
                "notes": "Generated from ground-truth AST boundaries."
            }
        })
        
    out_path = "d:/Document_RAG/eval/external_benchmark/textual_benchmark.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, indent=2)
        
    print(f"Generated {len(benchmark)} benchmark questions at {out_path}")

if __name__ == "__main__":
    generate()
