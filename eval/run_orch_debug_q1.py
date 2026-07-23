import sys, os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Ensure project root and package dirs are first to avoid local module shadowing
retrieval_pkg = os.path.join(repo_root, 'retrieval')
if retrieval_pkg not in sys.path:
    sys.path.insert(0, retrieval_pkg)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Preload retrieval submodules to avoid local module shadowing (eval/retrieval.py)
import importlib.util, types
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

from agents.orchestrator import retrieve_node

q = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
paper = "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"

state = {
    'question': q,
    'agent': '',
    'retrieved_chunks': [],
    'citations': [],
    'answer': '',
    'error': '',
    'repo_id': None,
    'filters': {'file': paper},
    'retrieval_mode': 'corpus',
}

try:
    res = retrieve_node(state)
    import json
    print('retrieve_node result:')
    print(json.dumps(res, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()

print('\n--- Debug log last lines ---')
dbg_path = os.path.join('logs', 'retrieve_debug.jsonl')
if os.path.exists(dbg_path):
    with open(dbg_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for l in lines[-10:]:
        print(l.strip())
else:
    print('no debug file')
