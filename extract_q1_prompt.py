import json

# Read query logs to find the exact prompt for Q1
with open('logs/query_logs.jsonl', 'r') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('question') == 'What is the main contribution of the deep reinforcement learning approach for ramp metering?':
            print('=== EXACT PROMPT SENT TO LLM ===')
            # The prompt is not directly stored in logs, but we can reconstruct it from the retrieved chunks
            print('Retrieved chunks count:', len(entry.get('retrieved_chunks', [])))
            print()
            print('=== RETRIEVED CHUNKS FROM LOGS ===')
            for i, chunk in enumerate(entry.get('retrieved_chunks', [])[:10]):
                metadata = chunk.get('metadata', {})
                print(f'Chunk {i+1} (Page {metadata.get("page_start", "?")}-{metadata.get("page_end", "?")}):')
                print(f'  Paper: {metadata.get("paper_title", "unknown")}')
                print(f'  Section: {metadata.get("section", "unknown")}')
                print(f'  Content: {chunk.get("content", "")[:400]}...')
                print()
            break
