#!/usr/bin/env python3
import json, os

logs_path = 'logs/query_logs.jsonl'
expected_path = 'eval/ai_papers_expected_answers.json'
# load expected mapping
expected = {}
if os.path.exists(expected_path):
    with open(expected_path, 'r', encoding='utf-8') as f:
        lst = json.load(f)
        for it in lst:
            expected[it['id']] = it
# latest run results
rdir = os.path.join('eval','results')
subdirs = [os.path.join(rdir,d) for d in os.listdir(rdir) if os.path.isdir(os.path.join(rdir,d))]
subdirs = sorted(subdirs, key=os.path.getmtime)
run_file = os.path.join(subdirs[-1],'run_results.json')
run = []
if os.path.exists(run_file):
    with open(run_file,'r',encoding='utf-8') as f:
        run = json.load(f)
# load logs
logs = {}
if os.path.exists(logs_path):
    with open(logs_path,'r',encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
                logs[e.get('question')] = e
            except:
                pass

out = []
for item in run:
    q = item['question']
    qid = item.get('id')
    key_concepts = []
    if qid and qid in expected:
        key_concepts = expected[qid].get('key_concepts', [])
    retrieved = ''
    log = logs.get(q, {})
    chunks = log.get('retrieved_chunks', []) if log else []
    sections = [c.get('metadata', {}).get('section', '') for c in chunks]
    for c in chunks:
        retrieved += ' ' + (c.get('content') or '')
    answer = item.get('answer', '') or ''
    def cov(kc_list, text):
        if not kc_list:
            return 0.0
        t = text.lower(); m = 0
        for kc in kc_list:
            if kc.lower() in t:
                m += 1
        return round(100.0*m/len(kc_list), 2)
    rcov = cov(key_concepts, retrieved)
    acov = cov(key_concepts, answer)
    ref_flag = any('reference' in (s or '').lower() for s in sections)
    if rcov < 30.0:
        root = 'Retrieval'
    elif acov < 40.0:
        root = 'LLM Reasoning'
    else:
        root = 'Unknown'
    out.append({
        'id': qid,
        'question': q,
        'paper': item.get('paper'),
        'key_concepts': key_concepts,
        'retrieved_concept_coverage_percent': rcov,
        'answer_concept_coverage_percent': acov,
        'retrieved_sections': list(set(sections))[:5],
        'root_cause': root
    })
os.makedirs('eval/results', exist_ok=True)
with open('eval/results/diagnosis.json','w',encoding='utf-8') as f:
    json.dump(out,f,indent=2,ensure_ascii=False)
print('Wrote eval/results/diagnosis.json')
