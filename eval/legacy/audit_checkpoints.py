import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

checkpoints_dir = 'eval/scientific_validation/checkpoints'
questions = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']

summary_data = {}

for q in questions:
    print(f"===================== {q} =====================")
    qpath = os.path.join(checkpoints_dir, q)
    
    # 1. Question
    with open(os.path.join(qpath, 'question.json'), encoding='utf-8') as f:
        qdata = json.load(f)['data']
        print(f"Paper: {qdata.get('paper')}")
        print(f"Question: {qdata.get('question')}")
        print(f"Expected Answer: {qdata.get('expected_answer')}")
        print(f"Difficulty: {qdata.get('difficulty')}, Evidence Type: {qdata.get('evidence_type')}")
    
    # 2. Metrics
    with open(os.path.join(qpath, 'metrics.json'), encoding='utf-8') as f:
        mdata = json.load(f)['data']
        print("\n--- METRICS ---")
        print(json.dumps(mdata, indent=2))
        
    # 3. Retrieved Chunks
    with open(os.path.join(qpath, 'retrieved_chunks.json'), encoding='utf-8') as f:
        rdata = json.load(f)['data']
        chunks = rdata.get('retrieved_chunks', [])
        print(f"\n--- RETRIEVED CHUNKS ({len(chunks)}) ---")
        repos = set()
        for c in chunks:
            repos.add(c.get('pdf_filename'))
            print(f"  Index {c.get('chunk_index')}: PDF={c.get('pdf_filename')}, Page={c.get('page')}, Section={c.get('section')}, Sim={c.get('similarity')}")
        print(f"  Unique PDFs retrieved for {q}: {list(repos)}")

    # 4. Claim Verification
    with open(os.path.join(qpath, 'claim_verification.json'), encoding='utf-8') as f:
        cdata = json.load(f)['data']
        print(f"\n--- CLAIM VERIFICATION SUMMARY ---")
        if isinstance(cdata, list):
            claims_list = cdata
        elif isinstance(cdata, dict):
            claims_list = cdata.get('claim_verification', [])
        
        print(f"Total claims in verification output: {len(claims_list)}")
        for idx, item in enumerate(claims_list):
            print(f"\n  [Claim {idx+1}]")
            print(f"    Claim Text: {item.get('claim') or item.get('claim_text')}")
            print(f"    Status: {item.get('status') or item.get('grounding_status')}")
            print(f"    Confidence: {item.get('confidence')}")
            print(f"    Quoted Evidence: {item.get('quoted_evidence')}")
            print(f"    Reasoning: {item.get('reasoning') or item.get('reason')}")
            top_ev = item.get('top_evidence', [])
            print(f"    Top Evidence items ({len(top_ev)}):")
            for ev in top_ev:
                print(f"      - Page {ev.get('page')}, Section {ev.get('section')}: Status={ev.get('verification_status')}, Conf={ev.get('verification_confidence')}, Reason={ev.get('verification_reason')}")

    print("\n\n")
