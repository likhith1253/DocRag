import sys, os
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from storage.vector_store import VectorStoreManager
question = "What is the main contribution of the deep reinforcement learning approach for ramp metering?"
paper = "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"

vman = VectorStoreManager(collection_name='chunks')
print('Searching with metadata filter file=filename')
chunks, timing = vman.search(question, top_k=100, metadata_filters={'file': paper})
print('Returned:', len(chunks))
for i,c in enumerate(chunks[:5]):
    print(i, c.get('metadata',{}).get('file'))

print('\nSearching without metadata filter')
chunks2, timing2 = vman.search(question, top_k=100, metadata_filters=None)
print('Returned:', len(chunks2))
for i,c in enumerate(chunks2[:5]):
    print(i, c.get('metadata',{}).get('file'))
