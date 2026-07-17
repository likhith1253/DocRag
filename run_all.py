import os
import sys
import subprocess
import yaml

def print_step(step):
    print(f"\n{'='*60}\n{step}\n{'='*60}")

def run_cmd(command):
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, text=True)
    if result.returncode != 0:
        print(f"Command failed with return code {result.returncode}")
        sys.exit(result.returncode)
    return result

def main():
    try:
        print_step("1. Verifying environment and config...")
        config_path = "config.yaml"
        if not os.path.exists(config_path):
            print("Error: config.yaml not found.")
            sys.exit(1)
            
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("Config loaded successfully.")

        # Step 2. Warm up/ingest (we make sure the collections are built)
        print_step("2. Building/Verifying search collections...")
        
        # We can run ingestion if Qdrant directory is missing or empty
        qdrant_path = config.get("qdrant_path", "./qdrant_storage")
        if not os.path.exists(qdrant_path) or not os.listdir(qdrant_path):
            print("Qdrant storage empty or missing. Building search index...")
            # Run ingestion flow from ingestion/loader and chunker
            from ingestion.loader import load_repository
            from ingestion.language_detect import detect_language
            from ingestion.chunker import chunk_file
            from storage.vector_store import VectorStoreManager
            from storage.knowledge_graph import KnowledgeGraphManager
            from storage.metadata_store import MetadataStoreManager
            
            workspace_path = os.getcwd()
            print(f"Using repository path: {workspace_path}")
            all_chunks = []
            for file_info in load_repository(workspace_path):
                file_path = file_info["file_path"]
                if file_path.replace("\\", "/").startswith(".venv/") or not file_path.endswith((".py", ".md")):
                    continue
                lang = detect_language(file_path)
                file_chunks = chunk_file(file_path, file_info["content"], file_info["repo_name"], file_info["branch"], lang)
                all_chunks.extend(file_chunks)
            print(f"Generated {len(all_chunks)} chunks.")

            # Build metadata store
            meta_manager = MetadataStoreManager("./metadata_store.json")
            for chunk in all_chunks:
                meta_manager.add_metadata(chunk["metadata"]["hash"], chunk["metadata"])

            # Build vector index
            v_manager = VectorStoreManager()
            v_manager.add_chunks(all_chunks)

            # Build knowledge graph
            kg_manager = KnowledgeGraphManager()
            kg_manager.build_from_chunks(all_chunks)
            kg_manager.save_to_json("./knowledge_graph.json")
            print("Search collections built successfully.")
        else:
            print("Qdrant storage exists. Skipping initial ingestion to preserve existing index.")

        python_exe = os.path.join(".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = "python" # Fallback

        # Step 3. Run all experiments
        experiments = [
            "eval/experiments/main_comparison.yaml",
            "eval/experiments/ablation_kg.yaml",
            "eval/experiments/ablation_ast.yaml",
            "eval/experiments/ablation_routing.yaml",
            "eval/experiments/embedding_ablation.yaml"
        ]

        for exp_config in experiments:
            print_step(f"Running Experiment: {exp_config}")
            run_cmd([python_exe, "eval/run_experiment.py", "--config", exp_config])

        print_step("All experiments completed successfully.")

    except Exception as e:
        print(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
