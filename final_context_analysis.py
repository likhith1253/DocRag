#!/usr/bin/env python3
import os, json, sys, re
from datetime import datetime

LOGS_PATH = os.path.join('logs','query_logs.jsonl')
RUNS_DIR = os.path.join('eval','results')
EXPECTED_PATH = os.path.join('eval','ai_papers_expected_answers.json')

# load expected map
expected_map = {}
if os.path.exists(EXPECTED_PATH):
    with open(EXPECTED_PATH,'r',encoding='utf-8') as f:
        for it in json.load(f):
            expected_map[it.get('id')] = it

# pick latest run_results.json
runs = [os.path.join(RUNS_DIR,d) for d in os.listdir(RUNS_DIR) if os.path.isdir(os.path.join(RUNS_DIR,d))]
if not runs:
    print('No runs found in eval/results')
    sys.exit(1)
runs = sorted(runs, key=os.path.getmtime)
latest = runs[-1]
run_file = os.path.join(latest,'run_results.json')
if not os.path.exists(run_file):
    print('No run_results.json in', latest)
    sys.exit(1)
with open(run_file,'r',encoding='utf-8') as f:
    run = json.load(f)

# load logs and keep last entry per question
last_logs = {}
if os.path.exists(LOGS_PATH):
    with open(LOGS_PATH,'r',encoding='utf-8',errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
                q = e.get('question')
                last_logs[q]=e
            except:
                continue

# helper: first 300 chars
def first_n(s,n=300):
    s = s.replace('\n',' ')
    return s[:n]

# helper: sentence splitter
sent_split = re.compile(r'(?<=[.!?])\s+')

analysis = []
for item in run:
    q = item.get('question')
    qid = item.get('id')
    expected = item.get('expected','')
    expected_core = expected
    km = expected_map.get(qid, {})
    key_concepts = km.get('key_concepts',[]) if km else []

    log = last_logs.get(q)
    chunks = log.get('retrieved_chunks',[]) if log else []

    chunk_entries = []
    found_support=False
    matched_sentence=None
    matched_chunk=None
    for c in chunks:
        md = c.get('metadata',{})
        cid = c.get('id') or md.get('hash') or ''
        paper = md.get('paper_title') or md.get('file') or md.get('file_name') or md.get('file', '')
        section = md.get('section','')
        page_start = md.get('page_start',None)
        page_end = md.get('page_end',None)
        content = c.get('content','')
        first300 = first_n(content,300)
        chunk_entries.append({
            'chunk_id': cid,
            'paper': paper,
            'section': section,
            'page_start': page_start,
            'page_end': page_end,
            'first_300': first300,
            'full': content
        })
        # check if expected_core or any key concept appears in this chunk
        # match whole expected phrase or key concept
        low = content.lower()
        # check exact expected sentences
        if expected_core and expected_core.strip() and expected_core.strip().lower() in low:
            found_support=True
            # find sentence containing it
            sents = sent_split.split(content)
            for s in sents:
                if expected_core.strip().lower() in s.lower():
                    matched_sentence = s.strip()
                    break
            matched_chunk = cid
        if not found_support and key_concepts:
            for kc in key_concepts:
                if kc.lower() in low:
                    found_support=True
                    # find sentence
                    sents = sent_split.split(content)
                    for s in sents:
                        if kc.lower() in s.lower():
                            matched_sentence = s.strip()
                            break
                    matched_chunk = cid
                    break

    # if not found in final chunks, search all indexed chunks for that paper to determine whether parser produced it
    found_in_index=False
    index_locations=[]
    if not found_support:
        # try to locate collection file in registry to get collection name
        # fallback: scan logs for any chunks belonging to this paper in any log entry
        # For speed, scan the logs file for any occurrence of expected phrase (simple heuristic)
        if os.path.exists(LOGS_PATH):
            with open(LOGS_PATH,'r',encoding='utf-8',errors='replace') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except:
                        continue
                    chunks_all = e.get('retrieved_chunks',[])
                    for c in chunks_all:
                        cont = c.get('content','').lower()
                        if (expected_core and expected_core.strip().lower() in cont) or any(kc.lower() in cont for kc in key_concepts):
                            found_in_index=True
                            md = c.get('metadata',{})
                            index_locations.append({'chunk_id': c.get('id') or md.get('hash'), 'file': md.get('file') or md.get('paper_title'), 'section': md.get('section')})
                            # break
                    if found_in_index:
                        break
    # determine final verdict YES/NO
    verdict = 'YES' if found_support else 'NO'

    # if NO, determine likely cause using evidence
    cause = None
    if verdict=='NO':
        if not chunks:
            cause = 'Document routing / Zero chunks retrieved (no final context)'
        else:
            if found_in_index:
                cause = 'Retrieval/MMR/Reranker/Context packing (information present in index but not in final chunks)'
            else:
                cause = 'Parser/Chunking (information not present in any retrieved chunks)' 

    analysis.append({
        'id': qid,
        'question': q,
        'expected': expected_core,
        'key_concepts': key_concepts,
        'final_chunks': chunk_entries,
        'found_in_final_context': found_support,
        'matched_sentence': matched_sentence,
        'matched_chunk_id': matched_chunk,
        'found_in_index_elsewhere': found_in_index,
        'index_locations': index_locations,
        'determined_cause': cause
    })

# save results
out_path = os.path.join('eval','results','final_context_analysis.json')
with open(out_path,'w',encoding='utf-8') as f:
    json.dump(analysis,f,indent=2,ensure_ascii=False)
print('Wrote', out_path)

# print concise summary grouping
reached = sum(1 for a in analysis if a['found_in_final_context'])
not_reached = len(analysis)-reached
print('Reached Qwen:', reached)
print('Never reached Qwen:', not_reached)

# print per-question minimal report to stdout in requested format
for a in analysis:
    print('\n' + ('='*80))
    print('Question:', a['question'])
    print('\nExpected Answer:\n')
    print(a['expected'])
    print('\n' + ('-'*50))
    for c in a['final_chunks']:
        print('\nChunk ID:', c['chunk_id'])
        print('Paper:', c['paper'])
        print('Section:', c['section'])
        print('Page:', f"{c.get('page_start')} - {c.get('page_end')}")
        print('First 300 chars:\n')
        print(c['first_300'])
        print('\n' + ('-'*50))
    print('\nDoes the final context contain required info?')
    print(a['found_in_final_context'] and 'YES' or 'NO')
    if a['found_in_final_context']:
        print('\nSupporting sentence:')
        print(a['matched_sentence'])
        print('\nWhy model may have failed to extract it:')
        print('LLM reasoning or answer synthesis gap: the sentence exists verbatim in context but the model omitted or failed to use it when producing the answer.')
    else:
        print('\nMissing info:')
        if not a['final_chunks']:
            print('No chunks were provided as final context for this question.')
        else:
            print('Expected key concepts not found in the final chunks.')
        print('\nEvidence why it never reached Qwen:')
        print(a['determined_cause'])

print('\nSummary:')
print('Reached Qwen', reached)
print('Never reached Qwen', not_reached)
