import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

checkpoints_dir = 'eval/scientific_validation/checkpoints'
questions = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']

full_audit = {}

for q in questions:
    qpath = os.path.join(checkpoints_dir, q)
    with open(os.path.join(qpath, 'question.json'), encoding='utf-8') as f:
        qdata = json.load(f)['data']
    with open(os.path.join(qpath, 'metrics.json'), encoding='utf-8') as f:
        mdata = json.load(f)['data']
    with open(os.path.join(qpath, 'retrieved_chunks.json'), encoding='utf-8') as f:
        rdata = json.load(f)['data']
    with open(os.path.join(qpath, 'claim_verification.json'), encoding='utf-8') as f:
        cdata = json.load(f)['data']
    with open(os.path.join(qpath, 'expanded_evidence.json'), encoding='utf-8') as f:
        edata = json.load(f)['data']

    full_audit[q] = {
        'question': qdata,
        'metrics': mdata,
        'retrieved': rdata,
        'claims': cdata,
        'expanded': edata
    }

print(f"Loaded checkpoints for {len(full_audit)} questions.")

# Dump a json report of all claims across Q1-Q5
claims_summary = []
for q, data in full_audit.items():
    c_list = data['claims']
    if isinstance(c_list, dict):
        c_list = c_list.get('claim_verification', [])
    for idx, c in enumerate(c_list):
        claims_summary.append({
            'question_id': q,
            'claim_idx': idx + 1,
            'claim': c.get('claim') or c.get('claim_text'),
            'status': c.get('status') or c.get('grounding_status'),
            'confidence': c.get('confidence'),
            'reason': c.get('reason') or c.get('reasoning'),
            'quoted_evidence': c.get('quoted_evidence'),
            'verification_error': c.get('verification_error'),
            'top_evidence_count': len(c.get('top_evidence', []))
        })

print(f"Total claims across Q1-Q5: {len(claims_summary)}")
with open('eval/claims_summary.json', 'w', encoding='utf-8') as f:
    json.dump(claims_summary, f, indent=2)

