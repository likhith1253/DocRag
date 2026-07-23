import sys, os, json
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

dataset_path = os.path.join('eval','ai_papers_expected_answers.json')
with open(dataset_path,'r',encoding='utf-8') as f:
    data = json.load(f)

results=[]
for it in data:
    qid = it['id']
    paper = it['paper']
    q = it['question']
    ans, bd = answer(q, repo_id=None, filters={'file': paper}, retrieval_mode='corpus')
    # read last log entry for this question
    with open('logs/query_logs.jsonl','r',encoding='utf-8') as lf:
        lines = lf.readlines()
    last=None
    for line in reversed(lines):
        e=json.loads(line)
        if e.get('question')==q:
            last=e; break
    cnt = len(last.get('retrieved_chunks',[])) if last else 0
    results.append((qid, cnt, ans[:80]))

for r in results:
    print(r[0], 'chunks=', r[1], 'answer_preview=', r[2])
