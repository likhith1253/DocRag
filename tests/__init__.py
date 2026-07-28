import storage.vector_store

# 1. Force tests to use the test Qdrant storage path to avoid locks on the production DB
cfg = storage.vector_store._get_config()
cfg["qdrant_path"] = "./test_qdrant_storage"
