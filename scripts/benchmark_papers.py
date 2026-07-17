import os
import time
import json
import glob
from ingestion.pdf_parser import parse_pdf, get_sections_with_pages
from ingestion.doc_chunker import chunk_document
from storage.vector_store import _get_encoder

BASE_PAPERS_DIR = "d:/DocRag/papers"

def run_benchmarks():
    results = []
    
    # Initialize Encoder just for benchmarking to avoid Qdrant file locks
    print("Loading embedding model...")
    encoder = _get_encoder("all-MiniLM-L6-v2")
    
    papers = glob.glob(f"{BASE_PAPERS_DIR}/**/*.pdf", recursive=True)
    
    print(f"Starting detailed benchmarking for {len(papers)} papers...")
    
    for i, paper_path in enumerate(papers):
        paper_stats = {
            "file": os.path.basename(paper_path),
            "collection": os.path.basename(os.path.dirname(paper_path))
        }
        
        try:
            # 1. Parsing Time
            start_parse = time.time()
            parsed = parse_pdf(paper_path)
            sections = get_sections_with_pages(parsed)
            parse_time = time.time() - start_parse
            paper_stats["parse_time_sec"] = parse_time
            
            # 2. Chunking Time
            start_chunk = time.time()
            chunks = chunk_document(
                file_path=paper_path,
                sections=sections,
                paper_title=parsed.get("title", ""),
                authors=parsed.get("authors", ""),
                year=parsed.get("year", ""),
                collection_id="benchmark_collection"
            )
            chunk_time = time.time() - start_chunk
            paper_stats["chunk_time_sec"] = chunk_time
            paper_stats["num_chunks"] = len(chunks)
            
            # 3. Embedding Time (Only if chunks > 0)
            if chunks:
                start_embed = time.time()
                texts = [c["content"] for c in chunks]
                encoder.encode(texts, show_progress_bar=False)
                embed_time = time.time() - start_embed
                paper_stats["embedding_time_sec"] = embed_time
            else:
                paper_stats["embedding_time_sec"] = 0.0
                
            paper_stats["total_ingest_time_sec"] = parse_time + chunk_time + paper_stats["embedding_time_sec"]
            paper_stats["status"] = "Success"
            
        except Exception as e:
            paper_stats["status"] = f"Error: {str(e)}"
            
        results.append(paper_stats)
        print(f"[{i+1}/{len(papers)}] {paper_stats['file']} - {paper_stats['status']}")
        
        # Save incrementally
        with open("d:/DocRag/scripts/paper_benchmarks.json", "w") as f:
            json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_benchmarks()
