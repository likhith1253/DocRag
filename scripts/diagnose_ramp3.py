import json

# Focus on the RECENT power grid queries (lines 1095+)
with open('logs/pipeline_debug.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total log lines: {len(lines)}")

# Look at lines >= 1095 only  
print("\n=== RECENT log entries (lines 1095+) for power grid query ===")
for i, line in enumerate(lines[1094:], start=1095):
    try:
        entry = json.loads(line)
        stage = entry.get('stage_name', '')
        data = entry.get('data', {})
        rid = entry.get('request_id', 'unknown')
        
        if 'Incoming Request' in stage:
            q = data.get('user_question', '')[:80]
            print(f"\n[Line {i}] INCOMING REQUEST [{rid}]: {q}")
        
        elif 'Cross Encoder' in stage:
            threshold = data.get('threshold_applied', 'N/A')
            above = data.get('above_threshold_count', 'N/A')
            dropped = data.get('dropped_by_threshold', 'N/A')
            out_count = data.get('output_chunks_count', 'N/A')
            evald = data.get('evaluated_chunks', [])
            
            print(f"\n[Line {i}] CE STAGE [{rid}]: threshold={threshold} above={above} dropped={dropped} output={out_count}")
            for ec in evald:
                rank = ec.get('rank')
                score = ec.get('combined_score', 'N/A')
                status = ec.get('status', '?')
                filename = ec.get('filename', '?')[:60]
                print(f"  rank={rank} score={score:.4f if isinstance(score, float) else score} status={status} file={filename}")
    except Exception as e:
        pass
