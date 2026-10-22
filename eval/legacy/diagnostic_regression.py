import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agents.orchestrator import Orchestrator
from storage.pipeline_logger import forensic_tracer
import time

def run_query(q):
    print(f"\n{'='*50}\nQUERY: {q}\n{'='*50}")
    
    # We clear the tracer stages before running
    if hasattr(forensic_tracer, "stages"):
        forensic_tracer.stages.clear()
        
    orch = Orchestrator()
    
    t0 = time.time()
    response = orch.answer(q)
    t_total = time.time() - t0
    
    stage6 = None
    stage7 = None
    stage10 = None
    
    if hasattr(forensic_tracer, "stages"):
        for s in forensic_tracer.stages:
            name = s.get("stage_name")
            if name == "Cross Encoder":
                stage6 = s["data"]
            elif name == "Prompt Builder":
                stage7 = s["data"]
            elif name == "HFTransformersBackend.generate":
                stage10 = s["data"]
                
    if stage6:
        print(f"CrossEncoder candidates (input chunks): {stage6.get('input_chunks_count')}")
        eval_log = stage6.get('evaluated_chunks', [])
        rejected = [c for c in eval_log if c.get('status') == 'DROPPED']
        accepted = [c for c in eval_log if c.get('status') == 'KEPT']
        print(f"Rejected chunks: {len(rejected)}")
        print(f"Accepted chunks: {len(accepted)}")
        
    if stage7:
        print(f"Final papers: {stage7.get('papers_grouped')}")
        print(f"Prompt chars: {stage7.get('prompt_length_chars')}")
        print(f"Prompt tokens (est): {stage7.get('total_tokens_estimated')}")
        
    if stage10:
        print(f"Generated tokens: {stage10.get('generated_token_count')}")
        conf = stage10.get('generation_config', {})
        print(f"max_new_tokens: {conf.get('max_new_tokens')}")
        print(f"Generation time: {stage10.get('generation_time_ms', 0)/1000.0:.2f} s")
        print(f"Stop reason: {stage10.get('stop_reason')}")
        
    print(f"Total request time: {t_total:.2f} s")

def main():
    q1 = "What algorithms are proposed for AI-based power grid voltage control?"
    q2 = "What are skeleton-based approaches in machine vision for action recognition?"
    run_query(q1)
    run_query(q2)

if __name__ == "__main__":
    main()