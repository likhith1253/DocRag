import json, os

# find latest results dir
run_dir = 'eval/results'
entries = [e for e in os.listdir(run_dir) if os.path.isdir(os.path.join(run_dir,e))]
entries.sort(key=lambda d: os.path.getmtime(os.path.join(run_dir,d)))
latest = entries[-1]
run_path = os.path.join(run_dir, latest, 'run_results.json')
print('Using results dir:', latest)
with open(run_path, 'r', encoding='utf-8') as f:
    runs = json.load(f)

logs_path = os.path.join('logs','query_logs.jsonl')
if not os.path.exists(logs_path):
    print('No logs found')
    exit(1)

# build index of last log entry per question (scan file once, keep last matching)
last_by_q = {}
with open(logs_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            e = json.loads(line)
        except Exception:
            continue
        q = e.get('question')
        if q:
            last_by_q[q] = e

# check each run item
results = []
for item in runs:
    q = item.get('question')
    entry = last_by_q.get(q)
    cnt = 0
    if entry:
        cnt = len(entry.get('retrieved_chunks', []))
    results.append({'id': item.get('id'), 'question': q, 'retrieved_chunks_count': cnt})

print(json.dumps(results, indent=2))
