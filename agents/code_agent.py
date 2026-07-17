from llm.backend import generate
from typing import List, Dict, Any

def run(query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Code agent: answers code-related questions using retrieved chunks.
    Calls llm.backend.generate() — never imports Ollama/Transformers directly.
    
    Args:
        query: The user query.
        chunks: Retrieved chunks from Phase 2 retrieval pipeline.
        
    Returns:
        Generated answer string.
    """
    # Limit number of chunks and truncate long chunk content to reduce token usage
    def _shorten(chunk, max_chars=1000):
        content = chunk.get('content', '')
        if len(content) > max_chars:
            return content[:max_chars] + "\n...[truncated]"
        return content

    context = "\n\n".join(
        f"[File: {c['metadata'].get('file', 'unknown')} | "
        f"Class: {c['metadata'].get('class')} | "
        f"Function: {c['metadata'].get('function')}]\n{_shorten(c)}"
        for c in chunks[:3]
    )
    
    prompt = (
        "You are a code analysis assistant. Use the following code context to answer the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer concisely and cite the relevant file/function when applicable:"
    )
    
    return generate(prompt, model_key="code_agent_model", chunk_count=min(len(chunks), 3))
