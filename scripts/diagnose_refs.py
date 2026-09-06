import json, re

_LOW_VALUE_SECTION_RE = re.compile(
    r'\b(references?|bibliography|acknowledgements?|acknowledgments?)\b',
    re.IGNORECASE,
)

TARGET_IDS = [
    '1ed11bde-c00d-42af-9979-3087e17c6b14',
    '4ed61f4b-2502-4f7a-8e22-4ffcc59dda3a',
    'b905c9fc-8297-4723-b16f-d6fdca760a5d',
]

with open('logs/pipeline_debug.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[1094:], start=1095):
    try:
        entry = json.loads(line)
        rid = entry.get('request_id', '')
        if rid not in TARGET_IDS:
            continue
        
        stage = entry.get('stage_name', '')
        data = entry.get('data', {})
        
        if 'Filtering' in stage:
            before = data.get('before_count', 'N/A')
            after = data.get('after_count', 'N/A')
            removed = data.get('removed_chunks_details', [])
            print(f"\n[Line {i}] [{rid[:8]}] FILTERING: before={before} after={after}")
            for r in removed:
                print(f"  REMOVED: {r.get('reason_removed','?')} | file={str(r.get('filename',''))[:40]}")
        
        elif 'Cross Encoder' in stage:
            evald = data.get('evaluated_chunks', [])
            refs_chunks = [ec for ec in evald if 'References' in str(ec.get('section', '')) or 'bibliography' in str(ec.get('section', '')).lower()]
            if refs_chunks:
                print(f"\n[Line {i}] [{rid[:8]}] CE STAGE: References section chunks:")
                for ec in refs_chunks:
                    sec_raw = repr(ec.get('section',''))
                    print(f"  rank={ec['rank']} score={ec['combined_score']:.4f} status={ec['status']} section_raw={sec_raw}")
                    matches = _LOW_VALUE_SECTION_RE.search(ec.get('section', ''))
                    print(f"  -> regex would filter? {bool(matches)}")
    except Exception as e:
        pass
