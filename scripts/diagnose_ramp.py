import json

# Find CE stage entries with KEPT ramp metering chunks
with open('logs/pipeline_debug.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total log lines: {len(lines)}")

found = 0
for i, line in enumerate(lines):
    try:
        entry = json.loads(line)
        stage = entry.get('stage_name', '')
        if 'Cross Encoder' in stage:
            data = entry.get('data', {})
            evald = data.get('evaluated_chunks', [])
            ramp_chunks = [ec for ec in evald if 'Ramp' in ec.get('filename','') or 'ramp' in ec.get('filename','')]
            if ramp_chunks and any(ec.get('status') == 'KEPT' for ec in ramp_chunks):
                found += 1
                print(f"\n=== Line {i}: CE stage with KEPT ramp chunks ===")
                for ec in evald[:12]:
                    rank = ec["rank"]
                    score = ec["combined_score"]
                    status = ec["status"]
                    filename = ec["filename"][:60]
                    print(f"  rank={rank} score={score:.4f} status={status} file={filename}")
                if found >= 3:
                    break
    except Exception:
        pass

print(f"\nTotal occurrences found: {found}")
