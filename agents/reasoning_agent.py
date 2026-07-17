from llm.backend import generate
from typing import List, Dict, Any

def run(query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Reasoning agent: handles complex reasoning, explanation, and analysis questions.
    Used when confidence is low OR query requires multi-step reasoning.
    Calls llm.backend.generate() — never imports Ollama/Transformers directly.
    
    Args:
        query: The user query.
        chunks: Retrieved chunks from Phase 2 retrieval pipeline.
        
    Returns:
        Generated answer string with reasoning.
    """
    # Limit number of chunks and truncate long chunk content to reduce token usage
    def _shorten(chunk, max_chars=1000):
        content = chunk.get('content', '')
        if len(content) > max_chars:
            return content[:max_chars] + "\n...[truncated]"
        return content

    context = "\n\n".join(
        f"[File: {c['metadata'].get('file', 'unknown')} | "
        f"Language: {c['metadata'].get('language')}]\n{_shorten(c)}"
        for c in chunks[:3]
    )
    
    prompt = (
        "You are an expert reasoning assistant analyzing a code repository. "
        "Use the following code context and your reasoning ability to answer the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Provide a detailed, reasoned answer explaining the 'why' and 'how', not just the 'what':"
    )
    
    return generate(prompt, model_key="reasoning_agent_model", chunk_count=min(len(chunks), 3))
