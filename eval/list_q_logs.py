import json

target = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
logs_path = 'logs/query_logs.jsonl'
with open(logs_path, 'r', encoding='utf-8') as f:
    for i,line in enumerate(f, start=1):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get('question') == target:
            cnt = len(entry.get('retrieved_chunks', []))
            print(f'line {i}: retrieved_chunks={cnt} answer={entry.get("answer")[:60] if entry.get("answer") else ""}')
