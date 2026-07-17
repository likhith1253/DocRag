import os
import json
import sys
import numpy as np
from sentence_transformers import util

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.backend import generate
from storage.vector_store import VectorStoreManager

CATEGORIES = [
    "Code Search",
    "Data Extraction",
    "Reasoning",
    "Architecture",
    "Debugging",
    "Dependency",
    "Security",
    "Performance"
]

def generate_qa_for_category(category: str, context: str) -> dict:
    prompt = f"""You are an expert AI dataset generator.
Generate EXACTLY 1 high-quality Q&A pair for the category '{category}' based strictly on the following repository context.

Context:
{context}

Output your response as a valid JSON object with EXACTLY these keys:
"question": the generated question
"answer": the answer to the question
"category": "{category}"
"sources": list of file paths from the Context that support the answer
"confidence": a float between 0.0 and 1.0 representing your confidence that the answer is perfectly correct and fully supported by the context without any hallucination.

Ensure the answer is factually correct. Return ONLY the raw JSON object. Do not include markdown formatting or backticks.
"""
    response_text = generate(prompt, model_key="reasoning_agent_model")
    
    try:
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
            
        data = json.loads(response_text)
        if isinstance(data, dict):
             if all(k in data for k in ["question", "answer", "category", "sources", "confidence"]):
                 if isinstance(data["sources"], list):
                     return data
    except Exception as e:
        print(f"Error parsing JSON from LLM: {e}")
    return None

def verify_candidate(qa: dict, context: str) -> tuple[bool, str]:
    """Automated verification step to check answerability, hallucination, and source support."""
    prompt = f"""You are a strict QA auditor. Review the following Q&A pair against the provided context.
    
Context:
{context}

Q&A Pair:
Question: {qa['question']}
Answer: {qa['answer']}
Category: {qa['category']}
Sources: {qa['sources']}

Verify the following:
1. Question is answerable from retrieved chunks.
2. Answer does not hallucinate information outside retrieved context.
3. Source files actually support the answer.
4. Question belongs to the requested category.

Output ONLY a valid JSON object:
{{
  "pass": true or false,
  "reason": "Brief explanation if false, else 'pass'"
}}
Return ONLY the JSON. Do not include markdown formatting or backticks.
"""
    response_text = generate(prompt, model_key="reasoning_agent_model")
    try:
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        data = json.loads(response_text.strip())
        return data.get("pass", False), data.get("reason", "Failed to parse reasoning")
    except Exception:
        return False, "Failed to parse verification response"

def validate_sources(sources: list) -> bool:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for source in sources:
        full_path = os.path.join(project_root, source)
        if not os.path.exists(full_path):
            return False
    return True

def is_duplicate(question: str, existing_questions: list, existing_embeddings: list, encoder) -> tuple[bool, str]:
    if question in existing_questions:
        return True, "Exact match duplicate"
    if not existing_questions:
        return False, ""
    
    q_emb = encoder.encode(question)
    similarities = util.cos_sim(q_emb, existing_embeddings)[0]
    if len(similarities) > 0 and max(similarities) > 0.85:
        return True, "Semantic duplicate"
    return False, ""

def main():
    store = VectorStoreManager()
    encoder = store.encoder
    output_file = os.path.join(os.path.dirname(__file__), "test_dataset.json")
    
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                dataset = json.load(f)
            except:
                dataset = []
    else:
        dataset = []

    existing_questions = [d['question'] for d in dataset]
    existing_embeddings = []
    if existing_questions:
        existing_embeddings = encoder.encode(existing_questions).tolist()

    print("Starting Phase 6B dataset generation pipeline...")
    
    accepted_count = 0
    rejected_count = 0
    rejection_reasons = []

    for category in CATEGORIES:
        print(f"\n{'='*40}")
        print(f"Category: {category}")
        print(f"{'='*40}")
        
        retrieved_chunks = store.search(f"{category} in python repository architecture code reasoning", top_k=5)
        if not retrieved_chunks:
            print(f"Reject: No chunks retrieved for category {category}")
            rejected_count += 1
            rejection_reasons.append(f"{category}: No context chunks")
            continue
            
        context_parts = []
        for i, c in enumerate(retrieved_chunks):
            file_name = c['metadata'].get('file', 'Unknown')
            context_parts.append(f"--- Chunk {i+1} (File: {file_name}) ---\n{c['content']}")
        context = "\n\n".join(context_parts)
        
        qa = generate_qa_for_category(category, context)
        if not qa:
            print("Reject: Failed schema validation")
            rejected_count += 1
            rejection_reasons.append(f"{category}: Schema/JSON failed")
            continue
            
        # 1. Answer length
        if len(qa['answer']) > 1500 or len(qa['answer']) < 10:
            print(f"Reject: Answer length unreasonable ({len(qa['answer'])} chars)")
            rejected_count += 1
            rejection_reasons.append(f"{category}: Length")
            continue

        # 2. Source files
        if not validate_sources(qa['sources']):
            print(f"Reject: Sources do not exist {qa['sources']}")
            rejected_count += 1
            rejection_reasons.append(f"{category}: Invalid sources")
            continue

        # 3. Confidence filter
        conf = float(qa.get('confidence', 0))
        if conf < 0.8:
            print(f"Reject: Low confidence ({conf})")
            rejected_count += 1
            rejection_reasons.append(f"{category}: Low confidence ({conf})")
            continue

        # 4. Duplicate Detection
        is_dup, dup_reason = is_duplicate(qa['question'], existing_questions, existing_embeddings, encoder)
        if is_dup:
            print(f"Reject: {dup_reason}")
            rejected_count += 1
            rejection_reasons.append(f"{category}: {dup_reason}")
            continue

        # 5. Automated Verification (Hallucination, Support)
        passed_verification, v_reason = verify_candidate(qa, context)
        if not passed_verification:
            print(f"Reject: LLM Verification failed - {v_reason}")
            rejected_count += 1
            rejection_reasons.append(f"{category}: Verif - {v_reason}")
            continue

        # Human Review
        print("\n--- Human Verification ---")
        print(f"Category: {qa['category']}")
        print(f"Question: {qa['question']}")
        print(f"Answer:   {qa['answer']}")
        print(f"Sources:  {qa['sources']}")
        print(f"Confidence: {conf}")
        
        while True:
            user_input = input("\nAccept this Q&A pair? (y/n/skip): ").strip().lower()
            if user_input in ['y', 'yes', 'n', 'no', 'skip']:
                break
            print("Invalid input.")
            
        if user_input in ['y', 'yes']:
            # Strip confidence before saving as it's not needed in final dataset
            qa_to_save = {k: v for k, v in qa.items() if k != "confidence"}
            dataset.append(qa_to_save)
            existing_questions.append(qa['question'])
            if len(existing_embeddings) == 0:
                existing_embeddings = encoder.encode([qa['question']]).tolist()
            else:
                new_emb = encoder.encode([qa['question']]).tolist()[0]
                existing_embeddings.append(new_emb)
                
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(dataset, f, indent=2)
            accepted_count += 1
            print("Accepted.")
        else:
            rejected_count += 1
            rejection_reasons.append(f"{category}: Human rejected")
            print("Rejected.")

    print(f"\n--- Phase 6B Run Complete ---")
    print(f"Questions Generated Attempted: 8")
    print(f"Accepted: {accepted_count}")
    print(f"Rejected: {rejected_count}")
    print("Rejection Reasons:")
    for r in rejection_reasons:
        print(f"- {r}")
        
if __name__ == "__main__":
    main()
