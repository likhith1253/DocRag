"""
Offline LLM-as-a-Judge module for evaluating generated answers against expected answers
and checking for hallucination, entity attribution errors, and grounding failures.

This does NOT run in the production /query path to avoid adding latency.
It should be run offline over benchmark results.
"""

import json
import argparse
import sys
from pathlib import Path
import time

# Add parent directory to path so we can import modules
repo_root = Path(__file__).parent.parent.absolute()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from llm.backend import generate

JUDGE_SYSTEM_PROMPT = """You are an impartial and rigorous LLM Judge evaluating answers from a RAG pipeline.
Your job is to read the Provided Question, the Expected Correct Answer, the Actual Generated Answer, and the Grounding Context.
You must determine whether the Actual Generated Answer has any of the following failures:

1. ENTITY_ATTRIBUTION_ERROR: The model lists correct entities but attaches the wrong properties, mechanisms, or relationships to them based on proximity in the text, confusing one entity's properties for another.
2. GENERATION_HALLUCINATION: The model invents facts, methods, numbers, or results not present in the Grounding Context.
3. INSUFFICIENT_EVIDENCE: The Grounding Context did not contain the information needed to answer the question, but the model still tried to answer instead of stating it cannot find it, OR the model correctly stated it cannot find it (which means the failure was upstream in retrieval).
4. IRRELEVANT_ANSWER: The model answered something completely unrelated to the user's question or gave an overly verbose generic answer that failed to address the core question.
5. RETRIEVAL_FAILURE: The generated answer is "I cannot find this information" AND the Expected Correct Answer indicates the system should have known it, meaning retrieval failed to provide the necessary context.
6. NONE: The answer is factually correct, properly grounded, well-attributed, and directly answers the question.

Output your evaluation as a valid JSON object with EXACTLY two fields:
{
  "failure_category": "<one of the 6 categories above>",
  "reasoning": "<brief explanation of why you chose this category>"
}

Do not include any Markdown formatting blocks (e.g. ```json) around your output.
"""


def evaluate_benchmark(benchmark_file: str, output_file: str):
    """
    Run the LLM judge on a benchmark results file.
    Expects a JSON list of objects containing:
    - id
    - question
    - expected_answer
    - final_parsed_answer (the generated answer)
    - retrieved_chunks (list of chunk objects with 'content')
    """
    input_path = Path(benchmark_file)
    if not input_path.exists():
        print(f"Error: {benchmark_file} not found.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    results = []

    print(f"Starting Offline LLM Judge evaluation for {len(data)} items...")
    
    for i, item in enumerate(data):
        print(f"Evaluating item {i+1}/{len(data)} (ID: {item.get('id', 'unknown')})...")
        
        question = item.get("question", "")
        expected = item.get("expected_answer", "")
        actual = item.get("final_parsed_answer", item.get("raw_llm_answer", ""))
        
        # Reconstruct grounding context
        chunks = item.get("retrieved_chunks", [])
        context_text = "\n\n".join([c.get("content", "") for c in chunks])
        if not context_text:
            context_text = "No context retrieved."
            
        prompt = (
            f"{JUDGE_SYSTEM_PROMPT}\n"
            f"==================================================\n"
            f"QUESTION: {question}\n\n"
            f"EXPECTED ANSWER: {expected}\n\n"
            f"ACTUAL GENERATED ANSWER: {actual}\n\n"
            f"GROUNDING CONTEXT: {context_text}\n"
            f"==================================================\n"
            f"JSON OUTPUT:"
        )

        try:
            # We use the existing generate method but configure a long depth for the judge
            start_t = time.perf_counter()
            response = generate(
                prompt=prompt, 
                model_key="doc_agent_model", 
                request_id=f"judge_{item.get('id', 'idx_'+str(i))}", 
                answer_depth="DETAILED" # allows max tokens 1024
            )
            eval_ms = (time.perf_counter() - start_t) * 1000
            
            # Clean up potential markdown formatting from the response
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            elif clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            clean_response = clean_response.strip()
            
            try:
                eval_json = json.loads(clean_response)
            except json.JSONDecodeError:
                eval_json = {
                    "failure_category": "JSON_PARSE_ERROR",
                    "reasoning": f"Failed to parse LLM output: {response}"
                }
            
            item_result = {
                "id": item.get("id"),
                "question": question,
                "failure_category": eval_json.get("failure_category", "UNKNOWN"),
                "reasoning": eval_json.get("reasoning", ""),
                "eval_ms": eval_ms
            }
            results.append(item_result)
            
            print(f"  Result: {item_result['failure_category']} ({eval_ms:.0f}ms)")
            
        except Exception as e:
            print(f"  Error evaluating item: {e}")
            results.append({
                "id": item.get("id"),
                "failure_category": "EVAL_CRASH",
                "reasoning": str(e)
            })

    # Output results
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nEvaluation complete. Results saved to {out_path}")
    
    # Summary
    categories = {}
    for r in results:
        cat = r.get("failure_category", "UNKNOWN")
        categories[cat] = categories.get(cat, 0) + 1
        
    print("\nSummary of Failure Categories:")
    for cat, count in categories.items():
        print(f"  {cat}: {count} ({(count/len(results))*100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline LLM Judge")
    parser.add_argument("--benchmark", required=True, help="Path to benchmark JSON containing generation results")
    parser.add_argument("--output", default="eval/results/judge_results.json", help="Path to output evaluation JSON")
    args = parser.parse_args()
    
    evaluate_benchmark(args.benchmark, args.output)