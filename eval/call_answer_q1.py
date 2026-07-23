import sys, os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Preload retrieval submodules to avoid eval/retrieval.py shadowing
import importlib.util, types
mmr_path = os.path.join(repo_root, 'retrieval', 'mmr_rerank.py')
ce_path = os.path.join(repo_root, 'retrieval', 'cross_encoder_rerank.py')

spec = importlib.util.spec_from_file_location('retrieval.mmr_rerank', mmr_path)
mmr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mmr)

spec2 = importlib.util.spec_from_file_location('retrieval.cross_encoder_rerank', ce_path)
ce = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ce)

pkg = types.ModuleType('retrieval')
setattr(pkg, 'mmr_rerank', mmr)
setattr(pkg, 'cross_encoder_rerank', ce)
import sys
sys.modules['retrieval'] = pkg
sys.modules['retrieval.mmr_rerank'] = mmr
sys.modules['retrieval.cross_encoder_rerank'] = ce

from agents.orchestrator import answer

q = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
paper = "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"

ans, bd = answer(q, repo_id=None, filters={"file": paper}, retrieval_mode='corpus')
print('Answer:', ans)
print('Latency breakdown:', bd)

import json
with open('logs/query_logs.jsonl','r',encoding='utf-8') as f:
    lines=f.readlines()
print('\nLast log entry:')
print(lines[-1])
