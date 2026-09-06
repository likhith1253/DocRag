import json

# Find the SPECIFIC power grid query run and its CE stage data
with open('logs/pipeline_debug.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total log lines: {len(lines)}")

# First, find all incoming request entries to see query content
print("\n=== Recent Incoming Requests ===")
recent_requests = []
for i, line in enumerate(lines[-200:], start=max(0,len(lines)-200)):
    try:
        entry = json.loads(line)
        stage = entry.get('stage_name', '')
        if 'Incoming Request' in stage:
            data = entry.get('data', {})
            q = data.get('user_question', '')[:80]
            rid = data.get('request_id', '')
            recent_requests.append((i, rid, q))
    except:
        pass

for i, rid, q in recent_requests[-10:]:
    print(f"  Line {i}: [{rid}] {q}")

# Find CE stages adjacent to "power grid" query
print("\n=== CE Stages with scores ===")
for i, line in enumerate(lines):
    try:
        entry = json.loads(line)
        stage = entry.get('stage_name', '')
        if 'Cross Encoder' in stage:
            data = entry.get('data', {})
            evald = data.get('evaluated_chunks', [])
            threshold = data.get('threshold_applied', 'N/A')
            above = data.get('above_threshold_count', 'N/A')
            dropped = data.get('dropped_by_threshold', 'N/A')
            out_count = data.get('output_chunks_count', 'N/A')
            ramp_kept = [ec for ec in evald if ('Ramp' in ec.get('filename','') or 'ramp' in ec.get('filename','')) and ec.get('status') == 'KEPT']
            power_grid = [ec for ec in evald if 'Rethink' in ec.get('filename','') or 'Power_Grid' in ec.get('filename','')]
            if ramp_kept:
                print(f"\nLine {i}: threshold={threshold} above_threshold={above} dropped={dropped} output={out_count}")
                print(f"  Ramp KEPT: {[(ec['rank'], ec['combined_score']) for ec in ramp_kept]}")
                print(f"  Power Grid: {[(ec['rank'], ec['combined_score'], ec['status']) for ec in power_grid]}")
    except:
        pass
