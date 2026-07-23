import json

data = json.load(open('eval/results/comprehensive/results.json'))
q1 = [d for d in data if d['question_id'] == 'Q1'][0]

print('=== ORIGINAL QUESTION ===')
print(q1['question'])
print()

print('=== EXPECTED ANSWER ===')
print(q1['expected_answer'])
print()

print('=== RETRIEVED CHUNKS ===')
print(f'Number of chunks: {len(q1["retrieved_chunks"])}')
print(f'Type of first chunk: {type(q1["retrieved_chunks"][0])}')
print()

# Check if chunks are stored as strings or dicts
if q1['retrieved_chunks']:
    first_chunk = q1['retrieved_chunks'][0]
    if isinstance(first_chunk, str):
        print('Chunks are stored as strings (content only)')
        for i, chunk in enumerate(q1['retrieved_chunks']):
            print(f'Chunk {i+1}:')
            print(f'  Content: {chunk[:500]}...')
            print()
    else:
        print('Chunks are stored as dictionaries')
        for i, chunk in enumerate(q1['retrieved_chunks']):
            print(f'Chunk {i+1}:')
            print(f'  Data: {str(chunk)[:500]}...')
            print()

print('=== RAW LLM OUTPUT ===')
print(q1['raw_llm_answer'])
print()

print('=== PARSED/FINAL ANSWER ===')
print(q1['final_parsed_answer'])
print()

print('=== GROUNDING STATEMENTS ===')
for stmt in q1['grounding_statements']:
    print(f'Statement: {stmt["statement"][:100]}...')
    print(f'  Supported: {stmt["supported"]}')
    print(f'  Chunk (Page {stmt["page"]}): {stmt["chunk"][:100]}...')
    print(f'  Similarity: {stmt["similarity"]}')
    print(f'  Hallucination: {stmt["is_hallucination"]}')
    print()

print('=== SEMANTIC SIMILARITY COMPUTATION ===')
print(f'Score: {q1["semantic_similarity"]}')
print('Method: difflib.SequenceMatcher ratio() * 100')
print(f'Expected: "{q1["expected_answer"][:50]}..."')
print(f'Generated: "{q1["raw_llm_answer"][:50]}..."')
print()

print('=== GROUNDING SCORE COMPUTATION ===')
print(f'Score: {q1["grounding_score"]}')
print('Method: Count of supported statements / total statements * 100')
print(f'Supported: {sum(1 for s in q1["grounding_statements"] if s["supported"])}')
print(f'Total: {len(q1["grounding_statements"])}')
print(f'Ratio: {sum(1 for s in q1["grounding_statements"] if s["supported"]) / max(1, len(q1["grounding_statements"])) * 100}')
