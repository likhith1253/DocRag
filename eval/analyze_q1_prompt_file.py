import re, sys, os
p='eval/q1_prompt.txt'
with open(p,'r',encoding='utf-8') as f:
    s=f.read()

system_prompt = 'You are a research assistant answering questions about academic papers.'
count_system = s.count(system_prompt)
count_doc_excerpts = s.count('Document Excerpts:')
excerpt_matches = list(re.finditer(r"\[EXCERPT\s+\d+\]", s))
num_excerpts = len(excerpt_matches)

# Extract each excerpt block
excerpt_blocks = []
for i,m in enumerate(excerpt_matches):
    start = m.start()
    end = excerpt_matches[i+1].start() if i+1 < len(excerpt_matches) else len(s)
    excerpt_blocks.append(s[start:end])

excerpt_lengths = [len(b) for b in excerpt_blocks]

print('system_prompt_count=', count_system)
print('document_excerpts_count=', count_doc_excerpts)
print('num_excerpt_blocks=', num_excerpts)
print('total_chars=', len(s))
for i,l in enumerate(excerpt_lengths[:50], start=1):
    print(f'EXCERPT {i} chars={l}')

# detect repetitions of header sequence (first 12 lines)
header = s.splitlines()[:20]
header_text='\n'.join(header)
occ_header = s.count(header_text)
print('\nfirst-20-lines occurrences=', occ_header)

# find if the full grounding header repeated many times consecutively
pattern = re.escape('\n'.join(header))

# find longest run of repeated header-like block at start
print('\nPreview start (first 500 chars):')
print(s[:500])

# Find the span where the first EXCERPT occurs
if excerpt_matches:
    print('\nIndex of first excerpt match:', excerpt_matches[0].start())
    print('Chars before first excerpt:', excerpt_matches[0].start())

# Search for unexpected large repetitions of 'Document Excerpts:' location
locs = [m.start() for m in re.finditer('Document Excerpts:', s)]
print('Document Excerpts positions (first 20):', locs[:20])

# check whether the header repeated N times equals number of 'Document Excerpts:' occurrences
print('\nDone')
