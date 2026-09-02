import os
import unittest
import shutil
import tempfile
from pathlib import Path
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.vector_store import VectorStoreManager

class TestVectorStore(unittest.TestCase):
    def setUp(self):
        # We will use a temporary storage path for testing to avoid overriding production DB
        self.test_qdrant_path = "./test_qdrant_storage"
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        if os.path.exists(self.test_qdrant_path):
            try:
                shutil.rmtree(self.test_qdrant_path)
            except Exception:
                pass

    def tearDown(self):
        if hasattr(VectorStoreManager, "_clients"):
            for path, client in list(VectorStoreManager._clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            VectorStoreManager._clients.clear()
        if os.path.exists(self.test_qdrant_path):
            try:
                shutil.rmtree(self.test_qdrant_path)
            except Exception:
                pass

    def test_add_and_search(self):
        # Read files from workspace_path
        workspace_path = str(Path(__file__).resolve().parents[1])
        
        # Collect chunks from a few select python files in tests
        chunks = []
        for file_info in load_repository(workspace_path):
            file_path = file_info["file_path"]
            if file_path.replace("\\", "/").startswith(".venv/") or not file_path.endswith(".py") or "test_loader" not in file_path:
                continue
            
            content = file_info["content"]
            repo_name = file_info["repo_name"]
            branch = file_info["branch"]
            lang = detect_language(file_path)
            file_chunks = chunk_file(file_path, content, repo_name, branch, lang)
            chunks.extend(file_chunks)
            if len(chunks) > 5:
                break
                
        self.assertTrue(len(chunks) > 0, "No chunks generated to index.")
        
        # Override manager's path temporarily
        manager = VectorStoreManager()
        manager.collection_name = "test_chunks"
        if manager.client.collection_exists(manager.collection_name):
            manager.client.delete_collection(manager.collection_name)
        manager._ensure_collection()
        
        # Add chunks
        manager.add_chunks(chunks)
        
        # Search — returns (chunks, timing_dict) tuple
        result_chunks, _ = manager.search("test", top_k=2)
        self.assertTrue(len(result_chunks) > 0)
        self.assertIn("content", result_chunks[0])
        self.assertIn("metadata", result_chunks[0])
        self.assertIn("score", result_chunks[0])

    def test_qdrant_path_resolves_against_repo_root(self):
        repo_root = Path(__file__).resolve().parents[1]
        original_cwd = os.getcwd()
        temp_dir = tempfile.mkdtemp()
        try:
            os.chdir(temp_dir)
            manager = VectorStoreManager()
            qdrant_cfg = manager.config.get("qdrant_path", "./qdrant_storage")
            expected_name = os.path.basename(qdrant_cfg)
            self.assertEqual(
                Path(manager.qdrant_path).resolve(),
                (repo_root / expected_name).resolve(),
            )
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(temp_dir, ignore_errors=True)

    @unittest.mock.patch("storage.vector_store.SentenceTransformer")
    def test_embedding_device_configuration(self, mock_st):
        from storage.vector_store import _get_encoder, _get_embedding_device

        # 1. CPU mode via embedding.device = "cpu"
        config_cpu = {"embedding": {"device": "cpu"}}
        device_cpu = _get_embedding_device(config_cpu)
        self.assertEqual(device_cpu, "cpu")
        _get_encoder("fake-model-cpu", device=device_cpu)
        self.assertEqual(mock_st.call_args[1].get("device"), "cpu")

        # 2. CUDA mode via embedding.device = "cuda" — GPU-preferred loading
        # now genuinely checks torch.cuda.is_available() before attempting a
        # CUDA load (so a bad/no-GPU environment falls back to CPU instead of
        # crashing); mock that check here to exercise the "CUDA available"
        # branch on this CPU-only test machine.
        config_cuda = {"embedding": {"device": "cuda"}}
        device_cuda = _get_embedding_device(config_cuda)
        self.assertEqual(device_cuda, "cuda")
        with unittest.mock.patch("torch.cuda.is_available", return_value=True), \
             unittest.mock.patch("torch.cuda.get_device_name", return_value="Fake-GPU"):
            _get_encoder("fake-model-cuda", device=device_cuda)
        self.assertEqual(mock_st.call_args[1].get("device"), "cuda")

        # 2b. CUDA requested but genuinely unavailable -> falls back to CPU
        # rather than ever calling SentenceTransformer with device="cuda".
        with unittest.mock.patch("torch.cuda.is_available", return_value=False):
            _get_encoder("fake-model-cuda-unavailable", device="cuda")
        self.assertEqual(mock_st.call_args[1].get("device"), "cpu")

        # 3. Fallback to top-level device config
        self.assertEqual(_get_embedding_device({"device": "cpu"}), "cpu")
        self.assertEqual(_get_embedding_device({"device": "cuda"}), "cuda")


if __name__ == "__main__":
    unittest.main()
