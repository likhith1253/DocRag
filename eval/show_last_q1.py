import json

target = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
logs_path = 'logs/query_logs.jsonl'
last=None
last_line=None
with open(logs_path, 'r', encoding='utf-8') as f:
    for i,line in enumerate(f, start=1):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get('question') == target:
            last = entry
            last_line = i
if last:
    print('last line', last_line)
    print(json.dumps(last, indent=2, ensure_ascii=True))
else:
    print('not found')
