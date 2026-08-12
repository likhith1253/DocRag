import os
import sys

repo_root = os.path.abspath(".")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agents.orchestrator import Orchestrator
from storage.pipeline_logger import forensic_tracer
import storage.vector_store

# Mock generate so we don't wait for LLM
from unittest.mock import patch
def fast_main():
    with patch("llm.transformers_backend.HFTransformersBackend.generate", return_value="MOCKED_ANSWER"):
        q1 = "What algorithms are proposed for AI-based power grid voltage control?"
        q2 = "What are skeleton-based approaches in machine vision for action recognition?"
        
        orch = Orchestrator()
        
        for q in [q1, q2]:
            print(f"\n======================================")
            print(f"QUERY: {q}")
            print(f"======================================")
            orch.answer(q)
            
            stage6 = None
            stage7 = None
            if hasattr(forensic_tracer, "stages"):
                for s in forensic_tracer.stages:
                    if s.get("stage_name") == "Cross Encoder":
                        stage6 = s["data"]
                    if s.get("stage_name") == "Prompt Builder":
                        stage7 = s["data"]
            
            if stage6:
                print(f"CrossEncoder input: {stage6.get('input_chunks_count')} chunks")
                print(f"Threshold applied: {stage6.get('threshold_applied')} (Dropped: {stage6.get('dropped_by_threshold')})")
                eval_log = stage6.get('evaluated_chunks', [])
                for c in eval_log:
                    if c.get('status') == 'KEPT':
                        print(f"  [KEPT] Paper: {c.get('filename')} | Raw CE: {c.get('ce_score')} | Final Score: {c.get('combined_score')}")
            
            if stage7:
                print(f"\nPrompt Characters: {stage7.get('prompt_length_chars')}")
                print(f"Total tokens estimated: {stage7.get('total_tokens_estimated')}")
                print(f"Excerpts merged: {stage7.get('total_excerpts_inserted')} from {stage7.get('papers_grouped')} papers")

fast_main()