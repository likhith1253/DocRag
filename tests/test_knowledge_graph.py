import os
import unittest
import tempfile
from ingestion.loader import load_repository
from ingestion.language_detect import detect_language
from ingestion.chunker import chunk_file
from storage.knowledge_graph import KnowledgeGraphManager

class TestKnowledgeGraph(unittest.TestCase):
    def test_build_and_save(self):
        workspace_path = "d:/Document_RAG"
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
                
        self.assertTrue(len(chunks) > 0)
        
        kg = KnowledgeGraphManager()
        kg.build_from_chunks(chunks)
        
        # Verify nodes and edges exist
        self.assertTrue(len(kg.graph.nodes) > 0)
        self.assertTrue(len(kg.graph.edges) > 0)
        
        # Test serialization
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            kg.save_to_json(tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertTrue(os.path.getsize(tmp_path) > 0)
            
            kg2 = KnowledgeGraphManager()
            kg2.load_from_json(tmp_path)
            self.assertEqual(len(kg.graph.nodes), len(kg2.graph.nodes))
            self.assertEqual(len(kg.graph.edges), len(kg2.graph.edges))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()
