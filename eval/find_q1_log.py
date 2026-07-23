import json, os

# load latest run_results.json to get Q1 question
run_dir = 'eval/results'
# pick most recent results directory by timestamp-like name
entries = os.listdir(run_dir)
entries = [e for e in entries if os.path.isdir(os.path.join(run_dir,e))]
if not entries:
    print('No run results')
    exit(0)
# pick most recently modified results directory
entries.sort(key=lambda d: os.path.getmtime(os.path.join(run_dir,d)))
latest = entries[-1]
run_path = os.path.join(run_dir, latest, 'run_results.json')
print('Using results directory:', latest)
if not os.path.exists(run_path):
    print('run_results.json not found in', latest)
    exit(0)
with open(run_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
    if not data:
        print('empty run results')
        exit(0)
    q1 = data[0].get('question')
print('Looking for question in logs:', q1)
logs_path = os.path.join('logs','query_logs.jsonl')
found = False
with open(logs_path, 'r', encoding='utf-8') as f:
    for i,line in enumerate(f):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get('question') == q1:
            print('Found log entry at line', i+1)
            print(json.dumps(entry, indent=2, ensure_ascii=True))
            found=True
if not found:
    print('No matching log entry found for question')
