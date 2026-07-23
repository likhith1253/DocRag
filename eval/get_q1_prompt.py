import os, sys, json
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from storage.vector_store import VectorStoreManager, _get_config
# Preload retrieval submodules to avoid local module shadowing
import importlib.util, types
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mmr_path = os.path.join(repo_root, 'retrieval', 'mmr_rerank.py')
ce_path = os.path.join(repo_root, 'retrieval', 'cross_encoder_rerank.py')

spec = importlib.util.spec_from_file_location('retrieval.mmr_rerank', mmr_path)
mmr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mmr)

spec2 = importlib.util.spec_from_file_location('retrieval.cross_encoder_rerank', ce_path)
ce = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ce)

pkg = types.ModuleType('retrieval')
setattr(pkg, 'mmr_rerank', mmr)
setattr(pkg, 'cross_encoder_rerank', ce)
import sys
sys.modules['retrieval'] = pkg
sys.modules['retrieval.mmr_rerank'] = mmr
sys.modules['retrieval.cross_encoder_rerank'] = ce

from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder
import agents.doc_agent as doc_agent

question = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
paper = "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"

config = _get_config()
vector_top_k = config.get('retrieval', {}).get('vector_top_k', 30)
rerank_top_k = config.get('retrieval', {}).get('rerank_top_k', 5)

vman = VectorStoreManager(collection_name='chunks')
# Step 1: vector search
chunks, timing = vman.search(question, top_k=vector_top_k, metadata_filters={'file': paper})
print('Retrieved chunks (count):', len(chunks))
for i,c in enumerate(chunks[:10], start=1):
    meta=c.get('metadata',{})
    print(f'{i}. id={c.get("id")} file={meta.get("file")} section={meta.get("section")} page={meta.get("page_start")}')
    preview=c.get('content','')[:300].replace('\n',' ')
    safe_preview = preview.encode('ascii','replace').decode('ascii')
    print('   ', safe_preview)

# Deduplicate by metadata.hash
seen=set(); uniq=[]
for c in chunks:
    h=c.get('metadata',{}).get('hash','')
    if h and h not in seen:
        seen.add(h); uniq.append(c)
chunks=uniq
print('\nAfter dedupe count:', len(chunks))

# Filter out references
filtered=[]
for c in chunks:
    sec=(c.get('metadata',{}).get('section') or '').lower()
    if any(x in sec for x in ['reference','bibliography','acknowledg']):
        continue
    filtered.append(c)
chunks=filtered
print('After section filter count:', len(chunks))

# MMR rerank
query_vector = timing.get('query_vector')
mmr_chunks = mmr_rerank(question, chunks, top_k=min(40,len(chunks)), query_vector=query_vector)
print('After MMR count:', len(mmr_chunks))
for i,c in enumerate(mmr_chunks[:5], start=1):
    meta=c.get('metadata',{})
    print(f' MMR {i}. id={c.get("id")} section={meta.get("section")} page={meta.get("page_start")}')

# Cross-encoder rerank
ce_chunks = rerank_cross_encoder(question, mmr_chunks, top_k=rerank_top_k)
print('After cross-encoder count:', len(ce_chunks))
for i,c in enumerate(ce_chunks[:10], start=1):
    meta=c.get('metadata',{})
    print(f' CE {i}. id={c.get("id")} section={meta.get("section")} page={meta.get("page_start")}')

# Context builder selection (orchestrator picks top 8 before doc_agent.run)
selected = ce_chunks[:8]
print('\nChunks selected by context builder (count):', len(selected))
for i,c in enumerate(selected, start=1):
    meta=c.get('metadata',{})
    print(f' S{i}. id={c.get("id")} paper={meta.get("file")} section={meta.get("section")} page={meta.get("page_start")}')
    preview = c.get('content','')[:300].replace('\n',' ')
    print('   ', preview.encode('ascii','replace').decode('ascii'))

# Build exact prompt without sending to LLM
valid_chunks = [c for c in selected if c.get('content','').strip()]
context_block = doc_agent._build_context_block(valid_chunks)
prompt = doc_agent._build_grounding_prompt(question, context_block)

# Save prompt to file for inspection
with open('eval/q1_prompt.txt','w',encoding='utf-8') as f:
    f.write(prompt)

# Also write the IDs at each stage to JSON
out = {
    'retrieved_ids':[c.get('id') for c in vman.search(question, top_k=vector_top_k, metadata_filters={'file': paper})[0]],
    'mmr_ids':[c.get('id') for c in mmr_chunks],
    'ce_ids':[c.get('id') for c in ce_chunks],
    'selected_ids':[c.get('id') for c in selected],
}
with open('eval/q1_stage_ids.json','w',encoding='utf-8') as f:
    json.dump(out,f,indent=2)

# Print safe summary and prompt stats
safe_prompt = prompt.encode('ascii','replace').decode('ascii')
print('\n=== PROMPT (ASCII-safe preview) ===')
print(safe_prompt[:2000])
print('...')
print('=== END PREVIEW ===\n')

# Token estimate using llm.backend heuristic
approx_tokens = int(len(prompt.split()) * 1.33)
print('Prompt chars:', len(prompt))
print('Prompt words:', len(prompt.split()))
print('Prompt tokens_approx:', approx_tokens)

# Check if any selected chunk was truncated by _MAX_EXCERPT_CHARS
truncated = []
for i,c in enumerate(valid_chunks, start=1):
    content = c.get('content','')
    if len(content) > 2000:
        truncated.append(i)
print('Chunks truncated in prompt (indices):', truncated)

# Check whether the expected answer sentence appears in prompt
expected_phrase = 'deep Q-learning'  # approximate key phrase from expected answer
contains = expected_phrase in prompt
print('Contains expected phrase ("deep Q-learning") in prompt?', contains)

# Also search for explicit sentence from expected answer
expected_sentence = 'The paper proposes a deep Q-learning approach for adaptive ramp metering'
print('Contains exact expected sentence?', expected_sentence in prompt)

print('\nSaved eval/q1_prompt.txt and eval/q1_stage_ids.json')
