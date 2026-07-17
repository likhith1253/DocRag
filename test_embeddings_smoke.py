import os
import yaml
from storage.vector_store import VectorStoreManager

models = [
    "all-MiniLM-L6-v2",
    "BAAI/bge-base-en-v1.5",
    "intfloat/e5-base-v2"
]

def main():
    # Read base config
    config_path = "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    for model in models:
        print(f"\n--- Testing Model: {model} ---")
        try:
            # Overwrite config for the specific model
            config["embedding_model"] = model
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f)
            
            # Initialize VectorStoreManager (which initializes SentenceTransformer)
            v_manager = VectorStoreManager()
            
            # Smoke test encoding
            text = "This is a smoke test document."
            if "e5" in model.lower():
                text = "passage: " + text
                
            embedding = v_manager.encoder.encode([text])[0]
            
            print(f"PASS - Initialized on device: {v_manager.device}")
            print(f"PASS - Embedding shape: {embedding.shape}")
        except Exception as e:
            print(f"FAIL - {str(e)}")

if __name__ == "__main__":
    main()
