import json

# Focus on the specific power grid query request IDs
TARGET_IDS = [
    '1ed11bde-c00d-42af-9979-3087e17c6b14',
    '4ed61f4b-2502-4f7a-8e22-4ffcc59dda3a',
    'b905c9fc-8297-4723-b16f-d6fdca760a5d',
]

with open('logs/pipeline_debug.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total log lines: {len(lines)}")

for i, line in enumerate(lines[1094:], start=1095):
    try:
        entry = json.loads(line)
        rid = entry.get('request_id', '')
        if rid not in TARGET_IDS:
            continue
        
        stage = entry.get('stage_name', '')
        data = entry.get('data', {})
        
        if 'Cross Encoder' in stage:
            threshold = data.get('threshold_applied', 'N/A')
            above = data.get('above_threshold_count', 'N/A')
            dropped = data.get('dropped_by_threshold', 'N/A')
            out_count = data.get('output_chunks_count', 'N/A')
            evald = data.get('evaluated_chunks', [])
            print(f"\n[Line {i}] [{rid[:8]}] CE STAGE: threshold={threshold} above={above} dropped={dropped} output={out_count}")
            for ec in evald:
                rank = ec.get('rank')
                score = ec.get('combined_score', 'N/A')
                status = ec.get('status', '?')
                filename = ec.get('filename', '?')[:65]
                section = ec.get('section', '?')[:30]
                if status == 'KEPT':
                    print(f"  KEPT rank={rank} score={score:.4f} file={filename} sect={section}")
        
        elif 'Context Assembly' in stage:
            chunks_in = data.get('chunks_entering_prompt', [])
            print(f"\n[Line {i}] [{rid[:8]}] CONTEXT ASSEMBLY: {len(chunks_in)} chunks")
            for c in chunks_in:
                print(f"  rank={c.get('rank')} file={str(c.get('filename',''))[:60]} score={c.get('score', 'N/A')} chars={c.get('character_count')}")
        
        elif 'Prompt Builder' in stage:
            chars = data.get('prompt_size_chars', 'N/A')
            tokens = data.get('approx_prompt_token_count', 'N/A')
            depth = data.get('answer_depth', 'N/A')
            print(f"\n[Line {i}] [{rid[:8]}] PROMPT: {chars} chars, ~{tokens} tokens, depth={depth}")
        
        elif 'HFTransformers' in stage:
            gen_cfg = data.get('generation_config', {})
            max_tok = gen_cfg.get('max_new_tokens', 'N/A')
            gen_count = data.get('generated_token_count', 'N/A')
            stop = data.get('stop_reason', 'N/A')
            gen_ms = data.get('generation_time_ms', 'N/A')
            print(f"\n[Line {i}] [{rid[:8]}] LLM: max_new_tokens={max_tok} generated={gen_count} stop={stop} gen_ms={gen_ms}")
    except Exception as e:
        pass
