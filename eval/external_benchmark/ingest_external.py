import os
import sys

# Add the main project to path so we can import modules
sys.path.append(os.path.abspath("d:/Document_RAG"))

from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.vector_store import VectorStoreManager
from storage.knowledge_graph import KnowledgeGraphManager
from storage.metadata_store import MetadataStoreManager

def main():
    repo_path = "d:/Document_RAG/eval/external_benchmark/repos/textual"
    db_path = "d:/Document_RAG/eval/external_benchmark/db"
    os.makedirs(db_path, exist_ok=True)
    
    # Change cwd so vector store and other relative paths might be set properly?
    # VectorStoreManager uses config, which uses qdrant_path. Let's patch config or just use the manager.
    # We will just rely on the path being correct or passing absolute paths.
    
    print(f"Ingesting repository from: {repo_path}")
    all_chunks = []
    
    # Textual has docs, tests, and src. We only want python files mostly.
    for file_info in load_repository(repo_path):
        file_path = file_info["file_path"]
        if ".git" in file_path or "tests/" in file_path:
            continue
        if not file_path.endswith(".py"):
            continue
        
        lang = detect_language(file_path)
        # Override repo_name to 'textual'
        file_chunks = chunk_file(file_path, file_info["content"], "textual", "main", lang)
        all_chunks.extend(file_chunks)
        
    print(f"Generated {len(all_chunks)} chunks from Textual.")

    meta_manager = MetadataStoreManager(os.path.join(db_path, "metadata_store.json"))
    for chunk in all_chunks:
        meta_manager.add_metadata(chunk["metadata"]["hash"], chunk["metadata"])

    # Vector store might default to ./qdrant_storage. We probably shouldn't mess up the main one.
    # Let's change cwd just to be safe.
    original_cwd = os.getcwd()
    os.chdir(db_path)
    try:
        v_manager = VectorStoreManager()
        v_manager.add_chunks(all_chunks)
    finally:
        os.chdir(original_cwd)

    kg_manager = KnowledgeGraphManager()
    kg_manager.build_from_chunks(all_chunks)
    kg_manager.save_to_json(os.path.join(db_path, "knowledge_graph.json"))
    
    print("Ingestion verification complete.")

if __name__ == "__main__":
    main()
