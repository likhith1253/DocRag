#!/usr/bin/env python3
"""
Re-index the AI Papers folder with the latest parser.
"""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.pdf_parser import parse_pdf, get_sections_with_pages
from ingestion.doc_chunker import chunk_document
from storage.vector_store import VectorStoreManager
from storage.metadata_store import MetadataStoreManager

def reindex_ai_papers():
    ai_papers_dir = Path("papers/AI")
    if not ai_papers_dir.exists():
        print(f"Error: {ai_papers_dir} does not exist")
        return False
    
    meta_manager = MetadataStoreManager("./metadata_store.json")
    v_manager = VectorStoreManager()
    collection_id = str(uuid.uuid4())
    
    pdf_files = sorted(ai_papers_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to reindex\n")
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}] {pdf_path.name}", end=" ")
        sys.stdout.flush()
        
        try:
            # Parse PDF
            parsed = parse_pdf(str(pdf_path))
            
            # Get sections with page ranges
            sections = get_sections_with_pages(parsed)
            if not sections:
                print(f"SKIP")
                continue
            
            # Extract metadata
            paper_title = parsed.get("title", pdf_path.stem)
            authors = parsed.get("authors", "")
            year = parsed.get("year", "")
            
            file_path = f"papers/AI/{pdf_path.name}"
            
            # Chunk the document
            chunks = chunk_document(
                file_path=file_path,
                sections=sections,
                paper_title=paper_title,
                authors=authors,
                year=year,
                collection_id=collection_id
            )
            
            if not chunks:
                print(f"SKIP")
                continue
            
            # Add to vector store
            for chunk in chunks:
                v_manager.add_chunks([chunk])
                meta_manager.add_metadata(
                    chunk["metadata"]["hash"],
                    chunk["metadata"]
                )
            
            print(f"OK")
            
        except Exception as e:
            print(f"ERR")
    
    print("\nDone")
    return True

if __name__ == "__main__":
    reindex_ai_papers()
