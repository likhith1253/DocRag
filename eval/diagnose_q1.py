import sys, json, os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from storage.registry import get_registry
from storage.vector_store import VectorStoreManager, _get_config
# Defer imports of retrieval modules to avoid shadowing by eval/retrieval.py
mmr_rerank = None
rerank_cross_encoder = None

question = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
paper = "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"

import importlib, importlib.util
print('sys.path preview:')
for p in sys.path[:10]:
    print('  ', p)
# inspect how 'retrieval' will be resolved
spec = importlib.util.find_spec('retrieval')
print('retrieval spec:', spec)
if spec and spec.origin:
    print('retrieval origin:', spec.origin)

# now import retrieval submodules explicitly using importlib
try:
    retrieval = importlib.import_module('retrieval')
    mmr_rerank = importlib.import_module('retrieval.mmr_rerank').mmr_rerank
    rerank_cross_encoder = importlib.import_module('retrieval.cross_encoder_rerank').rerank_cross_encoder
    print('Imported retrieval.mmr_rerank and retrieval.cross_encoder_rerank OK')
except Exception as e:
    print('Failed to import retrieval submodules:', e)

print('\nQ1 question:', question)
registry = get_registry()
# find repo containing the paper by scanning collections' sample metadata
found=None
for rid, repo in registry.repositories.items():
    coll = repo.vector_collection
    if not coll:
        continue
    try:
        vman = VectorStoreManager(collection_name=coll)
        # try to fetch some chunks to inspect metadata
        all_chunks = vman.get_all_chunks(limit=50)
        for ch in all_chunks:
            meta = ch.get('metadata',{})
            fn = meta.get('file') or meta.get('paper') or meta.get('paper_title')
            if fn and paper in fn:
                found=(rid, repo, coll)
                break
        if found:
            break
    except Exception as e:
        # ignore
        pass

if not found:
    print('Repository for paper not found in registry. Will try global collection "chunks"')
    coll = 'chunks'
else:
    rid, repo, coll = found
    print('Detected repo_id:', rid)
    print('Repository name:', repo.name)
    print('Collection:', coll)

vman = VectorStoreManager(collection_name=coll)
print('\nStage: Vector search (top_k=100)')
chunks, timing = vman.search(question, top_k=100, metadata_filters={'file': paper})
print('Vector timing:', timing)
print('Number of chunks returned:', len(chunks))
for i,ch in enumerate(chunks[:10]):
    meta = ch.get('metadata',{})
    print(f'  [{i}] id={meta.get("chunk_id") or meta.get("hash") or "<no-id>"} section={meta.get("section")} file={meta.get("file")}')

# apply orchestrator-like metadata filtering (exclude references/bibliography)
filtered=[]
removed_reasons=[]
for ch in chunks:
    sec = (ch.get('metadata',{}).get('section') or '').lower()
    if any(x in sec for x in ['reference','bibliography','acknowledg']):
        removed_reasons.append(('section_filter', ch.get('metadata',{}).get('chunk_id')))
        continue
    filtered.append(ch)
print('\nAfter metadata filtering: ', len(filtered), 'removed:', len(removed_reasons))

# dedupe by hash
seen=set(); uniq=[]; dup_removed=0
for ch in filtered:
    h = ch.get('metadata',{}).get('hash','')
    if h and h in seen:
        dup_removed+=1
        continue
    seen.add(h); uniq.append(ch)
print('After dedupe: ', len(uniq), 'duplicates removed:', dup_removed)

# MMR rerank
if uniq:
    mmr_res = mmr_rerank(question, uniq, top_k=min(40,len(uniq)))
    print('After MMR rerank:', len(mmr_res))
else:
    print('MMR skipped (no chunks)')

# Cross-encoder rerank
if uniq:
    cross = rerank_cross_encoder(question, uniq, top_k=20)
    print('After cross-encoder rerank:', len(cross))
    for i,ch in enumerate(cross[:5]):
        meta=ch.get('metadata',{})
        print(f'  rerank[{i}] id={meta.get("chunk_id")} score={ch.get("score") if ch.get("score") is not None else "<no-score>"} sec={meta.get("section")}')
else:
    print('Cross-encoder skipped (no chunks)')

# Also try corpus-wide search (no metadata filter)
print('\nStage: Corpus-wide vector search (top_k=100, no filters)')
cb_chunks, cb_timing = vman.search(question, top_k=100, metadata_filters=None)
print('Corpus vector timing:', cb_timing)
print('Corpus chunks returned:', len(cb_chunks))
for i,ch in enumerate(cb_chunks[:10]):
    meta=ch.get('metadata',{})
    print(f'  [{i}] id={meta.get("chunk_id")} file={meta.get("file")} section={meta.get("section")}')
